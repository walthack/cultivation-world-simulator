# Spec: v1.2.2 — Sects Pool Expansion + Loader Warning (A + B)

**Status**: draft (Hassan, 2026-06-08, transcribing master 16:15 directive)
**Type**: content-mostly patch + minimal loader instrumentation (NOT a
mechanism change — no new sect generator).
**Version**: v1.2.2 (off `main` @ `v1.2.1-liuchao-content`)
**Owner**: codex (content + warning + tests); Hassan reviews + verifies + tags
**Branch**: `content/sects-pool-warning-v1.2.2`
**Tag target**: `v1.2.2-sects-pool-warning`

---

## 1. Why

v1.2 verification (2026-06-07, master) flagged **W1**: scenarios
declaring `generation_profile.random_sect_count = 10` produced only
1 (liuchao) or 2 (sanguo) sects. Hassan root-cause analysis
(2026-06-08, message 9536):

- `src/server/init_flow.py:_select_scenario_existed_sects` routes
  `random_sect_count` through a **select-from-pool** algorithm
  (`scripted_sects + select(remaining, needed=random_sect_count)`).
- liuchao `config/presets/liuchao/sects.json` has **1 sect** total
  (太乙真宗); sanguo has **3** (无门派 / 黄巾道 / 五斗米道). After
  scripted sects are removed, `remaining` is too small to honor
  `random_sect_count=10`. Selector returns whatever fits — fail-silent.
- This is NOT a generation_profile bug; it's a thin-content + missing-
  warning combination. The resolver provenance is `scenario`,
  `fallback_to_default` is `false`, `audit.json` shows 0 fallback. The
  mechanism is correct.

