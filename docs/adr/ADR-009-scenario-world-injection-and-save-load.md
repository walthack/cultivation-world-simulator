# ADR-009: Scenario World Injection and Save Load

## Status

Accepted for Milestone C.

## Context

Stage 2d and Milestone B attach `ScriptedScenarioState` to the live world and expose read-only scenario visibility. Scenario authoring data still lives mostly in the scripted shadow state: initial avatars are not real `Avatar` instances, authored relationships are not visible to social systems, and scenario runtime state is not persisted through save/load.

Milestone C closes that gap without changing dispatcher semantics, frontend surfaces, mutation APIs, or the `--scenario` flag. The scenario timeline remains authored static data, while the mutable runtime state must become part of the save file.

## Decision

Inject scenario avatars after the normal init-flow random NPC generation. Scenario avatars are additive: the requested random NPC population is kept, and authored characters are registered afterward through `world.avatar_manager.register_avatar(..., is_newly_born=True)`.

Scenario avatar IDs are honored verbatim. The authored ID, such as `cheng-zongyang`, becomes the `Avatar.id` used by `AvatarManager`, relation maps, roleplay entry points, and save data.

Scenario reference fields are strict. `sect_id`, `persona_traits`, `goldfinger_id`, `realm`, and `stage` are validated against the active preset. A bad reference fails initialization with the offending field and avatar ID instead of silently falling back to random/default content.

Scenario relationships are applied bidirectionally. Each authored `{a, b, value}` writes `RelationState(friendliness=value)` in both `a.relations[b]` and `b.relations[a]`, so existing social systems can read either direction without knowing the scenario source.

Save files persist only the mutable scripted scenario runtime:

```json
{
  "scenario_id": "liuchao",
  "state": {},
  "triggered_events": []
}
```

The timeline is not saved. Loading re-reads the scenario file through `scenario_loader.load(scenario_id)` so authored static data stays canonical.

Loading a scenario save requires the current boot scenario ID to match the save's `scenario_id`. A Liuchao save loaded while booted with Sanguo, or with no scenario flag, is refused with a message telling the operator to restart with the saved scenario ID. Legacy saves without `scripted_scenario` keep the existing load path and do not fabricate scenario state.

## Edge Cases

| Case | Behavior |
|---|---|
| Boot `--scenario liuchao` and load Liuchao save | Load succeeds and restores `state` plus `triggered_events`. |
| Boot `--scenario sanguo` and load Liuchao save | Load is refused with an explicit scenario mismatch error. |
| Boot no scenario and load Liuchao save | Load is refused and asks for `--scenario liuchao`. |
| Boot `--scenario liuchao` and load no-scenario save | Load succeeds through the legacy path; no `scripted_scenario` key is required. |
| Boot no scenario and load no-scenario save | Load succeeds with `world.scripted_scenario` remaining absent. |
| Scenario avatar references missing goldfinger/persona/sect | Initialization fails at the bad field; no silent default is applied. |
| Scenario relation references missing avatar | Injection fails with the bad relationship entry. |
| Save mid-scenario then load | Triggered event IDs are restored so already-fired events do not re-fire. |

## Consequences

Scenario characters now appear in the same avatar manager as generated NPCs and can participate in existing avatar detail, roleplay, action, relation, and save/load flows.

Default no-scenario initialization remains unchanged because avatar and relation injection only runs when `world.scripted_scenario` and a resolved active scenario are both present.

The save format stays clean for legacy/default games because the top-level `scripted_scenario` key is omitted when no scenario is active.

Scenario-only persona and goldfinger keys are materialized as lightweight registry objects so the existing avatar serializer can persist numeric references without a parallel save path.

## Alternatives

One alternative was to inject scenario avatars inside `ScenarioInjectedWorld.create_with_db`. That was rejected because world creation happens before the normal random NPC generation phase, which would make random generation see scenario avatars as pre-existing population and would blur Milestone C's additive timing rule.

Another alternative was to store scenario timelines in save files. That was rejected because timelines are authored static data and should come from the scenario package on load, while only runtime state and triggered event IDs are mutable.

A third alternative was to silently load scenario saves under a different or missing boot scenario by trusting the save file. That was rejected because it would mix runtime state with the wrong active scenario metadata, preset references, and timeline.
