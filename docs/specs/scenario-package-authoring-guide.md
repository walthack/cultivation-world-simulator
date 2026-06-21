# CWS Scenario Package — Authoring & Import Guide

**Audience:** anyone (human author, agent, or a v2 novel→scenario generator) producing an importable scenario.

A **scenario package** is a self-contained, swappable data plugin. The engine is fixed; a package supplies all the world + plot content as JSON. You can author, zip, import, and play one without touching engine code. This guide is the contract: produce a package that matches it and it will import + run, exercising the full L1–L4 narrative stack.

---

## 1. Package structure

A package is a **zip** containing one top-level directory named exactly `<scenario_id>` with **two required files**:

```
<scenario_id>.zip
└── <scenario_id>/
    ├── scenario.json     # world definition (required)
    └── timeline.json     # plot events (required)
```

- `scenario_id` must be snake_case and match the directory name.
- The package **references** a `world_preset` by id (presets live in `config/presets/<preset_id>/`); presets are not embedded in the package.
- An optional `fingerprint` (sha256) in scenario.json lets the importer mark the package `verified` / `modified` / `unsigned`.

**Import:** `import_scenario_zip(zip_bytes)` → inspect → extract → `validate_scenario_dir` (full schema validation) → fingerprint check → install under the data root → enable. Then `load(scenario_id)` resolves it (bundled `config/scenarios` takes precedence, data-root installs are the fallback). A package that fails validation is rejected with a precise `path` to the bad field.

`schema_version` appears in **both** files; supported: `0.1 0.2 1.0 1.1 1.2`. **Author new packages at `1.2`** (newest; gets full reference validation).

---

## 2. `scenario.json` — world definition

```jsonc
{
  "schema_version": "1.2",
  "scenario_id": "my_scenario",        // snake_case, == dir name
  "title": "…",                        // non-empty
  "version": "1.0.0",                  // non-empty
  "author": "…",                       // optional
  "description": "…",                  // optional
  "world_preset": { "preset_id": "liuchao" },   // must resolve to config/presets/<id>
  "generation_sources": {              // where each content pool comes from: "scenario" | "default"
    "regions": "scenario", "dynasties": "scenario", "sects": "scenario",
    "npc_names": "scenario", "personas": "scenario", "weapons": "scenario",
    "techniques": "scenario", "roots": "scenario", "relations": "scenario",
    "initial_events": "scenario", "fallback_to_default": false
  },
  "world_background": "…",             // free narrative text (clipped + fenced before any LLM use)
  "initial_state": {
    "year": 1, "month": 1,
    "generation_profile": { … },       // progression axes (see §6)
    "avatars": [ { "id": "cheng-zongyang", "surname": "程", "given_name": "宗扬",
                   "gender": "男", "age": 25, "sect_id": null,
                   "location_region_id": "grassland_battlefield",
                   "realm": "ZHU_JI", "stage": "EARLY_STAGE", "level": 1,
                   "backstory": "…", "persona_traits": [ … ] }, … ],
    "sects": [ … ],
    "relationships": [ { "a": "cheng-zongyang", "b": "wang-zhe", "value": 30 }, … ],
    "world_flags": { "some_flag": true }
  },

  "backbone": {                        // OPTIONAL — the L4 Narrative Director's hard constitution (§5)
    "prohibited_predicates": [ { "world_flag": { "flag": "demon_wins", "value": true } } ],
    "irreversible_facts":    [ { "world_flag": { "flag": "wang_zhe_dead", "value": true } } ]
  }
}
```

Notes:
- Every `id` referenced (region/dynasty/sect/avatar/root/technique/weapon) must exist in the preset or in this package's pools. At schema `1.2` these refs are validated — a dangling id is a hard error.
- `world_flags` initial values are the starting flag set.

---

## 3. `timeline.json` — plot events

```jsonc
{
  "schema_version": "1.2",
  "events": [ { …event… }, … ]
}
```