v1.2.2 fixes the two thin-content + warning gaps without changing
generation mechanism. **A real "generate sect from template" mechanism
is deferred to v1.3** (master directive: "v1.3 再考虑真正的 sect
generator").

## 2. Scope — master 2026-06-08 (hard limits)

What's IN (A + B):

**A. Content patch**
- `config/presets/liuchao/sects.json` expanded to ≥ 10 entries
- `config/presets/sanguo/sects.json` expanded to ≥ 10 entries
- v1.0/v1.2.1 existing sect IDs preserved (additive only)

**B. Loader warning**
- `src/scenario/scenario_loader.py` (or a sibling resolver-init helper)
  emits a **non-fatal warning** at scenario load time when
  `generation_profile.random_sect_count > pool_size - scripted_count`
- Warning is logged (via `logging.warning` or `print` to stderr —
  codex picks the convention already used in `scenario_loader.py`
  / `init_flow.py`) with these fields verbatim:
  - scenario id
  - declared `random_sect_count`
  - available pool size (`len(preset_sects.json sects)`)
  - scripted sect count (`len(scenario.initial_state.sects)`)
  - effective cap (`max(0, pool_size - scripted_count)`)

**Explicitly OUT (do not touch)**:
- Sect generator code path. v1.2.2 does NOT add "generate sect from
  template" or any new mechanism. Master directive: v1.3 only.
- Schema. No new top-level fields, no schema_version bump (still 1.2).
- Mod platform.
- Other preset content (races / roots / techniques / weapons stay
  exactly as v1.2.1 shipped).
- scenario.json files (`config/scenarios/liuchao/scenario.json`,
  `sanguo/scenario.json`) — don't touch.
- `default` preset.
- Any non-warning behavioral change. The warning **must not fail
  loading** under any condition.

## 3. A — Content requirements

### 3.1 Counts
- Each preset's `sects.json` must have **at least 10 entries** in
  `sects: [...]` (the inline-entity form, not just `sect_ids`).
- `sect_ids` list must be updated to include every new sect's `id`.

### 3.2 Theme — match v1.2.1 motifs already used
- liuchao: lean on 门阀 (aristocratic clans), 清谈 (philosophical
  salons), 寺观 (Buddhist/Daoist abbeys), 流亡 (refugee/exile),
  山水 (landscape), 玄学 (Xuanxue), 江左 (south-of-Yangtze). Each
  new sect should pick 1-2 motifs visible in its name + description.
- sanguo: lean on 黄巾余孽 / 五斗米道 / 江东 / 西凉 / 北地豪族 /
  许都侍御 (court attendants) / 太学清议. New names should map to
  generic 三国 tropes.

### 3.3 Fields per entry (match existing shape)
```jsonc
{
  "id": 7,
  "scenario_id": "liuchao-qingtan-she",   // stable slug
  "name": "清谈社"
  // codex confirms whether existing entries carry more fields
  // (orthodoxy / leader / region) by reading current liuchao/sanguo
  // sects.json end-to-end first; matches that shape exactly
}
```

### 3.4 IDs
- liuchao existing IDs preserved: `1` (太乙真宗 — keep as id=1)
- sanguo existing IDs preserved: `0` (无门派), `1` (黄巾道), `2` (五斗米道)
- New entries use **integer IDs starting from `2` (liuchao)** or
  `3` (sanguo)`, contiguous, no gaps
- `scenario_id` slug-style, prefix `liuchao-` or `sanguo-` respectively

### 3.5 Numerical / mechanic discipline
- No power creep (this is sect metadata, mechanics are downstream of
  sect attributes if they exist — codex matches existing entries'
  shape; do not invent new effect fields)
- Each entry needs a `name` (Chinese) and `scenario_id` (slug)

## 4. B — Loader warning requirements

### 4.1 Trigger condition

Inside scenario loading (Phase A in `scenario_loader.py`, after the
existing fail-fast preset-file check), evaluate:

```python
sects_source = generation_sources.get("sects")  # "scenario" or "default"
random_sect_count = generation_profile.get("random_sect_count")

if (
    sects_source == "scenario"
    and random_sect_count is not None
    and random_sect_count > 0
):
    pool = load_preset_sects(preset_id).get("sects", [])
    scripted = scenario.initial_state.get("sects", [])
    available = max(0, len(pool) - len(scripted))
    if random_sect_count > available:
        log_warning(
            f"Scenario '{scenario_id}' declared "
            f"random_sect_count={random_sect_count} but only "
            f"{available} sects available in preset '{preset_id}' "
            f"after {len(scripted)} scripted (pool size {len(pool)}). "
            f"Effective sect cap will be {available}."
        )
```

(Codex finalizes the exact phrasing to match house style; the **five
fields** must appear: scenario_id, declared count, available count,
scripted count, effective cap. The wording above is illustrative.)

### 4.2 Non-fatal — hard rule

- Warning **must not raise**. Loading proceeds.
- Warning must not break `fallback_to_default = false` semantics
  elsewhere (the existing fail-fast for missing preset files stays
  unchanged).
- If `random_sect_count` is omitted or `None`, no warning.
- If `sects_source == "default"`, no warning (master is opting out
  of scenario sect pool).
- If a no-scenario game is loaded, no warning (scenario None → skip
  entire generation_profile resolution per v1.1 semantics).

### 4.3 Where the warning surfaces
- At minimum: stderr / Python logger at level WARNING.
- If `scenario_loader.py` already accumulates `ScenarioLoadIssues`
  (look for similar patterns in v1.2 code), append the warning there
  so future readers / a future Wizard UI can surface it. Otherwise
  bare `logging.warning(...)` is acceptable.

## 5. Tests

Add to a **single new file** `tests/test_sects_pool_warning.py` (don't
mix into v1.2.1 / v1.2 tests; this is its own concern):

### Positive
- `test_liuchao_random_sect_count_now_reaches_target_or_pool_cap`:
  init a fresh liuchao world with `random_sect_count=10`, expect
  generated sect count ≥ 8 (allowing room for scripted overlap; if
  liuchao's expanded pool is 10 and 1 is scripted, available=9,
  expected sects = 1 scripted + 9 random = 10).
- `test_sanguo_random_sect_count_reaches_pool_cap`: same shape.
- `test_warning_NOT_emitted_when_random_sect_count_within_pool`:
  using a scenario with `random_sect_count=5` and a pool of 12, no
  warning is logged.

### Negative / instrumentation
- `test_warning_emitted_when_random_sect_count_exceeds_pool`:
  construct a scenario with `random_sect_count=99` on liuchao's
  current pool, assert a warning is captured and that the message
  contains all 5 required fields (scenario id, declared count,
  available count, scripted count, effective cap).
- `test_warning_NOT_emitted_when_no_scenario`: no-scenario game →
  no sect warning even if settings would imply a mismatch.

### Regression
- `tests/test_generation_source_control.py`, `test_scenario_generation_profile.py`,
  `test_scenario_avatar_fallback_position.py`, `test_mod_platform.py`
  — all stay green. Codex re-runs after each meaningful change.

## 6. Acceptance criteria (codex: done when all hold)

- [ ] `config/presets/liuchao/sects.json` `sects` array has ≥ 10
  entries, includes existing id=1 (太乙真宗)
- [ ] `config/presets/sanguo/sects.json` `sects` array has ≥ 10
  entries, includes existing id=0 / id=1 / id=2
- [ ] Both files' `sect_ids` list synchronized with the new entries
- [ ] No new top-level fields in either sects.json
- [ ] scenario_loader emits a non-fatal warning when
  `random_sect_count > pool_size - scripted_count` and
  `generation_sources.sects == "scenario"`
- [ ] Warning message contains all 5 required fields (scenario id,
  declared count, available count, scripted count, effective cap)
- [ ] Warning suppressed for: no scenario / `sects: "default"` /
  `random_sect_count` omitted / `random_sect_count ≤ available`
- [ ] 5 new tests in `tests/test_sects_pool_warning.py` (3 positive
  + 2 instrumentation) all green
- [ ] No regression in v1.2 (9 tests), v1.1 (14 tests), v1.0.1 (3
  tests), mod_platform (12 tests) — Hassan reruns broad pytest at
  verification time, codex confirms focused suites first
- [ ] No edits to anything outside the 4 listed files (2 sects.json,
  1 scenario_loader.py, 1 new test file) — verify with
  `git diff --name-only` before reporting done

## 7. Codex dispatch hints

Stack order inside this PR:
1. Read the spec end-to-end.
2. Read current `config/presets/liuchao/sects.json` and `sanguo/sects.json`
   end-to-end to confirm field shape and existing IDs.
3. Decide the warning emission point in `scenario_loader.py` first
   (small, well-scoped change); add the warning hook with no condition
   yet.
4. Write 5 tests in `tests/test_sects_pool_warning.py`. Two should
   already pass (no-scenario, within-pool); three should fail
   (instrumentation hooks not wired, content insufficient).
5. Wire the warning condition properly (run instrumentation tests).
6. Expand `liuchao/sects.json` and `sanguo/sects.json` (run the
   positive tests).
7. Re-run the focused regression suites.

Run focused suites after each meaningful change:
```
.venv/bin/pytest tests/test_sects_pool_warning.py tests/test_generation_source_control.py tests/test_scenario_generation_profile.py tests/test_scenario_avatar_fallback_position.py tests/test_mod_platform.py -v
```

Total expected green tests after this PR:
- v1.2.2 sects pool warning: 5
- v1.2 generation source control: 9
- v1.1 generation profile: 14
- v1.0.1 avatar fallback: 3
- mod platform: 12
- **Subtotal: 43 focused tests**

**Commit / push**: codex sandbox cannot write `.git/index.lock`.
Leave changes in working tree. Hassan commits + pushes + ff-merges +
tags `v1.2.2-sects-pool-warning`.

**Report back with**:
- Files changed (should be exactly 4: 2 sects.json, 1 scenario_loader.py,
  1 new test file). Confirm with `git diff --name-only` and `git status`.
- Sect entry counts per preset, with existing IDs called out as preserved
- Theme map: which 2-3 motifs from §3.2 surface in each preset
- Warning trigger sample: paste the warning message string captured in
  the negative instrumentation test
- Test result line for the 5-suite focused run
- Anything ambiguous in the spec that you resolved on your own
