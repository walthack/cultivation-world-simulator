# ADR: Scenario Single Choice Audit D6

Date: 2026-06-02

## Status

Ready for Hassan review. Do not proceed to D7 until reviewed.

## Context

Schema v0.1 requires `main` and `world_event` scenario events to push stable choices through the existing choice surface. The schema also requires pending choice persistence later: `{event_id, choices, set_at_month, timeout_month}`.

Current CWS implementation:

- Core choice models live in `src/systems/single_choice/models.py`.
- Choice scenarios implement `SingleChoiceScenario.build_request()` and `apply_decision()`.
- `resolve_single_choice()` already supports LLM, fallback, and player roleplay choice via `roleplay_service.begin_roleplay_choice()`.
- The current roleplay choice wait is runtime-only and future-based. It is not yet persisted into save/load.
- Existing business implementations include item exchange and sect recruitment.

## Option A: Reuse Existing `single_choice`

Approach:

- Add a scenario-specific adapter class, e.g. `ScenarioEventChoiceScenario`.
- Convert Schema v0.1 `choices` into `SingleChoiceOption`.
- Use `SingleChoiceRequest.context` for `scenario_id`, `event_id`, `default_outcome`, and effect metadata.
- Let `resolve_single_choice()` keep choosing between player roleplay, LLM, and fallback.
- Record final selected choice into `scenario_runtime.event_outcomes`.

Pros:

- Reuses the already-integrated roleplay choice path.
- Avoids a second pending-choice UI/API model.
- Keeps `main` / `world_event` consistent with existing finite decisions.
- Lower D7-D10 risk because only an adapter is needed.

Cons:

- Current `SingleChoiceRequest` stores `avatar` object, not explicit `avatar_id`; persistence needs a serializable companion state.
- Current pending choice in roleplay runtime is not save/load ready.
- `resolve_single_choice()` is immediate from the scenario engine perspective; persisted timeout behavior must be layered around it.

Estimate:

- D8 scenario choice adapter: 0.5 day.
- D10 roleplay path integration: 0.5-1 day.
- Save/load pending choice persistence: 1-2 days, likely after MVP unless D10 requires save/load.

## Option B: Fork And Modify As `scenario_choice`

Approach:

- Create separate scenario choice models, pending state, router payloads, and frontend display contract.
- Keep existing `single_choice` untouched.

Pros:

- Full control over Schema v0.1 persistence shape.
- Avoids changing assumptions in existing item/sect choice flows.

Cons:

- Duplicates choice models, normalization, fallback, roleplay wait, and UI payload logic.
- Higher chance of divergent behavior between scenario and roleplay finite decisions.
- More code to test before D10, with no clear benefit for MVP.

Estimate:

- New backend choice model/resolver: 1-2 days.
- Roleplay/API/frontend alignment: 2-4 days.
- Tests and migration risk: 1-2 days.

## Recommendation

Reuse existing `single_choice` and add a thin scenario adapter.

D7-D10 should not fork the choice system. The scenario engine should model event dispatch/effects separately, then call the existing choice resolver only when an event needs player/LLM/fallback selection.

For Stage 1 MVP, persistence gaps should be recorded but not solved unless D10 explicitly needs save/load during a pending choice. The stable Schema v0.1 choice fields should be preserved in `scenario_runtime`, while the immediate runtime flow can reuse the current `SingleChoiceDecision`.

## Hassan Review Questions

1. Confirm reuse of `single_choice` with a scenario adapter instead of creating `scenario_choice`.
2. Confirm whether Stage 1 D10 must include pending-choice save/load persistence, or whether runtime-only pending choice is acceptable for MVP.
3. Confirm fallback behavior when no avatar is currently controlled: use `default_outcome` if present, otherwise existing `FallbackPolicy.FIRST_OPTION`.