### Event — common fields
```jsonc
{
  "id": "liuchao-opening",             // unique within the timeline
  "type": "main",                      // see event types below
  "trigger": {
    "year": 1, "month": 1,             // exact-month scheduling
    "condition": { "always": {} }      // condition DSL (§4); fires only if true that month
  },
  "name": "穿越落地",
  "description": "…",                  // authored narrative; clipped+fenced before any LLM use
  "effects": [ { "type": "set_flag", "flag": "liuchao_opening_seen" } ],  // §4 effects

  // optional gating / structure:
  "requires_events": ["some-earlier-id"],   // only eligible after these fired
  "blocks_events":   ["some-other-id"],     // suppresses those once this fires
  "dynasty_id": "qin",                       // if set, trigger MUST carry at_region_id in preset regions
  "at_region_id": "grassland_battlefield"
}
```

### Event types (`type`)
| type | behavior |
|---|---|
| `main` / `side_event` / `sect_event` / `world_event` | apply the event's top-level `effects` |
| `branch` | selector: evaluate each `branches[].condition` in order, apply the FIRST match's effects, else `default_branch` (§5 L1) |
| `character_introduction` | spawn an authored NPC |
| `relation_change` / `relationship_event` | shorthand: `{a,b,delta}` adjusts a relation |
| `ending` | terminal beat |

### Optional narrative-stack fields (the L1–L4 features)
- **L1 branching (v1.6):** `branch` event with `"branches": [{ "id", "condition", "effects" }], "default_branch": "<branch id>"`; and storyline tagging: any event may carry `"storyline": "<line_id>"` and only fires while that line is active. A line is activated by the `activate_storyline` effect. One-way mutual exclusion is engine-managed; load-time validation rejects a storyline no `activate_storyline` can reach.
- **L2 narrative fill (v1.7):** `"narrative_fill": true` opts the event into LLM-generated narration (display-only; never affects mechanics) — you MUST also provide `"narration_fallback": "…"` (used with no LLM key / on failure).
- **L3 anchors (v1.8):** `"anchor": true` marks an event as part of the deterministic backbone the LLM may not cross between.
- **L4 mandatory (v1.9):** `"mandatory": true` (requires `"anchor": true`) marks a milestone the Narrative Director must always keep reachable; the director is rejected if a proposal would starve it.

---

## 4. Condition DSL & effects

**Condition** = a single-key object, either an operator or a predicate:
- Operators: `{ "all": [ … ] }`, `{ "any": [ … ] }`, `{ "not": { … } }`.
- Predicates (each `{ "<name>": { …params… } }`):
  `always, world_flag, world_year, world_month, var_equals, event_triggered, random_chance, player_realm, player_sect, player_has_skill, player_stat, player_relation, controlled_avatar_is, npc_alive, npc_realm, npc_relation`.
  Examples: `{"world_flag":{"flag":"x","value":true}}`, `{"npc_relation":{"a":"id1","b":"id2","value":50,"op":">="}}`, `{"var_equals":{"name":"phase","value":"open"}}`.

**Effects** (`effects: [ { "type": …, … } ]`), canonical types:
`set_flag, clear_flag, set_var, set_stat, gain_stat, lose_stat, gain_skill, lose_skill, gain_item, lose_item, relation_change, npc_set_relation, npc_join, npc_leave, npc_die, npc_set_realm, npc_spawn, activate_storyline, world_event_trigger, economy_event`.

Placeholders: `{controlled_avatar}` in effect string values is substituted with the controlled avatar id at apply time.

---

## 5. The L4 backbone (driving the Narrative Director)

To make a package that the autonomous **Narrative Director** (L4) drives, declare a `backbone` in scenario.json **and** mark `mandatory` anchors in the timeline:

- `prohibited_predicates`: world states that must NEVER become true. The director's proposals are rejected if applying them would satisfy any.
- `irreversible_facts`: states that, once true, must NEVER be reversed (e.g. a death/faction-fall flag). The director can't undo a held one (no resurrection).
- **Both must be DETERMINISTIC builtin predicates** — the allow-list is every predicate in §4 **except `random_chance`** (and no mod predicates). A hard gate decided by one evaluation can't be a coin flip; non-deterministic backbone predicates are rejected at load.
- `mandatory` anchors (timeline events with `anchor:true, mandatory:true`) are the milestones the director must keep reachable. Author them with **modellable** conditions (flag/var/relation/event_triggered) so the reachability gate can prove them; conditions reading un-modellable state (e.g. npc state, random_chance) make the director fail-closed (conservatively reject) near that anchor.

