"""v1.7 M2 — reproducible narration cache key (Q3/Q8).

Generated narration is frozen into the save keyed by
`(scenario_id, event_id, resolved_outcome, content_locale)` so a reload reads
the cached text instead of regenerating (which would be non-reproducible — the
LLM client exposes no seed, Q9). The cache itself lives on a dedicated field
(`ScriptedScenarioState.narration_cache`), a SIBLING of `state`, so it is never
readable by `var_equals` / conditions — preserving the Q12 isolation boundary.
"""

from __future__ import annotations

from typing import Any

# Unit separator: not valid inside scenario/event ids or locale codes, so the
# composite key is unambiguous.
_SEP = "\x1f"


def resolved_outcome(event_id: str, event_outcomes: dict[str, Any] | None) -> str:
    """The stable per-event outcome that distinguishes alternate narrations of the
    same event: the selected branch id (branch events) or chosen choice id (choice
    events), else "" for plain events. Dispatch records both into `event_outcomes`."""
    outcome = (event_outcomes or {}).get(str(event_id))
    if not isinstance(outcome, dict):
        return ""
    return str(outcome.get("branch_id") or outcome.get("choice_id") or "")


def narration_cache_key(scenario_id: Any, event_id: Any, outcome: Any, locale: Any) -> str:
    """Compose the reproducibility key. Locale is part of the key (Q8) so each
    content_locale stores its own narration and they never overwrite each other."""
    return _SEP.join(
        (str(scenario_id or ""), str(event_id or ""), str(outcome or ""), str(locale or ""))
    )
