# Stage 2d D-d1 Spec — Second Scenario (三国 mock) to Prove Generality

Date: 2026-06-02
Author: Hassan
Status: Ready for codex implementation
Master signoff:
- 2026-06-02 23:00 SGT — Q1 = 三国 mock (not simple_demo), Q2 = 6-10 timeline events 起步, Q3 = dispatch codex directly

## Goal

Author a **second scenario** independent from liuchao to prove the Scenario Engine is a **generic mod system**, not 六朝-hardcoded. The acceptance is: `python src/server/main.py --dev --scenario sanguo` boots cleanly, the new scenario loads through the same `scenario_loader.load()` API, and a sanguo-specific timeline event fires correctly through phase 12.5 (Stage 2d D-d2 just shipped).

This is content authoring on top of an already-functional engine. No engine changes expected. If you find a gap in the engine that blocks sanguo from working, STOP and report — don't change engine code unilaterally.

## Scope = author one complete scenario folder + preset

### scenario folder
`config/scenarios/sanguo/`:
- `scenario.json` — schema_version 0.2, scenario_id "sanguo", world_preset preset_id "sanguo", 3 initial avatars (liu-bei / cao-cao / sun-quan), world_background text.
- `timeline.json` — schema_version 0.2, **6-10 main events** spread across the three powers, using `dynasty_id` + `trigger.at_region_id` fields. At least one scene MUST be a multi-perspective triple (赤壁前夜 / 三顾茅庐 / 官渡 etc. — pick one), with three events sharing the same trigger date + at_region_id, each gated by `controlled_avatar_is` for liu-bei / cao-cao / sun-quan respectively. Use `{controlled_avatar}` placeholder in at least one effect string.

### preset folder
`config/presets/sanguo/` — all 9 files required (no fallback to default):
- `dynasties.json` — 3 dynasties: shu (蜀, 刘备, capital chengdu, territory shu/hanzhong), wei (魏, 曹操, capital xuchang, territory zhongyuan/luoyang/hebei), wu (吴, 孙权, capital jianye, territory jiangdong/jiangzhou). With pairwise rival/neutral relations (蜀-魏 rival -40, 魏-吴 rival -30, 蜀-吴 neutral 0, possibly later 联吴抗魏 +10).
- `regions.json` — 6-8 regions covering the scene anchors used in timeline.json (chengdu, hanzhong, xuchang, luoyang, hebei, jianye, jingzhou, chibi). Same schema as liuchao regions.
- `region_adjacency.json` — minimal graph connecting the 6-8 regions (each region has 2-3 neighbors).
- `orthodoxies.json` — 2-3 orthodoxies (儒 confucianism, 道 daoism, 法 legalism). Same schema as liuchao orthodoxies.
- `realms.json` — **may copy liuchao 九境 verbatim** (LIAN_QI/ZHU_JI/...). The fiction premise: 三国 alt-history where 诸侯 are also 修士. This is fine — the goal is engine generality, not fictional purity. Alternative: define 5-tier 三国 progression (兵卒/将领/统帅/王侯/霸主) — only do if it's quick.
- `sects.json` — minimal, 2-3 sects max (e.g., 黄巾道 / 五斗米道 / 卧龙). One sect with id=0 or 1 representing "无门派" (default for liu-bei / cao-cao / sun-quan who are 诸侯 not 宗门弟子). OK to be very lean.
- `name_templates.json` — minimal 汉人 name pool. Can crib from liuchao name_templates.json structure.
- `personas.json` — 2-3 personas tagged "三国" / "诸侯" / "枭雄" / "仁义" etc.
- `goldfingers.json` — 2-3 goldfingers themed (e.g., 龙气 / 王霸之气 / 智囊). Same schema as liuchao goldfingers.

### tests
`tests/test_scenario_e2e_sanguo.py`:
- Load sanguo through `scenario_loader.load()` — assert scenario_id, preset_id, 3 avatars present
- Inject into a freshly-created world via `inject_scenario_into_world`, advance simulator one step at year 1 month 1, assert at least one expected sanguo timeline event fires
- Reuse the controlled_avatar perspective test pattern from `test_scenario_e2e_liuchao.py`: set controlled_avatar to liu-bei → only liu-bei's perspective event triggers; switch to cao-cao → only cao-cao's triggers.

Minimum **4 new tests** that prove generality (not just load-validity).

## Forbidden scope

- No engine code changes (`src/scenario/*`, `src/sim/*`, `src/server/*`). If you think the engine needs a change to support sanguo, STOP and report — that's a separate ADR.
- Don't add features to liuchao. Don't touch any existing liuchao files.
- Don't write API endpoints.
- Don't touch `.venv/` (recurring rule from prior dispatches).
- Don't touch `tests/test_game_init_integration.py` (pre-existing failures).

## Acceptance criteria

1. `python src/server/main.py --dev --scenario sanguo` boots, no errors, server idle, version 3.4.0.
2. `world.scripted_scenario.scenario_id == "sanguo"`, timeline non-empty, state ready.
3. `python src/server/main.py --dev --scenario liuchao` still works (no liuchao regression).
4. `scenario_loader.load("sanguo")` returns a `ResolvedScenario` matching schema v0.2.
5. Phase 12.5 dispatches at least one sanguo main event during year 1 month 1 step.
6. Multi-perspective scene: controlled_avatar=liu-bei → only liu-bei's variant fires; switch to cao-cao → only cao-cao's; switch to sun-quan → only sun-quan's. Same scene, same trigger date.
7. `{controlled_avatar}` placeholder substitutes correctly in sanguo effect strings (mirror liuchao's `linan_gate_seen_by_{controlled_avatar}` pattern).
8. Scenario subset pytest: 115 → ≥ 119 (+4 sanguo e2e). No liuchao regression.
9. Full suite: 1623 → ≥ 1627 (or whatever the +new count adds). 3 pre-existing failures unchanged.

## Notes / cribs

- Look at `config/scenarios/liuchao/scenario.json` for the schema shape.
- Look at `config/scenarios/liuchao/timeline.json` for event entry shape (especially the cheng-zongyang-arrives-at-linan-gate trio for multi-perspective pattern).
- Look at `config/presets/liuchao/*.json` for each preset file's schema.
- The `dynasty_id` and `trigger.at_region_id` fields are v0.2 additions (Stage 2c). Use them in every main event.
- Avatar `goldfinger_id` and `persona_traits` must reference keys defined in `goldfingers.json` and personas (or be a small set of free-form trait strings — check what liuchao does).

## Commit grouping

Single feature branch, can be 1-2 commits:
1. `feat: D-d1 — sanguo scenario + preset folder` (all the data files + ADR if you want one — ADR optional for content-only additions)
2. `test: D-d1 — sanguo scenario e2e tests` (the new test file)

If `.git/index.lock` blocks, write working tree and report unstaged.

## Reporting format

```
WROTE (new files):
  <full list of new files>
MODIFIED (existing files):
  <should be empty or near-empty — content-only task>
NEW TEST COUNT: 115 -> <N>
COMMITS: <sha + subject> | unstaged | blocked by lock
DEVIATIONS FROM SPEC: <list if any>
```

"PARTIAL — done: X, remaining: Y" if you bail.
