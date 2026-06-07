# Spec: v1.0.1 — Scenario Avatar Fallback Position (minimal patch)

**Status**: draft (Hassan, 2026-06-07)
**Type**: **hotfix** — does NOT change scenario schema (no new fields,
no schema_version bump). Schema 1.1 + generation_profile arrive in v1.1.
**Version**: v1.0.1 — patch release on top of `v1.0.0-final`
**Owner**: Hassan (small, do in one go — no codex dispatch needed)
**Branch**: `fix/scenario-avatar-position-v1.0.1` (off `main` @ `v1.0.0-final`)
**Tag target**: `v1.0.1`

---

## 1. Why patch first, why minimal

Master playtest 2026-06-07: `--scenario=liuchao` shipped 3 scenario
avatars at `(0,0)` because `create_scenario_avatar`
(`src/sim/avatar_init.py:1585`) didn't set position / tile /
born_region_id at all. Visible stacking, immediate UX break.

Full design ("Scenario World Generation Control") lands in v1.1 — but
that needs schema changes, generation profiles, multiple test layers,
and a codex PR cycle. v1.0.1 is the **minimum** fix so existing v1.0
users (and master's ongoing playtest) get a sane fallback today.

**Scope**: random fallback position only. No schema change. No new
JSON fields. No author control over placement. v1.1 supersedes.

## 2. The patch

In `src/sim/avatar_init.py` `create_scenario_avatar`, before the
`Avatar(...)` constructor:

```python
pos_x = random.randint(0, world.map.width - 1)
pos_y = random.randint(0, world.map.height - 1)
```

Pass `pos_x, pos_y` to `Avatar(...)`. After construction:

```python
avatar.tile = world.map.get_tile(avatar.pos_x, avatar.pos_y)
avatar.born_region_id = get_born_region_id(world, parents=[], sect=sect, race=None)
```

That's it. ~6 lines net.

(The current working-tree `QUICK-PATCH 2026-06-07 (Hassan)` block is
exactly this — graduate it to a proper commit with comment cleaned up:
no "QUICK-PATCH" label, no "v1.1 will replace" note — those concerns
live in v1.1's spec, not in this hotfix.)

## 3. Tests (Layer 1 + Layer 5)

New file `tests/test_scenario_avatar_fallback_position.py`:

**Positive**
- `test_scenario_avatar_gets_random_position_and_tile` — load a
  scenario with one avatar (no pos / region_id), inject into a world,
  assert `avatar.pos_x` in `[0, map.width-1]`, `pos_y` in
  `[0, map.height-1]`, `tile is not None`, `born_region_id != -1`.
- `test_scenario_avatars_scatter_across_runs` — over 30 trials with the
  same single-avatar scenario, observed `(pos_x, pos_y)` tuples cover
  more than 1 distinct value (statistical scatter — proves random not
  pinned to a constant).

**Negative**
- `test_scenario_avatar_creation_uses_map_bounds` — explicitly construct
  a world with known `map.width=20, height=20`, then assert no avatar
  pos ever exceeds those bounds across 50 trials (defensive against
  off-by-one in `randint`).

No schema validation, no new fields → no `ScenarioValidationError`
cases needed yet.

## 4. RC verification (subset of full 5-layer)

- Layer 1: new file passes + full backend pytest still 1694 (or 1694 +
  3 new = 1697) passing.
- Layer 2: ff-merge to main clean (it's a 1-file patch, trivially
  clean).
- Layer 3 / 4A: no Playwright changes required — the position bug
  wasn't covered by Layer 3/4A, so they keep passing as-is. (Adding
  position contract to Layer 4A is v1.1's job.)
- Layer 5: 1 negative test in the new file.
- Boot smoke `--scenario=liuchao` still green (year=1, avatars exist).
- Master visual check: scenario avatars no longer stacked at (0,0) in
  the rendered map.

## 5. Release notes (drop into `docs/release-verification-report.md`
or a `CHANGELOG.md` snippet)

```
v1.0.1 (2026-06-07)
- Fix: scenario avatars no longer spawn stacked at map origin (0,0).
  `create_scenario_avatar` now assigns a random position and resolves
  `tile` + `born_region_id` like random NPCs do. Schema unchanged.
  Authors can opt into intentional placement in v1.1 (see v1.1 spec).
- No schema changes, no API changes, no behavior change for
  no-scenario games or for scenarios without `initial_state.avatars`.
```

## 6. Acceptance criteria

- [ ] `create_scenario_avatar` sets random pos + tile + born_region_id
  unconditionally
- [ ] 2 positive + 1 negative test in
  `tests/test_scenario_avatar_fallback_position.py`
- [ ] Full backend pytest green (1694 + new = 1697)
- [ ] Boot smoke `--scenario=liuchao` still year=1, scenario avatars
  registered, no longer stacked at (0,0) (manual visual)
- [ ] Working-tree quick-patch from 2026-06-07 promoted to a clean
  commit with comment normalized
- [ ] Tag `v1.0.1` cut after merge to main
- [ ] `docs/release-verification-report.md` updated with v1.0.1 row

## 7. Out of scope (deferred to v1.1)

- Per-avatar `pos: {x, y}` and `region_id` fields in scenario.json
- `generation_profile` (random_npc_count / random_sect_count /
  use_default_generation overrides)
- liuchao / sanguo content updates to use generation profile
- Layer 4A E2E assertion that scenario avatars have distinct positions
