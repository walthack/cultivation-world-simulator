from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.systems.single_choice import (
    ChoiceSource,
    FallbackMode,
    FallbackPolicy,
    SingleChoiceDecision,
    SingleChoiceOption,
    SingleChoiceOutcome,
    SingleChoiceRequest,
)
from src.systems.single_choice.engine import resolve_single_choice

from ..effect_applier import apply_effects
from ..state_access import get_player, get_scenario_runtime, get_value


@dataclass(slots=True)
class ScenarioChoiceOutcome(SingleChoiceOutcome):
    event_id: str
    choice_id: str


class ScenarioEventChoiceScenario:
    def __init__(self, *, state: Any, event: dict[str, Any]):
        self.state = state
        self.event = event

    def build_request(self) -> SingleChoiceRequest:
        player = get_player(self.state)
        options = [
            SingleChoiceOption(
                key=str(choice.get("id") or choice.get("key")),
                title=str(choice.get("title") or choice.get("text") or choice.get("id") or choice.get("key")),
                description=str(choice.get("description") or choice.get("text") or ""),
            )
            for choice in self.event.get("choices", []) or []
        ]
        default_outcome = self.event.get("default_outcome")
        fallback = (
            FallbackPolicy(FallbackMode.PREFERRED_KEY, preferred_key=str(default_outcome))
            if default_outcome
            else FallbackPolicy(FallbackMode.FIRST_OPTION)
        )
        return SingleChoiceRequest(
            task_name="single_choice",
            template_path=Path("templates/single_choice.txt"),
            avatar=player,
            situation=str(self.event.get("description") or self.event.get("name") or ""),
            options=options,
            fallback_policy=fallback,
            request_id=f"scenario-{self.event.get('id')}",
            title=str(self.event.get("name") or self.event.get("id") or "Scenario event"),
            description=str(self.event.get("description") or ""),
            context={
                "scenario_event_id": self.event.get("id"),
                "default_outcome": default_outcome,
            },
        )

    async def apply_decision(self, decision: SingleChoiceDecision) -> ScenarioChoiceOutcome:
        choice_id = str(decision.selected_key)
        for choice in self.event.get("choices", []) or []:
            if str(choice.get("id") or choice.get("key")) == choice_id:
                effects = choice.get("effects", self.event.get("effects", []))
                apply_effects(self.state, effects or [])
                break
        runtime = get_scenario_runtime(self.state)
        runtime.setdefault("event_outcomes", {})[str(self.event.get("id"))] = {
            "choice_id": choice_id,
            "by_player": decision.source == ChoiceSource.PLAYER_ROLEPLAY,
        }
        return ScenarioChoiceOutcome(
            decision=decision,
            result_text=str(self.event.get("outcome_text") or ""),
            event_id=str(self.event.get("id")),
            choice_id=choice_id,
        )


def _controlled_avatar_id(state: Any) -> str:
    runtime = get_scenario_runtime(state)
    if runtime.get("controlled_avatar_id"):
        return str(runtime.get("controlled_avatar_id"))
    roleplay = get_value(state, "roleplay_session", {}) or {}
    return str(get_value(roleplay, "controlled_avatar_id", "") or "")


async def resolve_scenario_event_choice(state: Any, event: dict[str, Any]) -> ScenarioChoiceOutcome:
    scenario = ScenarioEventChoiceScenario(state=state, event=event)
    player = get_player(state)
    controlled_id = _controlled_avatar_id(state)
    player_id = str(get_value(player, "id", "") or "")
    if controlled_id and player_id and controlled_id == player_id and hasattr(player, "world"):
        return await resolve_single_choice(scenario)

    request = scenario.build_request()
    selected = str(event.get("default_outcome") or request.options[0].key)
    decision = SingleChoiceDecision(
        selected_key=selected,
        thinking="",
        source=ChoiceSource.FALLBACK,
        raw_response=None,
        used_fallback=True,
        fallback_reason="scenario_default_outcome" if event.get("default_outcome") else "first_option",
    )
    return await scenario.apply_decision(decision)


async def handle_main_event(state: Any, event: dict[str, Any]) -> ScenarioChoiceOutcome:
    if event.get("choices"):
        return await resolve_scenario_event_choice(state, event)
    apply_effects(state, event.get("effects", []) or [])
    decision = SingleChoiceDecision("", "", ChoiceSource.FALLBACK, None, True, "no_choices")
    return ScenarioChoiceOutcome(decision, str(event.get("outcome_text") or ""), str(event.get("id")), "")