The director itself is a runtime LLM component — you do **not** author director events. You author the **bounds** (backbone + mandatory anchors); the director generates direction-conforming beats within them, and every proposal passes backbone + forward-replay reachability gates before applying. With no LLM key the director is silent and the mandatory anchors still fire (scripted skeleton stays playable).

---

## 6. Progression profile

`initial_state.generation_profile` re-points the cultivation/advancement axes to the scenario's own system (e.g. liuchao uses 太乙九境 + 身份官职 + 名望 instead of default 修真 realms). Use it so NPC goals and progression text are scenario-flavored rather than generic. (See `src/scenario/progression_profile.py` for the resolved axes contract.)

---

## 7. Minimal worked example (an L4-ready package)

`my_scenario/scenario.json`
```jsonc
{
  "schema_version": "1.2", "scenario_id": "my_scenario", "title": "Demo", "version": "1.0.0",
  "world_preset": { "preset_id": "liuchao" },
  "generation_sources": { "fallback_to_default": true },
  "initial_state": {
    "year": 1, "month": 1,
    "avatars": [ { "id": "hero", "surname": "程", "given_name": "宗扬", "gender": "男", "age": 25, "realm": "ZHU_JI" } ],
    "world_flags": {}
  },
  "backbone": {
    "prohibited_predicates": [ { "world_flag": { "flag": "demon_wins", "value": true } } ],
    "irreversible_facts":    [ { "world_flag": { "flag": "mentor_dead", "value": true } } ]
  }
}
```

`my_scenario/timeline.json`
```jsonc
{
  "schema_version": "1.2",
  "events": [
    { "id": "m_open", "type": "side_event", "anchor": true, "mandatory": true,
      "trigger": { "year": 1, "month": 1, "condition": { "always": {} } },
      "name": "开篇", "narration_fallback": "故事开始。", "narrative_fill": true,
      "effects": [] },
    { "id": "m_fall", "type": "side_event", "anchor": true, "mandatory": true,
      "trigger": { "year": 5, "month": 1, "condition": { "always": {} } },
      "name": "恩师之死", "effects": [ { "type": "set_flag", "flag": "mentor_dead" } ] }
  ]
}
```
Here the director may invent beats over the 5 years between the anchors (set flags, nudge relations, set vars, introduce minor NPCs, fire atomic local crises) — but can never set `demon_wins`, never clear `mentor_dead` after y5, and never make `m_open`/`m_fall` unreachable.

---

## 8. Validation & gotchas
- Validate before shipping: importing runs `validate_scenario_dir`; a bad field raises with its `path`. Author at `1.2` for full reference validation.
- `mandatory: true` requires `anchor: true`.
- `backbone` predicates must be deterministic builtins (no `random_chance`/mod).
- A `dynasty_id` event MUST have `trigger.at_region_id` in the preset's regions.
- `narrative_fill: true` requires `narration_fallback`.
- Generated narration is display-only — never write it into `effects`/`condition`/relation logic.
- Reference ids (region/dynasty/sect/avatar/root/technique/weapon) must resolve in the preset or package pools.
- Known limitation: a plain event `set_flag` effect's flag is currently not persisted across save/reload (a pre-existing engine gap, on the backlog); the director's own flag/relation/var/npc writes ARE persisted.

---

## 9. For a v2 novel→scenario generator
Target this exact format. The novel→package pipeline should emit: a `world_preset` (or reference an existing one) + `scenario.json` (factions/characters/geography/relations as initial_state + generation_sources pools + a `backbone` capturing the story's thesis-level prohibited outcomes and irreversible facts) + `timeline.json` (the novel's arc as anchored events, with `mandatory` on the load-bearing plot milestones, `branch`/`storyline` for divergences, `narrative_fill` on beats that want LLM prose). Encode mature/dark source themes as structural facts faithfully; the format carries metadata, not prose, so fidelity to the source's adult nature does not require explicit text.
