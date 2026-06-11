from __future__ import annotations

from typing import Any

from ..condition_evaluator import evaluate_condition
from ..effect_applier import apply_effects


def _select_branch(state: Any, event: dict[str, Any]) -> dict[str, Any] | None:
    """First branch whose condition holds; else the default_branch; else None."""
    branches = event.get("branches", []) or []
    for branch in branches:
        if evaluate_condition(state, branch.get("condition")):
            return branch
    default_id = event.get("default_branch")
    if default_id is not None:
        for branch in branches:
            if branch.get("id") == default_id:
                return branch
    return None


async def handle_branch(state: Any, event: dict[str, Any]) -> dict[str, Any]:
    """Branch-point: apply the selected branch's effects (a runtime no-op when
    nothing matches — never raise, that would crash the game loop; structural
    soundness is enforced at load time)."""
    branch = _select_branch(state, event)
    if branch is None:
        return {"status": "ok", "event_id": event.get("id"), "selected_branch": None}
    apply_effects(state, branch.get("effects", []) or [])
    return {"status": "ok", "event_id": event.get("id"), "selected_branch": branch.get("id")}
