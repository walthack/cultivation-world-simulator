from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar
from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.gender import Gender
from src.classes.root import Root
from src.systems.cultivation import Realm
from src.systems.time import Month, Year, create_month_stamp


def _gender_from_payload(value: Any) -> Gender:
    if value is None:
        return Gender.MALE
    try:
        return Gender(str(value).strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid avatar gender: {value}") from exc


def _create_minimal_import_world() -> World:
    game_map = Map(width=10, height=10)
    for x in range(10):
        for y in range(10):
            game_map.create_tile(x, y, TileType.PLAIN)
    return World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))


def bulk_import_world(runtime, *, avatars: list[dict[str, Any]], world_flags: dict[str, Any]) -> dict[str, Any]:
    world = runtime.get("world")
    if not world:
        world = _create_minimal_import_world()
        if hasattr(runtime, "update"):
            runtime.update({"world": world})
        else:
            runtime.state.update({"world": world})

    imported_avatar_ids: list[str] = []
    for item in avatars:
        avatar_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if not avatar_id:
            raise HTTPException(status_code=400, detail="Avatar id is required")
        if not name:
            raise HTTPException(status_code=400, detail="Avatar name is required")
        if avatar_id in world.avatar_manager.avatars:
            raise HTTPException(status_code=409, detail=f"Avatar already exists: {avatar_id}")

        avatar = Avatar(
            world=world,
            name=name,
            id=avatar_id,
            birth_month_stamp=world.month_stamp,
            age=Age(
                int(item.get("age", 20) or 20),
                Realm.Qi_Refinement,
                innate_max_lifespan=80,
            ),
            gender=_gender_from_payload(item.get("gender")),
            pos_x=int(item.get("x", 0) or 0),
            pos_y=int(item.get("y", 0) or 0),
            root=Root.GOLD,
            personas=[],
            alignment=Alignment.RIGHTEOUS,
        )
        avatar.personas = []
        avatar.technique = None
        avatar.weapon = None
        avatar.auxiliary = None
        avatar.recalc_effects()
        world.avatar_manager.register_avatar(avatar, is_newly_born=True)
        imported_avatar_ids.append(str(avatar.id))

    flags = getattr(world, "world_flags", None)
    if not isinstance(flags, dict):
        flags = {}
        world.world_flags = flags
    flags.update(dict(world_flags or {}))

    return {
        "status": "ok",
        "imported_avatar_ids": imported_avatar_ids,
        "world_flags": dict(flags),
    }
