from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any, Callable


def _create_save_slot(*, config, get_events_db_path) -> tuple[Any, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    save_name = f"save_{timestamp}"
    saves_dir = config.paths.saves
    saves_dir.mkdir(parents=True, exist_ok=True)
    save_path = saves_dir / f"{save_name}.json"
    events_db_path = get_events_db_path(save_path)
    return save_path, events_db_path


def _select_existed_sects(*, sects_by_id, needed_sects: int) -> list[Any]:
    from src.config.presets import get_active_preset_id, get_preset_sect_ids

    preset_sect_ids = get_preset_sect_ids(get_active_preset_id())
    all_sects = [
        sects_by_id[sect_id]
        for sect_id in preset_sect_ids
        if sect_id in sects_by_id
    ]
    if not preset_sect_ids:
        all_sects = list(sects_by_id.values())
    if needed_sects <= 0 or not all_sects:
        return []

    pool = list(all_sects)
    random.shuffle(pool)
    return pool[:needed_sects]


def _setting_count(settings: Any, name: str) -> int:
    direct = getattr(settings, name, None)
    if direct is not None:
        return int(direct)
    defaults = getattr(settings, "new_game_defaults", None)
    if defaults is not None and hasattr(defaults, name):
        return int(getattr(defaults, name))
    raise AttributeError(f"settings missing {name}")


def resolve_generation_counts(*, scenario, settings) -> dict[str, int]:
    initial_state = getattr(scenario, "scenario", scenario) or {}
    if isinstance(initial_state, dict) and "initial_state" in initial_state:
        initial_state = initial_state.get("initial_state", {}) or {}
    profile = (
        initial_state.get("generation_profile")
        if isinstance(initial_state, dict)
        else None
    ) or {}

    if profile.get("use_scripted_only"):
        return {"npc_count": 0, "sect_count": 0}

    npc_count = profile.get("random_npc_count")
    if npc_count is None:
        npc_count = _setting_count(settings, "init_npc_num")

    sect_count = profile.get("random_sect_count")
    if sect_count is None:
        sect_count = _setting_count(settings, "sect_num")

    return {"npc_count": int(npc_count), "sect_count": int(sect_count)}


def _select_scenario_existed_sects(*, sects_by_id, random_sect_count: int, resolved_scenario) -> list[Any]:
    initial_state = (
        getattr(resolved_scenario, "scenario", {}) or {}
    ).get("initial_state", {}) if resolved_scenario is not None else {}
    scripted_ids: list[int] = []
    for item in list((initial_state or {}).get("sects", []) or []):
        try:
            sect_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if sect_id in sects_by_id and sect_id not in scripted_ids:
            scripted_ids.append(sect_id)

    scripted_sects = [sects_by_id[sect_id] for sect_id in scripted_ids]
    if random_sect_count <= 0:
        return scripted_sects

    remaining = {
        sect_id: sect
        for sect_id, sect in sects_by_id.items()
        if int(sect_id) not in set(scripted_ids)
    }
    return scripted_sects + _select_existed_sects(
        sects_by_id=remaining,
        needed_sects=random_sect_count,
    )


async def _apply_world_lore_if_needed(
    *,
    world,
    run_config,
    world_lore_manager_cls,
    build_world_lore_snapshot,
) -> None:
    world_lore = run_config.world_lore
    if not world_lore or not world_lore.strip():
        return

    world.set_world_lore(world_lore)
    print(f"Reshaping world based on worldview and history: {world_lore[:50]}...")
    try:
        world_lore_mgr = world_lore_manager_cls(world)
        await world_lore_mgr.apply_world_lore(world_lore)
        world.world_lore_snapshot = build_world_lore_snapshot(world)
        print("World lore applied")
    except Exception as exc:
        print(f"[Warning] Failed to apply world lore: {exc}")


async def _generate_initial_avatars(
    *,
    world,
    target_total_count: int,
    existed_sects,
    make_random_avatars,
) -> dict[Any, Any]:
    if target_total_count <= 0:
        return {}

    def _make_random_sync():
        return make_random_avatars(
            world,
            count=target_total_count,
            current_month_stamp=world.month_stamp,
            existed_sects=existed_sects,
        )

    random_avatars = await asyncio.to_thread(_make_random_sync)
    print(f"Generated {len(random_avatars)} random NPCs")
    return random_avatars


def _inject_scripted_scenario_initial_state_if_needed(*, world, resolved_scenario) -> None:
    if getattr(world, "scripted_scenario", None) is None or resolved_scenario is None:
        return

    from src.scenario.injector import inject_scenario_initial_state_into_world

    inject_scenario_initial_state_into_world(world, resolved_scenario)


async def _prepare_initial_character_profiles(*, world) -> None:
    from src.sim.simulator_engine.phases import lifecycle

    avatar_manager = getattr(world, "avatar_manager", None)
    if avatar_manager is None:
        return

    if hasattr(avatar_manager, "get_living_avatars"):
        living_avatars = list(avatar_manager.get_living_avatars())
    else:
        living_avatars = list(getattr(avatar_manager, "avatars", {}).values())
    if not living_avatars:
        return

    print("Preparing initial character profiles...")
    objective_results = await asyncio.gather(
        *[lifecycle.process_avatar_long_term_objective(avatar) for avatar in living_avatars],
        return_exceptions=True,
    )
    event_manager = getattr(world, "event_manager", None)
    if event_manager is not None:
        for result in objective_results:
            if isinstance(result, Exception):
                print(f"[Warning] Initial long-term objective generation failed: {result}")
                continue
            if result is not None:
                event_manager.add_event(result)

    backstory_results = await asyncio.gather(
        *[lifecycle.process_avatar_backstory(avatar) for avatar in living_avatars],
        return_exceptions=True,
    )
    for result in backstory_results:
        if isinstance(result, Exception):
            print(f"[Warning] Initial backstory generation failed: {result}")
    print("Initial character profiles prepared")


async def _run_llm_check_background(
    *,
    runtime,
    init_generation: int,
    check_llm_connectivity: Callable[[], tuple[bool, str]],
) -> None:
    if int(runtime.get("init_generation", 0) or 0) != init_generation:
        return
    runtime.update({"llm_check_pending": True})
    try:
        print("Checking LLM connectivity in background...")
        success, error_msg = await asyncio.to_thread(check_llm_connectivity)
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        if not success:
            print(f"[Warning] LLM connectivity check failed: {error_msg}")
            runtime.update(
                {
                    "llm_check_failed": True,
                    "llm_error_message": error_msg,
                    "llm_check_pending": False,
                }
            )
        else:
            print("LLM connectivity check passed")
            runtime.update(
                {
                    "llm_check_failed": False,
                    "llm_error_message": "",
                    "llm_check_pending": False,
                }
            )
    except Exception as exc:
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        runtime.update(
            {
                "llm_check_failed": True,
                "llm_error_message": f"连通性检测异常：{exc}",
                "llm_check_pending": False,
            }
        )
        print(f"[Warning] LLM connectivity check failed: {exc}")


async def _run_initial_events_background(*, runtime, sim, init_generation: int) -> None:
    async def _do_step() -> None:
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        print("Generating initial events in background...")
        try:
            await sim.step()
            print("Initial events generation completed")
        except Exception as exc:
            print(f"[Warning] Initial events generation failed: {exc}")

    try:
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        await runtime.run_mutation(_do_step)
    except Exception as exc:
        print(f"[Warning] Initial events background task failed: {exc}")


async def perform_game_initialization(
    *,
    runtime,
    avatar_assets: dict[str, list[int]],
    assets_path: str,
    config,
    update_init_progress: Callable[[int, str], None],
    reset_runtime_custom_content: Callable[[], None],
    reload_all_static_data: Callable[[], None],
    scan_avatar_assets: Callable[..., dict[str, list[int]]],
    load_cultivation_world_map: Callable[[], Any],
    get_events_db_path,
    get_runtime_run_config: Callable[[Any], Any],
    world_cls,
    create_month_stamp,
    year_cls,
    month_enum,
    generate_dynasty: Callable[[], Any],
    generate_emperor: Callable[[Any, int], Any],
    event_cls,
    translate: Callable[..., str],
    simulator_cls,
    model_to_dict: Callable[[Any], dict[str, Any]],
    world_lore_manager_cls,
    build_world_lore_snapshot: Callable[[Any], Any],
    sects_by_id,
    make_random_avatars,
    check_llm_connectivity: Callable[[], tuple[bool, str]],
    get_active_scenario: Callable[[], Any | None] | None = None,
) -> None:
    runtime.begin_initialization()
    runtime.clear_roleplay_session()

    async def _do_init():
        update_init_progress(0, "scanning_assets")
        print("Resetting world rule data...")
        reset_runtime_custom_content()
        reload_all_static_data()
        await asyncio.to_thread(
            lambda: avatar_assets.update(scan_avatar_assets(assets_path=assets_path))
        )

        update_init_progress(1, "loading_map")
        game_map = await asyncio.to_thread(load_cultivation_world_map)

        save_path, events_db_path = _create_save_slot(
            config=config,
            get_events_db_path=get_events_db_path,
        )
        runtime.update({"current_save_path": save_path})
        print(f"Events database: {events_db_path}")

        run_config = get_runtime_run_config(runtime)
        start_year = getattr(config.world, "start_year", 100)
        world = world_cls.create_with_db(
            map=game_map,
            month_stamp=create_month_stamp(year_cls(start_year), month_enum.JANUARY),
            events_db_path=events_db_path,
            start_year=start_year,
        )
        world.runtime = runtime
        world.dynasty = generate_dynasty()
        world.dynasty.current_emperor = generate_emperor(world.dynasty, int(world.month_stamp))
        world.event_manager.add_event(
            event_cls(
                month_stamp=world.month_stamp,
                content=translate(
                    "{dynasty_title} has enthroned a new ruler, and {emperor_name} ascends as emperor.",
                    dynasty_title=world.dynasty.title,
                    emperor_name=world.dynasty.current_emperor.name,
                ),
                is_major=True,
            )
        )

        sim = simulator_cls(world)
        sim.awakening_rate = run_config.npc_awakening_rate_per_month
        world.run_config_snapshot = model_to_dict(run_config)
        resolved_scenario = get_active_scenario() if get_active_scenario is not None else None
        generation_counts = resolve_generation_counts(
            scenario=resolved_scenario,
            settings=run_config,
        )

        update_init_progress(2, "shaping_world_lore")
        await _apply_world_lore_if_needed(
            world=world,
            run_config=run_config,
            world_lore_manager_cls=world_lore_manager_cls,
            build_world_lore_snapshot=build_world_lore_snapshot,
        )

        update_init_progress(3, "initializing_sects")
        if resolved_scenario is None:
            existed_sects = _select_existed_sects(
                sects_by_id=sects_by_id,
                needed_sects=int(generation_counts["sect_count"] or 0),
            )
        else:
            existed_sects = _select_scenario_existed_sects(
                sects_by_id=sects_by_id,
                random_sect_count=int(generation_counts["sect_count"] or 0),
                resolved_scenario=resolved_scenario,
            )

        update_init_progress(4, "generating_avatars")
        final_avatars = await _generate_initial_avatars(
            world=world,
            target_total_count=int(generation_counts["npc_count"] or 0),
            existed_sects=existed_sects,
            make_random_avatars=make_random_avatars,
        )

        world.avatar_manager.avatars.update(final_avatars)
        _inject_scripted_scenario_initial_state_if_needed(
            world=world,
            resolved_scenario=resolved_scenario,
        )
        world.existed_sects = existed_sects
        world.sect_context.from_existed_sects(existed_sects)
        runtime.update({"world": world, "sim": sim})
        try:
            from src.mod_platform.python_hooks import dispatch_lifecycle_hook
            dispatch_lifecycle_hook("on_world_init", world)
        except Exception as exc:
            runtime.fail_initialization(str(exc))
            raise

        update_init_progress(5, "preparing_character_profiles")
        await _prepare_initial_character_profiles(world=world)

        update_init_progress(6, "generating_initial_events")
        runtime.set_paused(True)
        runtime.finish_initialization(phase_name="complete")
        runtime.update(
            {
                "init_progress": 100,
                "llm_check_failed": False,
                "llm_error_message": "",
                "llm_check_pending": True,
            }
        )
        init_generation = int(runtime.get("init_generation", 0) or 0)
        asyncio.create_task(
            _run_llm_check_background(
                runtime=runtime,
                init_generation=init_generation,
                check_llm_connectivity=check_llm_connectivity,
            )
        )
        asyncio.create_task(
            _run_initial_events_background(
                runtime=runtime,
                sim=sim,
                init_generation=init_generation,
            )
        )
        print("Game world initialization completed!")

    try:
        await runtime.run_mutation(_do_init)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        runtime.fail_initialization(str(exc))
        print(f"[Error] Initialization failed: {exc}")
