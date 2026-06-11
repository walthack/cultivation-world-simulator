"""v1.6 end-to-end acceptance — the branch+storyline primitive replaces (and
improves on) v1.5's manual flag-bookkeeping branch.

v1.5 expressed the han-song fork as TWO hand-authored variant events, each
gated on a different player-choice flag (cheng_loyal_to_song / cheng_hedged_han);
mutual exclusion relied on the author keeping those flags mutually exclusive.

v1.6 expresses the same fork as ONE `branch` selector that activates one of two
named storylines; the engine — not the author — guarantees the unchosen line is
suppressed. These tests prove behavioural equivalence on the normal inputs AND
that the primitive is strictly safer when the author's flags are NOT mutually
exclusive.

This is a self-contained engine-acceptance fixture: it does NOT touch the
liuchao scenario (which is being realigned to the source novels separately).
"""

from __future__ import annotations

import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.branch_handler import handle_branch
from src.scenario.event_handlers.side_event_handler import handle_side_event


HARDENS = "han_hardens_against_song"
CHANNEL = "han_keeps_song_channel"


def _state(**flags):
    return {
        "world": {"year": 1, "month": 1, "world_flags": dict(flags)},
        "scenario_runtime": {"scenario_id": "demo", "triggered_event_ids": []},
    }


def _handlers():
    return {"branch": handle_branch, "side_event": handle_side_event}


def _side(event_id, *, flag_effect, condition=None, storyline=None):
    event = {
        "id": event_id,
        "type": "side_event",
        "trigger": {"year": 1, "month": 1, "condition": condition or {"always": {}}},
        "effects": [{"type": "set_flag", "flag": flag_effect}],
    }
    if storyline is not None:
        event["storyline"] = storyline
    return event


# --- the two encodings of the same fork ------------------------------------

def _manual_timeline():
    """v1.5 style: two flag-gated variant events, no first-class fork."""
    return [
        _side("han-song-loyal", flag_effect=HARDENS,
              condition={"world_flag": {"flag": "cheng_loyal_to_song"}}),
        _side("han-song-hedge", flag_effect=CHANNEL,
              condition={"world_flag": {"flag": "cheng_hedged_han"}}),
    ]


def _primitive_timeline():
    """v1.6 style: one branch selector + two storyline-tagged beats."""
    return [
        {
            "id": "han-song-fork",
            "type": "branch",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "branches": [
                {"id": "hardened", "condition": {"world_flag": {"flag": "cheng_loyal_to_song"}},
                 "effects": [{"type": "activate_storyline", "storyline": "han_hardened"}]},
                {"id": "channel", "condition": {"world_flag": {"flag": "cheng_hedged_han"}},
                 "effects": [{"type": "activate_storyline", "storyline": "han_channel"}]},
            ],
        },
        _side("han-hardened-beat", flag_effect=HARDENS, storyline="han_hardened"),
        _side("han-channel-beat", flag_effect=CHANNEL, storyline="han_channel"),
    ]


async def _run(timeline, **flags):
    state = _state(**flags)
    await EventDispatcher(timeline, handlers=_handlers()).dispatch_month(state)
    return state["world"]["world_flags"]


# --- equivalence on the normal player inputs -------------------------------

@pytest.mark.asyncio
async def test_loyal_outcome_is_equivalent():
    manual = await _run(_manual_timeline(), cheng_loyal_to_song=True)
    primitive = await _run(_primitive_timeline(), cheng_loyal_to_song=True)

    assert manual.get(HARDENS) is True and manual.get(CHANNEL) is None
    assert primitive.get(HARDENS) is True and primitive.get(CHANNEL) is None
    assert manual.get(HARDENS) == primitive.get(HARDENS)


@pytest.mark.asyncio
async def test_hedge_outcome_is_equivalent():
    manual = await _run(_manual_timeline(), cheng_hedged_han=True)
    primitive = await _run(_primitive_timeline(), cheng_hedged_han=True)

    assert manual.get(CHANNEL) is True and manual.get(HARDENS) is None
    assert primitive.get(CHANNEL) is True and primitive.get(HARDENS) is None
    assert manual.get(CHANNEL) == primitive.get(CHANNEL)


# --- the improvement: engine-enforced mutual exclusion ---------------------

@pytest.mark.asyncio
async def test_primitive_is_safer_when_author_flags_are_not_exclusive():
    """If both choice flags are set (an authoring slip), the MANUAL encoding
    fires BOTH variants — a contradictory world state. The PRIMITIVE picks the
    first matching branch and the engine suppresses the other line entirely."""
    manual = await _run(_manual_timeline(), cheng_loyal_to_song=True, cheng_hedged_han=True)
    primitive = await _run(_primitive_timeline(), cheng_loyal_to_song=True, cheng_hedged_han=True)

    # manual: both outcomes leak — the bug the primitive exists to prevent
    assert manual.get(HARDENS) is True and manual.get(CHANNEL) is True

    # primitive: exactly one line wins (first branch), the sibling is suppressed
    assert primitive.get(HARDENS) is True
    assert primitive.get(CHANNEL) is None
