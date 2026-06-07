# Spec: v1.2 — Scenario Generation Source Control

**Status**: draft (Hassan, 2026-06-07)
**Type**: feature — completes the "import a pre-defined world" promise.
**Version**: v1.2 (off `main` @ `v1.1.0-final`)
**Owner**: codex (implementation + tests + ADR); Hassan reviews spec only
**Branch**: `feat/scenario-generation-source-control-v1.2`
**ADR**: ADR-025 (new — supersedes nothing)
**Tag target**: `v1.2.0-final`

---

## 1. Background

- **v1.0**: scenario engine ships, metadata + timeline + scripted
  avatars/sects/relations injected.
- **v1.0.1**: scenario avatars no longer stack at (0,0).
- **v1.1**: scenario controls *quantity* of default random generation
  (random_npc_count / random_sect_count / use_scripted_only) and
  *position* of scripted avatars (pos / region_id).

**Diagnosis after v1.1 (master 2026-06-07)**: scenarios still don't
fully "import a pre-defined world." Even with v1.1, the *random* NPCs /
sects that fill out the world are drawn from CWS default pools —
default names, default personas, default weapons, default techniques.
A 六朝 game still has random NPCs named like generic cultivators,
wielding generic weapons. The scripted backbone is right; the
*procedurally filled rest* is not.

The fix: let the scenario **package** dictate the source pools.

## 2. What v1.2 must deliver (master's spec 2026-06-07)

The scenario package defines or selects the source pools for:

1. dynasties / factions
2. regions (map)
3. sects
4. NPC name list
5. NPC persona pool
6. weapons (神兵)
7. roots (灵根)
8. techniques (功法)
9. relations
10. initial events

CWS default pools are used only in **two** cases:
- no scenario (sandbox mode)
- scenario explicitly sets `fallback_to_default: true`

Master's proposed schema:

```jsonc
"generation_sources": {
  "regions": "scenario",
  "dynasties": "scenario",
  "sects": "scenario",
  "npc_names": "scenario",
  "personas": "scenario",
  "weapons": "scenario",
  "techniques": "scenario",
  "roots": "scenario",
  "relations": "scenario",
  "initial_events": "scenario",
  "fallback_to_default": false
}
```

## 3. Preset infra already exists — partial good news

`config/presets/` already houses three presets — `default`, `liuchao`,
`sanguo` — each a directory of JSON pool files. `scenario.json` already
has a `world_preset.preset_id` field that wires a scenario to its
preset. Several generators (e.g. `src/utils/name_generator.py`) already
read `get_active_preset_id()`.

**What's not done**:
- `liuchao` preset is **missing 4 of the 13** pool files: `races.json`,
  `roots.json`, `techniques.json`, `weapons.json`. So weapons /
  techniques / roots / races generation today silently falls back to
  default even when scenario is `liuchao`.
- `sanguo` preset likely has the same gaps (codex to audit and report
  in PR).
- No `generation_sources` field in `scenario.json` schema — the choice
  is "use preset" or "use default" is implicit (preset wins if file
  present, default if missing) with no error surface.
- No explicit `fallback_to_default` flag — every missing preset file
  silently falls back. Authors can't say "no, fail loud if my pool
  isn't there."

## 4. Schema — `scenario.json` schema_version 1.2

Add `generation_sources` to top-level (or under `initial_state`,
matching `generation_profile` from v1.1 — codex picks the placement
that reads best, and documents it):

```jsonc
{
  "schema_version": "1.2",
  "scenario_id": "liuchao",
  // ... existing v1.1 fields preserved ...
  "world_preset": { "preset_id": "liuchao" },

  "generation_sources": {
    "regions":         "scenario",
    "dynasties":       "scenario",
    "sects":           "scenario",
    "npc_names":       "scenario",
    "personas":        "scenario",
    "weapons":         "scenario",
    "techniques":      "scenario",
    "roots":           "scenario",
    "relations":       "scenario",
    "initial_events":  "scenario",
    "fallback_to_default": false
  }
}
```

- Each source key accepts `"scenario"` or `"default"`. Other values →
  `ScenarioValidationError`.
- `fallback_to_default: bool`. Default `false` if `generation_sources`
  block is present at all. If `generation_sources` is omitted →
  behavior identical to v1.1 (everything implicit-default).
- Schema 0.1 / 1.0 / 1.1 scenarios continue to load and behave exactly
  as before. **No regressions for existing fork users.**

