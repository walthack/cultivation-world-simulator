from __future__ import annotations

import random

from src.classes.action_runtime import ActionStatus
from src.classes.core.avatar import Avatar
from src.classes.event import Event
from src.classes.mutual_action.conversation import Conversation
from src.classes.relation.relations import ensure_numeric_relation_state, regress_yearly_friendliness, update_second_degree_relations
from src.run.log import get_logger
from src.utils.config import CONFIG
from src.systems.time import Month


def phase_process_interactions(avatar_manager, events: list[Event]) -> None:
    # 旧版关系系统使用“按事件累计互动次数”，新版已废弃。
    return


def phase_handle_interactions(
    avatar_manager,
    events: list[Event],
    processed_ids: set[str],
) -> None:
    for event in events:
        processed_ids.add(event.id)
    return


async def phase_evolve_relations(avatar_manager, living_avatars: list[Avatar]) -> list[Event]:
    current_month = int(living_avatars[0].world.month_stamp) if living_avatars else None
    for avatar in living_avatars:
        ensure_numeric_relation_state(avatar, current_month=current_month)
    return []


def _automatic_social_config(world) -> tuple[float, int]:
    scenario = getattr(world, "scripted_scenario", None)
    if scenario is None:
        return 0.0, 0

    profile = getattr(scenario, "generation_profile", {}) or {}
    social_config = profile.get("social_simulation", {}) or {}
    if not isinstance(social_config, dict) or social_config.get("enabled", True) is False:
        return 0.0, 0

    default_probability = float(getattr(CONFIG.world.story.probabilities, "daily_social", 0.0))
    probability = float(social_config.get("conversation_probability", default_probability))
    max_conversations = int(social_config.get("max_conversations_per_month", 1))
    return max(0.0, min(1.0, probability)), max(0, max_conversations)


def _pair_probability(base_probability: float, avatar_a: Avatar, avatar_b: Avatar) -> float:
    average_friendliness = (avatar_a.get_friendliness(avatar_b) + avatar_b.get_friendliness(avatar_a)) / 2
    friendliness_multiplier = 1.0 + max(-100.0, min(100.0, average_friendliness)) / 200.0
    return max(0.0, min(1.0, base_probability * friendliness_multiplier))


def _controlled_avatar_id(world) -> str:
    runtime = getattr(world, "runtime", None)
    if runtime is None or not hasattr(runtime, "get_roleplay_session"):
        return ""
    return str(runtime.get_roleplay_session().get("controlled_avatar_id") or "")


async def _run_automatic_conversation(world, initiator: Avatar, target: Avatar) -> list[Event]:
    action = Conversation(initiator, world)
    can_start, _reason = action.can_start(target_avatar=target)
    if not can_start:
        return []

    action.start(target_avatar=target)
    result = action.step(target_avatar=target)
    for _ in range(2):
        if result.status != ActionStatus.RUNNING:
            break
        response_task = getattr(action, "_response_task", None)
        if response_task is None:
            return []
        await response_task
        result = action.step(target_avatar=target)

    if result.status != ActionStatus.COMPLETED:
        return []

    events = list(result.events)
    events.extend(await action.finish(target_avatar=target))
    return events


async def phase_automatic_social(world, ctx) -> list[Event]:
    base_probability, max_conversations = _automatic_social_config(world)
    if base_probability <= 0.0 or max_conversations <= 0:
        return []

    controlled_avatar_id = _controlled_avatar_id(world)
    avatars_by_region: dict[int, list[Avatar]] = {}
    for avatar in ctx.living_avatars:
        if str(avatar.id) == controlled_avatar_id:
            continue
        tile = getattr(avatar, "tile", None)
        region = getattr(tile, "region", None)
        if region is not None:
            avatars_by_region.setdefault(id(region), []).append(avatar)

    candidate_pairs: list[tuple[Avatar, Avatar]] = []
    for avatars in avatars_by_region.values():
        for index, avatar_a in enumerate(avatars):
            for avatar_b in avatars[index + 1:]:
                candidate_pairs.append((avatar_a, avatar_b))
    random.shuffle(candidate_pairs)

    events: list[Event] = []
    matched_avatar_ids: set[str] = set()
    conversation_count = 0
    for avatar_a, avatar_b in candidate_pairs:
        if conversation_count >= max_conversations:
            break
        if str(avatar_a.id) in matched_avatar_ids or str(avatar_b.id) in matched_avatar_ids:
            continue
        if random.random() >= _pair_probability(base_probability, avatar_a, avatar_b):
            continue

        try:
            events.extend(await _run_automatic_conversation(world, avatar_a, avatar_b))
        except Exception as exc:
            get_logger().logger.error(
                "Automatic conversation failed for %s(%s) and %s(%s): %s",
                avatar_a.name,
                avatar_a.id,
                avatar_b.name,
                avatar_b.id,
                exc,
                exc_info=True,
            )
            continue

        matched_avatar_ids.update((str(avatar_a.id), str(avatar_b.id)))
        conversation_count += 1

    return events


def phase_update_calculated_relations(world, living_avatars: list[Avatar]) -> None:
    if world.month_stamp.get_month() != Month.JANUARY:
        return

    for avatar in living_avatars:
        regress_yearly_friendliness(avatar, current_month=int(world.month_stamp))
        update_second_degree_relations(avatar)
        ensure_numeric_relation_state(avatar, current_month=int(world.month_stamp))
