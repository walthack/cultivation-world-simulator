"""v1.7 M3 — bounded context assembly (Q4 layering + Q11 budget).

build_narrative_prompt layers, beyond the M1 mandatory context, two optional
layers within a budget: the involved-avatar relationship subgraph and a recent
chronicle. The chronicle is AUTHORED/mechanical text only — generated narration
must never feed back into a later generation (no context feedback loop).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.classes.event import Event
from src.scenario.narrative_fill import (
    CONTEXT_BUDGET_CHARS,
    _assemble_within_budget,
    _chronicle_context,
    _relationship_context,
    build_narrative_prompt,
)
from src.systems.time import Month, Year, create_month_stamp


def _event_with_avatars():
    return {
        "id": "e",
        "name": "草原惊变",
        "description": "秦军压境",
        "effects": [{"type": "relation_change", "a": "cheng-zongyang", "b": "wang-zhe", "delta": 5}],
    }


# --- relationship layer ------------------------------------------------------

def test_relationship_layer_surfaces_involved_avatar_subgraph(monkeypatch):
    seen = []

    def fake_summary(world, npc_id, *, max_entries):
        seen.append((npc_id, max_entries))
        return f"与某人(好感) [{npc_id}]"

    monkeypatch.setattr(
        "src.classes.relation.relationship_summary.build_relationship_summary", fake_summary
    )

    text = _relationship_context(_event_with_avatars(), SimpleNamespace())

    assert "cheng-zongyang" in text and "wang-zhe" in text
    assert {npc for npc, _ in seen} == {"cheng-zongyang", "wang-zhe"}
    assert all(m == 6 for _, m in seen)  # RELATIONSHIP_MAX_ENTRIES bound


def test_relationship_layer_is_safe_without_avatar_manager():
    # SimpleNamespace world has no avatar_manager → graceful empty, no crash
    assert _relationship_context(_event_with_avatars(), SimpleNamespace()) == ""


# --- chronicle layer: the anti-feedback-loop guard ---------------------------

def _narrated_event():
    ev = Event(
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        content="MECH-CONTENT",
    )
    ev.narration = "GENERATED-NARRATION"
    return ev


def test_chronicle_uses_content_never_generated_narration():
    world = SimpleNamespace(
        event_manager=SimpleNamespace(get_recent_events=lambda limit: [_narrated_event()])
    )
    text = _chronicle_context(world)

    assert "MECH-CONTENT" in text          # authored/mechanical text feeds context
    assert "GENERATED-NARRATION" not in text  # generated fill never feeds back


def test_chronicle_is_safe_without_event_manager():
    assert _chronicle_context(SimpleNamespace()) == ""


def test_chronicle_is_safe_when_event_str_raises():
    class Boom:
        def __str__(self):
            raise RuntimeError("bad event")

    world = SimpleNamespace(
        event_manager=SimpleNamespace(get_recent_events=lambda limit: [Boom()])
    )
    assert _chronicle_context(world) == ""  # formatting failure degrades, never raises


def test_relationship_layer_caps_number_of_summarized_avatars(monkeypatch):
    calls = []

    def fake_summary(world, npc_id, *, max_entries):
        calls.append(npc_id)
        return f"rel[{npc_id}]"

    monkeypatch.setattr(
        "src.classes.relation.relationship_summary.build_relationship_summary", fake_summary
    )
    many = {"id": "e", "effects": [{"type": "x", "npc_id": f"av-{i}"} for i in range(10)]}

    _relationship_context(many, SimpleNamespace())

    assert len(calls) <= 4  # RELATIONSHIP_MAX_AVATARS


def test_full_prompt_never_carries_generated_narration_back():
    """Integration: the assembled prompt includes chronicle content but never the
    generated narration of a past event (Q12 / no feedback loop)."""
    world = SimpleNamespace(
        event_manager=SimpleNamespace(get_recent_events=lambda limit: [_narrated_event()])
    )
    prompt = build_narrative_prompt({"id": "e", "name": "n", "description": "d"}, world)

    assert "MECH-CONTENT" in prompt
    assert "GENERATED-NARRATION" not in prompt


# --- budget ------------------------------------------------------------------

def test_budget_keeps_mandatory_drops_optional_when_tight():
    mandatory = [("M", "x" * 100)]  # → "M：" + 100 = 102 chars
    optional = [("O1", "y" * 100), ("O2", "z" * 100)]  # → 103 chars each
    out = _assemble_within_budget(mandatory, optional, budget=250)  # fits M + O1, not O2

    assert "M：" in out          # mandatory always kept
    assert "O1：" in out          # first optional fits
    assert "O2：" not in out      # second would exceed budget → dropped


def test_budget_hard_caps_total_length():
    mandatory = [("M", "x" * 10000)]
    out = _assemble_within_budget(mandatory, [], budget=500)
    assert len(out) <= 500


def test_build_prompt_is_bounded_even_with_huge_authored_fields():
    huge = "巨" * 50000
    prompt = build_narrative_prompt({"id": "e", "name": huge, "description": huge}, SimpleNamespace())
    # the fenced data region is bounded by the context budget (plus the fixed
    # instruction/fence scaffolding around it)
    assert len(prompt) < CONTEXT_BUDGET_CHARS + 2000