## 5. Behavior

### 5.1 Source resolver — fail-fast at load (master 2026-06-07)

Master's hard rule: **when `fallback_to_default = false`, missing
required generation source must fail fast during scenario _load_, not
at world-init time.** Authors learn about gaps immediately, not after
they hit a runtime path that happens to need the missing pool.

So validation is two-phase:

**Phase A — `scenario_loader.load(scenario_id)`**: as part of normal
load, after reading `generation_sources`:

- For each key set to `"scenario"`:
  - check `config/presets/<preset_id>/<kind-to-file-map>.json` exists
    on disk
  - if missing AND `fallback_to_default` is false → raise
    `ScenarioValidationError` with concrete message: `"Scenario
    'liuchao' declares generation_sources.weapons='scenario' but
    config/presets/liuchao/weapons.json is missing. Either add the
    file, set generation_sources.weapons='default', or set
    fallback_to_default: true."`

The kind-to-file map is part of this spec — codex defines it (a small
constant dict) and documents it. Initial mapping:

```python
KIND_TO_PRESET_FILE = {
    "regions":         "regions.json",
    "dynasties":       "dynasties.json",
    "sects":           "sects.json",
    "npc_names":       "name_templates.json",
    "personas":        "personas.json",
    "weapons":         "weapons.json",
    "techniques":      "techniques.json",
    "roots":           "roots.json",
    "relations":       None,           # relations are scenario-only;
                                        # ignore in load-time check
    "initial_events":  None,           # likewise
}
```

For keys with `None` mapping (relations / initial_events) the load
check is skipped — those don't live in preset files.

**Phase B — runtime `resolve_source(kind, *, scenario, preset_loader)
-> SourceHandle`** (used by generators):

