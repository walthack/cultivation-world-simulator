# Spec: v1.1 — Scenario World Generation Control

**Status**: draft (Hassan, 2026-06-07)
**Version**: v1.1 (off `v1.0.1`, supersedes v1.0.1's minimal fallback)
**Owner**: codex (implementation + tests + ADR); Hassan reviews spec only
**Branch**: `feat/scenario-world-generation-control-v1.1` (off `main` @ `v1.0.1`)
**ADR**: ADR-024 (new — supersedes nothing)
**Tag target**: `v1.1.0`

---

## 1. Why this exists

v1.0 ships scenario avatars + relations + scripted timeline, but
default world generation (random NPC fill, random sect fill) still runs
**on top of** scenario content. Result: a "六朝" game has 3 scenario
NPCs + 9 random NPCs scattered the map, so "most of the world is not
六朝." This violates the v1.0 Discussion promise of "import a
pre-defined world" because the world is still mostly random.

v1.0.1 fixes the (0,0) stacking visual bug with random fallback.

v1.1 makes scenarios **first-class controllers of world generation**.
Authors decide how much default randomness mixes with their scripted
content, and where their scripted NPCs go.

## 2. Six things v1.1 must deliver (master's spec 2026-06-07)

1. **scenario controls `random_npc_count`** — override default
   `init_npc_num`
2. **scenario controls `random_sect_count`** — override default
   `sect_num`
3. **scenario can disable default generation entirely** — pure
   scripted world
4. **scenario avatars support `region_id` / `pos`** — intentional
   placement
5. **liuchao / sanguo use a generation_profile** — bundled scenarios
   become reference examples of the new control surface
6. **no-scenario games preserve v1.0 behavior** — fully backward
   compatible, no regressions

## 3. Schema — `scenario.json`

Add a new `generation_profile` block under `initial_state`, plus per-
avatar `pos` / `region_id`. All optional.

```jsonc
{
  "schema_version": "1.1",
  "scenario_id": "liuchao",
  // ... existing top-level fields ...

  "initial_state": {
    "year": 1,
    "month": 1,

    // NEW — optional. Controls how default random generation mixes
    // with this scenario's scripted content. Omitted = v1.0 behavior
    // (full default generation on top of scripted content).
    "generation_profile": {
      // null / omitted = use default (settings.json new_game_defaults.init_npc_num)
      // 0 = no random NPCs (pure scripted)
      // N>0 = exactly N random NPCs added
      "random_npc_count": 0,

      // null / omitted = use default (settings.json new_game_defaults.sect_num)
      // 0 = no random sects
      // N>0 = exactly N random sects
      "random_sect_count": 0,

      // false (default) = run default generation pipeline at all
      // true = skip default generation entirely; only scripted
      //        avatars/sects from initial_state exist
      // Mutually exclusive with the count fields when true (count
      // fields ignored).
      "use_scripted_only": false
    },

    "avatars": [
      {
        "id": "wang-zhe",
        // ... existing avatar fields ...

        // NEW — optional, mutually exclusive with region_id
        "pos": { "x": 42, "y": 17 },

        // NEW — optional, mutually exclusive with pos
        "region_id": 5
      }
    ],
    "sects": [ /* ... */ ],
    "relationships": [ /* ... */ ],
    "world_flags": { /* ... */ }
  }
}
```

Bumps `schema_version` from `0.1` to `1.1`. Loader must accept both
(0.1 = legacy, no generation_profile, no per-avatar pos/region_id;
1.1 = full v1.1 surface). Existing v1.0 scenarios continue to load and
behave exactly as before.

## 4. Behavior — `src/server/init_flow.py` + `src/sim/avatar_init.py`

### 4.1 World generation order with a scenario

```
1. ScenarioInjectedWorld.create_with_db → apply scenario start time,
   inject scripted_scenario metadata
2. Build map from world_preset
3. Build sects:
   - Always: scripted sects from initial_state.sects
   - Then: random sects per generation_profile.random_sect_count
     (or settings default if profile omitted, or skip if
     use_scripted_only=true)
4. Build avatars:
   - Always: scripted avatars from initial_state.avatars
     (placement priority: pos → region_id → random scatter)
   - Then: random NPCs per generation_profile.random_npc_count
     (or settings default if profile omitted, or skip if
     use_scripted_only=true)
5. Inject relationships from initial_state.relationships
```

### 4.2 World generation order WITHOUT a scenario

Unchanged. Settings `new_game_defaults.init_npc_num` and `sect_num`
drive default generation. No new code paths fire when scenario is None.

### 4.3 `create_scenario_avatar` position priority

(Same as v1.0.1, but now reading new schema fields:)

1. `avatar.pos` present and valid → use `pos.x, pos.y`
2. `avatar.region_id` present and valid → pick random tile within that
   region
3. neither → random scatter (v1.0.1 fallback)

Always: set `tile`, `born_region_id`.

### 4.4 generation_profile resolution

Pseudo-code in `init_flow.py`:

```python
def resolve_generation_counts(*, scenario, settings):
    profile = (
        scenario and scenario.initial_state.get("generation_profile")
    ) or {}

    if profile.get("use_scripted_only"):
        return {"npc_count": 0, "sect_count": 0}

    npc_count = profile.get("random_npc_count")
    if npc_count is None:
        npc_count = settings.new_game_defaults.init_npc_num

    sect_count = profile.get("random_sect_count")
    if sect_count is None:
        sect_count = settings.new_game_defaults.sect_num

    return {"npc_count": int(npc_count), "sect_count": int(sect_count)}
```

## 5. Validation — `src/scenario/scenario_loader.py`

Add at load time (raise `ScenarioValidationError` with clear message):

- `generation_profile.random_npc_count` must be int ≥ 0 or omitted
- `generation_profile.random_sect_count` must be int ≥ 0 or omitted
- `generation_profile.use_scripted_only` must be bool or omitted
- `avatar.pos.x / y` must be int ≥ 0 (map bound check happens at
  injection time — loader doesn't know map dims)
- `avatar.region_id` must be int (existence check happens at injection
  time when world.map is built)
- `pos` and `region_id` mutually exclusive per avatar

## 6. Content updates — bundled scenarios

This PR DOES update `config/scenarios/liuchao/scenario.json` and
`config/scenarios/sanguo/scenario.json` to demonstrate the new
control surface (master's spec point 5: "liuchao / sanguo 通过
generation profile 接管世界生成").

### liuchao
- `generation_profile.random_npc_count: 3` (small backdrop only;
  the world is meant to feel scripted)
- `generation_profile.random_sect_count: 1`
- avatars get region_id placement per the **temporary principle**
  below; specific values **TBD until PR review** — codex must not
  pick narrative positions on its own.

**Temporary placement principle** (master 2026-06-07, applies to v1.1
first pass):

- Avatars with an explicit `sect` or known region affiliation → place
  in that affiliation's region (e.g. 王哲 → 太乙真宗 sect region
  because `sect_id: 1`).
- Avatars without affiliation → leave `region_id` and `pos` omitted in
  the JSON; the engine's scatter fallback (the v1.0.1 step-3 path)
  handles them.

Codex implements the **mechanism** (priority pos → region_id → random)
and applies this principle to bundled scenario content. **No
narrative coordinates baked in.** Master adjusts specific
`region_id` / `pos` values during PR review.

### sanguo
- `generation_profile.random_npc_count: 5`
- `generation_profile.random_sect_count: 2`
- avatars: existing list gains region_id where master specifies

(If master prefers to defer content updates to a separate PR, drop
this section to "out of scope" — clean engine-only PR is also
acceptable.)

### sample / e2e_test
Unchanged — they exist to test the engine, not to demonstrate
intentional placement.

## 7. Tests

### Layer 1 — backend pytest

`tests/test_scenario_generation_profile.py` (new file):

**Positive**
- `test_profile_random_npc_count_overrides_default` — scenario with
  `random_npc_count: 2`, world has exactly 2 random NPCs + scripted
- `test_profile_random_sect_count_overrides_default` — same for sects
- `test_profile_use_scripted_only_skips_defaults` — `use_scripted_only:
  true` → world has only scripted avatars/sects, regardless of
  settings defaults
- `test_no_profile_uses_settings_defaults` — scenario without
  generation_profile → settings init_npc_num + sect_num applied (v1.0
  parity)
- `test_no_scenario_unchanged` — game started without a scenario uses
  settings defaults, no generation_profile code path fires
- `test_avatar_pos_explicit_lands_at_coords` — pos lands at coords
- `test_avatar_region_id_lands_in_region` — region_id picks tile in
  region

**Negative (Layer 5)**
- `test_loader_rejects_negative_random_npc_count`
- `test_loader_rejects_non_bool_use_scripted_only`
- `test_loader_rejects_pos_and_region_id_together`
- `test_loader_rejects_negative_pos_coords`
- `test_injection_rejects_out_of_bounds_pos` (at injection time, since
  map dims known then)
- `test_injection_rejects_unknown_region_id`

### Layer 4A — frontend Playwright E2E

Update `web/e2e/layer4-scenario-engine.spec.ts`:

- Add Step 9: `--scenario=liuchao`, query avatars endpoint, assert all
  3 scripted avatars exist with non-null tile and born_region_id, and
  with distinct `(pos_x, pos_y)` tuples.
- Add Step 10: same scenario, query avatar count, assert total ==
  liuchao's scripted (3) + liuchao's `random_npc_count` (3) = 6 (or
  whatever the final content number is in §6).

### Layer 5 — milestone negative test audit

This whole spec is one milestone PR. ≥ 1 negative test required by
[[milestone-pr-stack]] — the loader / injection negative tests above
more than satisfy this.

## 8. ADR-024 outline

`docs/adr/ADR-024-scenario-world-generation-control.md`:

- **Context**: v1.0 / v1.0.1 left scenario avatars existing alongside
  default random generation. Result: scripted worlds feel
  predominantly random. Master playtest 2026-06-07 surfaced this.
- **Decision**: Introduce `generation_profile` and per-avatar position
  fields in scenario.json (schema_version 1.1). Scenarios become
  first-class controllers of world generation, overriding settings
  defaults when present.
- **Alternatives considered**:
  - Replace settings defaults entirely when any scenario active — too
    blunt; some scenarios want light scripted seasoning on a
    procedural world.
  - Per-avatar count override only (no profile block) — couldn't
    express "use scripted only," only relative tweaks.
  - Bake counts into scenario_id alias (e.g. `liuchao-strict` vs
    `liuchao-loose`) — explosion of IDs, no clean fallback.
- **Consequences**:
  - Existing scenarios at schema_version 0.1 / 1.0 continue to load
    and behave exactly as before (full v1.0 parity)
  - Authors get expressive control; tooling (Wizard) can surface the
    profile in a follow-up.
  - No-scenario games unaffected.
  - liuchao / sanguo become "this is what intentional design looks
    like" examples.

## 9. Acceptance criteria (codex: PR ready when all hold)

- [ ] `scenario_loader` accepts schema_version 1.1 with
  `generation_profile` + per-avatar `pos` / `region_id`; rejects
  schema-1.1 with invalid values; still accepts schema_version 0.1
- [ ] `init_flow.py` resolves generation counts via priority profile
  → settings; honors `use_scripted_only`
- [ ] `create_scenario_avatar` placement priority pos → region_id →
  random fallback (the v1.0.1 fallback graduates to step 3 of this
  priority)
- [ ] 7 positive + 6 negative backend tests added & green
- [ ] Layer 4A E2E Step 9 + 10 added & green; full Layer 4A still
  7 (or 9) / N PASS
- [ ] ADR-024 written
- [ ] `config/scenarios/liuchao/scenario.json` and `sanguo/scenario.json`
  updated to schema_version 1.1 with generation_profile + per-avatar
  placement (or this is split to a follow-up content PR with master's
  agreement)
- [ ] `config/scenarios/sample/scenario.json` left untouched
- [ ] No-scenario game smoke (`python src/server/main.py --dev`)
  generates exactly `settings.new_game_defaults.init_npc_num` NPCs and
  `sect_num` sects — v1.0 parity
- [ ] Full v1.0.1 test suite still passing
- [ ] `docs/release-verification-report.md` updated with v1.1 row

## 10. Out of scope (defer)

- Wizard UI (ScenarioWizardModal) showing generation_profile inputs.
  Recommended follow-up: v1.1.x or v1.2.
- Scenario-level map override (replacing the preset map). Already
  separately deferred.
- Tooling to bulk-update old scenarios to schema 1.1. They keep
  working at 0.1; authors migrate when they want the new control.

---

## Codex dispatch hints

- Stack ordering inside this PR:
  1. Schema doc + scenario_loader validation (smallest, well-defined)
  2. `create_scenario_avatar` placement priority (touches injection)
  3. `init_flow.py` generation_profile resolver + use in NPC/sect
     spawn paths
  4. backend tests
  5. liuchao / sanguo content updates (or split off — confirm with
     master)
  6. Layer 4A E2E updates
  7. ADR-024
- Use `screenshot-driven-playwright-iteration` for Layer 4A — `curl`
  the avatars endpoint first to confirm shape.
- Per [[multi-layer-rc-verification]], all five layers green before
  tag `v1.1.0`.
- Per [[milestone-pr-stack]], if PR feels too big, candidate split
  points: (a) schema + loader as one PR, (b) injection + tests as
  second, (c) content updates as third. Master can decide on dispatch.
