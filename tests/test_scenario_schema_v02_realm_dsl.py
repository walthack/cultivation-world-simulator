from __future__ import annotations

from src.config.presets import (
    get_preset_realm_by_canonical_name,
    get_preset_realm_display_name,
    get_preset_realms,
)
from src.scenario.schema_constants import (
    CANONICAL_EFFECT_TYPES,
    CANONICAL_PREDICATES,
    V01_TO_V02_EFFECT_DRIFT,
    V01_TO_V02_PREDICATE_DRIFT,
)


def test_realm_alias_round_trip():
    realms = get_preset_realms("default")

    assert realms[0] == {
        "id": "QI_REFINEMENT",
        "canonical_name": "QI_REFINEMENT",
        "display_name": "练气",
    }
    assert get_preset_realm_display_name("default", "QI_REFINEMENT") == "练气"


def test_realm_canonical_name_lookup():
    assert get_preset_realm_by_canonical_name("default", "foundation_establishment") == "FOUNDATION_ESTABLISHMENT"
    assert get_preset_realm_by_canonical_name("liuchao", "tong_you") == "TONG_YOU"


def test_dsl_canonical_predicates_are_frozen():
    assert "player_realm" in CANONICAL_PREDICATES
    assert "world_flag" in CANONICAL_PREDICATES
    assert "flag_set" not in CANONICAL_PREDICATES
    assert V01_TO_V02_PREDICATE_DRIFT["flag_set"] == "world_flag"


def test_dsl_canonical_effects_are_frozen():
    assert "set_flag" in CANONICAL_EFFECT_TYPES
    assert "clear_flag" in CANONICAL_EFFECT_TYPES
    assert "unset_flag" not in CANONICAL_EFFECT_TYPES
    assert V01_TO_V02_EFFECT_DRIFT["unset_flag"] == "clear_flag"