1. If no scenario active → return `default` source handle.
2. Read `generation_sources[kind]` from scenario.
   - `"scenario"`: load from `config/presets/<preset_id>/<kind>.json`
     (guaranteed present by Phase A unless `fallback_to_default` is
     true).
     - present → return that handle
     - missing AND `fallback_to_default` is true → return `default`
       (Phase A wouldn't have raised in this case)
     - missing AND `fallback_to_default` is false → defensive raise
       `ScenarioSourceMissingError` (should not happen if Phase A
       did its job; raise loudly so codex/master notices the contract
       drift)
   - `"default"`: return `default` source handle.
3. If `generation_sources` block omitted entirely → v1.1 implicit
   behavior (every kind → default).

### 5.2 Generators read via resolver

The following generators must route through the resolver. Each is a
small refactor — find the call site, swap the hard `default` lookup for
`resolve_source(kind, ...)`:

- random NPC names → `npc_names`
- random NPC personas → `personas`
- random NPC weapons → `weapons`
- random NPC techniques → `techniques`
- random NPC roots → `roots`
- random NPC races → `roots` (Race fields share the source if codex
  finds race lookup; otherwise track separately and update spec)
- random sect spawn → `sects`
- world map / region setup → `regions`
- dynasty assignment → `dynasties`
- relation seeding → `relations`
- initial event seeding → `initial_events`

If a generator can't be cleanly routed because the lookup is global /
deeply embedded, document the gap and ship the rest — incremental is
fine, the priority order is **names → personas → weapons → techniques**
(the four most visible to players).

### 5.3 Sandbox unchanged

When no scenario is active, no scenario lookups happen. Every generator
keeps reading default pools as it does today. Verify with a no-scenario
boot smoke + a Layer 1 test (`test_no_scenario_uses_default_sources`).

## 6. Preset content gaps — master picked option (a) 2026-06-07

Master's call: codex writes minimum viable stubs. liuchao does **not**
fall back to default; the validation power of v1.2 requires that
`liuchao` `generation_sources.weapons="scenario"` succeeds because
liuchao actually owns a `weapons.json`. Stubs may be thin (3-5 entries
per file) but they must be **scenario-owned source**, not a fallback.

`config/presets/liuchao/` currently has 9 of 13 pool files. To honor
`generation_sources.* = "scenario"`, liuchao needs to either:

(a) **provide** the four missing files (`races`, `roots`, `techniques`,
    `weapons`) with 六朝-flavored content, OR
(b) **mark** those keys `"default"` in `generation_sources`, OR
(c) **set** `fallback_to_default: true` to silently fall through.

Recommendation: v1.2 ships the **mechanism + a minimal viable content
seed** for liuchao (3-5 entries per missing file, just enough to prove
the wiring; master / future content PRs expand). Same for sanguo. This
keeps the PR focused on engineering, not content authorship.

Concretely, codex creates:
- `config/presets/liuchao/races.json` — at minimum 3 races (人族 is
  guaranteed; ideally 2-3 historically motivated species like 妖族 /
  鬼族 from 六朝 literature)
- `config/presets/liuchao/roots.json` — at minimum 5 root types (codex
  can mirror default 5 elements 金木水火土; master may rename in PR
  review)
- `config/presets/liuchao/techniques.json` — at minimum 3 techniques
  with 六朝-flavored names
- `config/presets/liuchao/weapons.json` — at minimum 3 weapons with
  六朝-flavored names

(And the same minimum for `sanguo` with 三国 flavor.)

**Codex does NOT invent rich narrative content**. Names should be
neutral / generic. Master can rename / expand in PR review or in a
follow-up content PR.

If master prefers, the content stubs can be deferred and v1.2 simply
ships with liuchao/sanguo setting `fallback_to_default: true` — the
mechanism works, content fills in later. Codex should ask in the PR
report which path master wants.

## 7. Validation — `scenario_loader.py`

- `generation_sources` is dict → ok; missing keys treated as omission
  (no error); unknown keys (typos like `"npcname"`) → warning logged,
  not error (forward compat).
- Each value must be `"scenario"` / `"default"` → else
  `ScenarioValidationError`.
- `fallback_to_default` must be bool if present.
- Schema_version `1.2` accepted; loader still accepts 0.1 / 1.0 / 1.1.

## 8. Tests

### Layer 1 — backend pytest (new file `tests/test_generation_source_control.py`)

**Positive**
- `test_no_scenario_uses_default_sources` — start a no-scenario game,
  assert every generator hits default
- `test_scenario_all_sources_scenario_with_fallback_false_loads_clean`
  — liuchao schema 1.2 with all sources=scenario, all preset files
  present → loads without error
- `test_scenario_source_scenario_hits_preset_pool` — for a key with a
  preset file (e.g. `personas` for liuchao), random gen pulls from
  liuchao preset persona keys (assert names / IDs from preset set)
- `test_scenario_source_default_overrides_to_default_pool` —
  `personas: "default"` even though liuchao preset has personas → gen
  uses default pool
- `test_fallback_to_default_true_silently_uses_default_when_preset_missing`
  — `weapons: "scenario"` + `fallback_to_default: true` + no
  `weapons.json` in preset → uses default, no error
- `test_generation_sources_omitted_preserves_v1_1_behavior` —
  scenario without `generation_sources` block behaves like v1.1

**Negative (Layer 5)**
- `test_loader_rejects_invalid_source_value` — `sects: "wrong_string"`
  → `ScenarioValidationError`
- `test_loader_rejects_non_bool_fallback_to_default` — fallback flag
  set to a string → `ScenarioValidationError`
- `test_world_init_raises_when_preset_missing_and_fallback_false` —
  `weapons: "scenario"`, fallback false, no preset weapons.json →
  `ScenarioSourceMissingError` at init time with clear message

### Layer 4A — frontend Playwright E2E

Update `web/e2e/layer4-scenario-engine.spec.ts`:

- Add Step 11: start a `--scenario=liuchao` game, query random NPC
  names, assert at least one matches `liuchao` `name_templates`
  pattern (and does NOT match default's distinctive surnames).
- Add Step 12: hot-swap to `sanguo`, query random NPC names, assert
  the pattern flips to sanguo's. (Only if hot-swap + name regen works
  with current architecture; if not, log gap and skip.)

### Layer 5 — milestone audit

Above 3 negatives + the schema validations satisfy
[[milestone-pr-stack]] rule.

## 9. ADR-025

`docs/adr/ADR-025-scenario-generation-source-control.md`:

- **Context**: v1.1 controls generation *count* and per-avatar *position*
  but procedurally generated NPCs / sects / dynasties are still drawn
  from CWS default pools. Master's playtest 2026-06-07 surfaced this as
  the next bottleneck for "import a pre-defined world."
- **Decision**: Introduce `generation_sources` block in scenario.json
  (schema_version 1.2). Per-source-type control (`"scenario"` /
  `"default"`); global `fallback_to_default` flag for missing preset
  files. Preset infra (already in `config/presets/<id>/`) becomes the
  canonical scenario-flavored pool source; default pool used only in
  sandbox mode or with explicit fallback.
- **Alternatives considered**:
  - Single all-or-nothing flag (e.g. `use_scenario_sources: true`) —
    too blunt; some scenarios may want scenario sects + default names,
    or default weapons + scenario techniques.
  - Embed pool data directly in scenario.json (denormalized) — bloats
    the manifest, breaks the preset abstraction, makes content reuse
    across scenarios harder.
  - Require *every* preset to be complete (13/13 files) — too heavy a
    burden for new scenario authors; fallback flag preserves the
    "minimum viable scenario" floor.
- **Consequences**:
  - Existing scenarios at schema_version 0.1 / 1.0 / 1.1 keep working
    (no field → v1.1 implicit-default behavior).
  - `liuchao` / `sanguo` presets will need 4 missing pool files
    eventually; v1.2 ships minimal stubs, content expansion happens
    in follow-up PRs.
  - Sandbox mode (no scenario) unchanged.

## 10. Acceptance criteria (codex: PR ready when all hold)

- [ ] `scenario_loader` accepts schema_version 1.2 with
  `generation_sources`; validates source values + bool flag; still
  accepts 0.1 / 1.0 / 1.1
- [ ] `resolve_source` implemented and tested as standalone unit
- [ ] At least 4 generators (names, personas, weapons, techniques)
  routed via resolver; document any that couldn't be routed
- [ ] `liuchao` and `sanguo` presets gain the 4 missing pool files
  with minimum viable stubs (or, if master agrees, set
  `fallback_to_default: true` and skip stubs)
- [ ] `liuchao` / `sanguo` scenario.json upgraded to schema_version
  1.2 with `generation_sources` block matching master's example
- [ ] 6 positive + 3 negative backend tests added & green
- [ ] Layer 4A E2E Step 11 (+ 12 if hot-swap supports) added & green
  (or skipped with explicit reason if architecture doesn't allow yet)
- [ ] ADR-025 written
- [ ] No-scenario game smoke: random NPCs / sects / dynasties pulled
  from default pool, no scenario code path fires (v1.0.1 / v1.1 parity)
- [ ] Full v1.1 test suite still passing (1712 + new = ~1721)
- [ ] `docs/release-verification-report.md` updated with v1.2 row
- [ ] **Master's fail-fast rule (2026-06-07)**: when
  `fallback_to_default=false`, missing required generation source
  fails fast during scenario *load* (not deferred to world init). At
  least one negative test asserts the load-time error path and the
  error message identifies (a) the scenario id, (b) the missing
  source kind, (c) the expected preset file path.

## 11. Out of scope

- Rich narrative content for liuchao/sanguo preset pools. The PR
  ships *mechanism* + *minimum stubs*. Content expansion happens in
  follow-up content PRs (likely master-authored or codex with master
  curating).
- Wizard UI for editing `generation_sources` in `ScenarioWizardModal`.
  Optional follow-up.
- Per-scenario / per-region NPC distribution (e.g. "liuchao NPCs in
  region X, sanguo NPCs in region Y") — out of scope; v1.3+ candidate.

---

## Codex dispatch hints

- Stack ordering inside this PR:
  1. Schema doc + scenario_loader validation
  2. `resolve_source` resolver as standalone module + unit tests
  3. Generator routing (names → personas → weapons → techniques in
     priority order; bail out gracefully on any that can't be routed
     and document)
  4. Preset content stubs (or fallback flag, per master's call)
  5. liuchao / sanguo scenario.json upgrade
  6. Layer 4A E2E (curl first, then write assertions per
     [[screenshot-driven-playwright-iteration]])
  7. ADR-025
- Run the focused suite (`pytest
  tests/test_generation_source_control.py
  tests/test_scenario_generation_profile.py
  tests/test_scenario_avatar_fallback_position.py -v`) after each
  meaningful change.
- Final full-suite run (`pytest tests/`) — expect 1712 + new positives
  + 0 regressions, plus the 3 pre-existing `test_game_init_integration`
  failures (sect-related, unchanged from v1.0) and possibly the 1
  environmental `test_server_binding` failure if port 8002 is held.
- Per [[multi-layer-rc-verification]], Layer 3 / 4A is master's manual
  Mac time; codex writes the spec, master runs Playwright.
- Commit & push: codex sandbox cannot write `.git/index.lock`. Leave
  changes in working tree. Hassan commits + pushes + tags.
