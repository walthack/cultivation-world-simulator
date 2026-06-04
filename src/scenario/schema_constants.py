from __future__ import annotations

from enum import StrEnum


class ScenarioPredicate(StrEnum):
    CONTROLLED_AVATAR_IS = "controlled_avatar_is"
    PLAYER_REALM = "player_realm"
    PLAYER_SECT = "player_sect"
    PLAYER_HAS_SKILL = "player_has_skill"
    PLAYER_STAT = "player_stat"
    PLAYER_RELATION = "player_relation"
    WORLD_YEAR = "world_year"
    WORLD_MONTH = "world_month"
    WORLD_FLAG = "world_flag"
    NPC_ALIVE = "npc_alive"
    NPC_REALM = "npc_realm"
    NPC_RELATION = "npc_relation"
    RANDOM_CHANCE = "random_chance"
    ALWAYS = "always"
    EVENT_TRIGGERED = "event_triggered"
    VAR_EQUALS = "var_equals"


class ScenarioEffectType(StrEnum):
    GAIN_SKILL = "gain_skill"
    LOSE_SKILL = "lose_skill"
    GAIN_STAT = "gain_stat"
    LOSE_STAT = "lose_stat"
    SET_STAT = "set_stat"
    GAIN_ITEM = "gain_item"
    LOSE_ITEM = "lose_item"
    SET_FLAG = "set_flag"
    CLEAR_FLAG = "clear_flag"
    NPC_JOIN = "npc_join"
    NPC_LEAVE = "npc_leave"
    NPC_DIE = "npc_die"
    NPC_SET_REALM = "npc_set_realm"
    NPC_SET_RELATION = "npc_set_relation"
    RELATION_CHANGE = "relation_change"
    WORLD_EVENT_TRIGGER = "world_event_trigger"
    ECONOMY_EVENT = "economy_event"
    SET_VAR = "set_var"


CANONICAL_PREDICATES = frozenset(item.value for item in ScenarioPredicate)
CANONICAL_EFFECT_TYPES = frozenset(item.value for item in ScenarioEffectType)

V01_TO_V02_PREDICATE_DRIFT = {
    "avatar_alive": "npc_alive",
    "avatar_dead": "not npc_alive",
    "avatar_at_sect": "npc relation/state predicate not in Batch A canonical set",
    "avatar_realm_at_least": "npc_realm",
    "avatar_age_at_least": "player_stat or npc state extension required",
    "sect_exists": "not implemented in Stage 1 canonical set",
    "sect_leader_is": "not implemented in Stage 1 canonical set",
    "flag_set": "world_flag",
    "flag_unset": "world_flag with value=false",
    "relation_at_least": "npc_relation or player_relation",
    "event_triggered": "event_triggered",
    "event_outcome_was": "not implemented in Stage 1 canonical set",
    "controlled_avatar_is": "controlled_avatar_is",
}

V01_TO_V02_EFFECT_DRIFT = {
    "unset_flag": "clear_flag",
    "spawn_avatar": "character_introduction handler or future npc_spawn effect",
    "delete_avatar": "npc_die",
    "set_avatar_field": "set_stat for player stats or future npc_set_field",
    "change_avatar_sect": "npc_join/npc_leave for Stage 1 scope",
    "set_avatar_realm": "npc_set_realm",
    "grant_goldfinger": "future goldfinger effect",
    "set_relation": "npc_set_relation",
    "delta_relation": "relation_change",
    "add_sect_member": "npc_join",
    "remove_sect_member": "npc_leave",
    "change_sect_leader": "future sect effect",
    "set_world_field": "set_flag/clear_flag for flag scope",
    "apply_to_region": "future region effect",
    "economy_event": "economy_event",
    "inject_narrative": "future narrative effect",
}
