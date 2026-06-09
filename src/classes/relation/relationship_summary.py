from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.classes.relation.relation import get_relation_label
from src.classes.relation.relations import get_numeric_relation, iter_live_relation_items

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


def _friendliness_label(value: int) -> str:
    if value >= 70:
        return "高好感"
    if value >= 30:
        return "好感"
    if value > 0:
        return "略有好感"
    if value <= -70:
        return "敌对"
    if value <= -20:
        return "反感"
    if value < 0:
        return "略有敌意"
    return "中立"


def build_avatar_relationship_summary(avatar: "Avatar", *, max_entries: int = 8) -> str:
    """Build a concise relationship-network summary from one avatar's perspective."""
    relation_states = dict(iter_live_relation_items(avatar))
    computed_relations = getattr(avatar, "computed_relations", {}) or {}
    targets = set(relation_states) | set(computed_relations)

    entries: list[tuple[int, str, str]] = []
    for other in targets:
        if other is avatar or getattr(other, "is_dead", False):
            continue

        state = relation_states.get(other)
        friendliness = int(getattr(state, "friendliness", 0) or 0)
        labels: list[str] = []
        if state is not None:
            if state.blood_relation is not None:
                labels.append(get_relation_label(state.blood_relation, avatar, other))
            labels.extend(
                get_relation_label(relation, avatar, other)
                for relation in sorted(state.identity_relations, key=lambda item: item.value)
            )

        computed_relation = computed_relations.get(other)
        if computed_relation is not None and computed_relation not in getattr(state, "identity_relations", set()):
            labels.append(get_relation_label(computed_relation, avatar, other))

        numeric_label = str(get_numeric_relation(avatar, other))
        if numeric_label and numeric_label not in labels:
            labels.append(numeric_label)
        friendliness_label = _friendliness_label(friendliness)
        if friendliness_label not in labels:
            labels.append(friendliness_label)

        if not labels:
            continue
        detail = "/".join(labels)
        entries.append((abs(friendliness), str(other.name), f"与{other.name}({detail})"))

    entries.sort(key=lambda item: (-item[0], item[1]))
    return "、".join(entry[2] for entry in entries[:max_entries])


def build_relationship_summary(world: Any, npc_id: str, *, max_entries: int = 8) -> str:
    """Build a human-readable Chinese relationship summary for an NPC id."""
    manager = getattr(world, "avatar_manager", None)
    if manager is None:
        return ""

    avatar = manager.get_avatar(str(npc_id))
    if avatar is None:
        return ""
    return build_avatar_relationship_summary(avatar, max_entries=max_entries)
