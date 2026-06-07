# Spec: v1.2.1 — Liuchao Content Patch (content-only)

**Status**: draft (Hassan, transcribing master 2026-06-07 15:12 directive)
**Type**: **content-only patch** — no schema, no code, no mechanism change.
**Version**: v1.2.1 (off `main` @ `v1.2.0-final`)
**Owner**: codex (content authoring); Hassan reviews + verifies + tags
**Branch**: `content/liuchao-preset-v1.2.1`
**Tag target**: `v1.2.1-liuchao-content`

---

## 1. Why

v1.2 shipped the *mechanism* for scenario source pool control + thin
14-entry stubs in `config/presets/liuchao/{races,roots,techniques,
weapons}.json`. Audit (master 2026-06-07 14:56) found the stubs are:

- formally minimal (3/5/3/3 entries, spec lower bound)
- mostly placeholder mechanics (`stat_modifiers: {}`, `effect_dsl: ""`,
  `effects: []` everywhere, uniform `+1 battle_strength` on weapons)
- `roots.json` is a verbatim rename of default 五元素 — zero
  differentiation
- result: a liuchao playtest game does not yet *feel* 六朝-flavored

v1.2.1 fills those four files with playtest-grade differentiated
content. **No schema change. No code change. No mod_platform touch.**

## 2. Scope — master 2026-06-07 (hard limits)

What's IN:
- only `config/presets/liuchao/{races,roots,techniques,weapons}.json`
- content authoring (entries + names + descriptions + mechanics)
- the same JSON shape the v1.2 loader already reads

What's OUT (do not touch — explicit non-goals):
- schema / `scenario.json` / loader
- resolver / generator code
- `mod_platform/*`
- new field types / new entry kinds
- sanguo preset (separate v1.2.x patch if master wants)
- preset structure across other files (`dynasties` / `regions` /
  `sects` / `personas` / `name_templates` / `orthodoxies` / etc.)

## 3. Requirements (master directive, verbatim transcription)

### 3.1 Counts
- each of the 4 files: **at least 8-12 entries**
- `roots.json`: **may keep the five elements**, but **must add
  liuchao-flavored variants** (e.g. variants tied to mountain, river,
  shrine, mourning, exile, salon)

### 3.2 Mechanics
- **at least 70% of entries per file** must have non-empty
  `effects` / `stat_modifiers` / `effect_dsl`
- **no uniform `+1 battle_strength`** — vary the mechanic kind and
  magnitude across entries

### 3.3 Theme — every category must surface 六朝 motifs
Choose from these themes (lean on more than one per file):
- **门阀** (aristocratic clans)
- **清谈** (philosophical salons)
- **山水** (landscape / mountain-water aesthetics)
- **玄学** (Xuanxue / metaphysical thought)
- **江左** (south-of-Yangtze geography)
- **流亡** (exile, displacement, refugee themes)
- **寺观** (Buddhist temples / Daoist abbeys)
- **志怪** (strange-tales literature)
- **乱世** (turmoil, dynastic collapse)

### 3.4 Numerical discipline
- `tier: 1` start unless an entry is conceptually distinct (e.g. a
  rare 寺观 relic might justify tier 2 — only when narratively earned)
- no power creep; if `effects` magnitude exceeds the v1.2 stub's
  `+1` / `+2`, the entry needs a clear reason in `description`
- avoid stacking large `stat_modifiers` that would dominate v1.2.0
  baseline game balance

### 3.5 IDs
- **all IDs must be stable, slug-style, prefixed `liuchao-`**
- examples: `liuchao-shanshui-zhuyou`, `liuchao-xuxue-jueli`,
  `liuchao-jiangzuo-mingshi`
- existing v1.2.0 stub IDs (`liuchao-qingxu`, `liuchao-bamboo-sword`,
  etc.) **must be preserved** as a subset — playtest saves and any
  fixtures referencing them keep working. New entries are additive.

### 3.6 Structural fidelity
- **JSON structure must remain loader-readable.** Match the existing
  shape of each file exactly:
  - `races.json`: `{preset_id, races: [{id, name, description,
    behavior_description, weight, stat_modifiers, effect_dsl, tags}]}`
  - `roots.json`: `{preset_id, roots: [{id, name, description,
    elements, stat_modifiers, effect_dsl, tags}]}`
  - `techniques.json`: `{preset_id, techniques: [{id, name, grade,
    attributes, effects, prereq_realm, source_sect_id}]}`
  - `weapons.json`: `{preset_id, weapons: [{id, name, tier,
    attributes, effects, required_realm}]}`
- if any field shape is unclear, read the matching `default` preset
  file in `config/presets/default/` as a reference, NOT to copy
  content but to confirm field semantics
- do not introduce new top-level keys
- do not change `preset_id` (`"liuchao"` everywhere)
- `tags` field in races/roots: keep `"liuchao"` tag; additional tags
  allowed if they encode themes (e.g. `["liuchao", "xuxue"]`)

## 4. Verification (master directive)

After codex finishes, Hassan runs:

1. `.venv/bin/pytest tests/test_generation_source_control.py -v` —
   expect 9/9 PASS (v1.2 contract unchanged)
2. `.venv/bin/pytest tests/test_scenario_generation_profile.py -v` —
   expect 14/14 PASS (v1.1 contract unchanged)
3. **Backend restart** + playtest:`--scenario=liuchao` new game,
   inspect random NPCs in the rendered map
4. **Human-eye check**: random NPCs visibly differ from default and
   from sanguo across at least 2 of {name flavor, race composition,
   technique names, weapon names}

## 5. Acceptance criteria (codex: done when all hold)

- [ ] all 4 files have ≥ 8 entries, ≤ 12 entries
- [ ] roots.json keeps 5 elements (GOLD/WOOD/WATER/FIRE/EARTH) AND
  adds liuchao-flavored variants
- [ ] ≥ 70% of entries per file have non-empty
  `effects` OR `stat_modifiers` OR `effect_dsl`
- [ ] no entry uses uniform `+1 battle_strength` mechanic without a
  thematic reason (each entry's mechanic should match its theme)
- [ ] every file surfaces at least 2 of the 9 motifs in §3.3
- [ ] all IDs slug-style with `liuchao-` prefix
- [ ] v1.2.0 stub IDs preserved (additive, not replacing)
- [ ] JSON loader-readable — no new top-level keys, fields match
  existing shape
- [ ] focused tests still green (verification 1 + 2)
- [ ] no edits to anything outside the 4 files (verify with
  `git diff --name-only`)

## 6. Codex dispatch hints

- Read each existing v1.2.0 stub file end-to-end before writing —
  preserve those IDs.
- Read the corresponding `config/presets/default/*.json` for field
  shape only (don't copy content; the *whole point* of v1.2.1 is
  differentiation from default).
- Spread the 9 themes across the 4 files; not every entry needs all
  themes, but each file should touch 2-3.
- Effects should vary in mechanic kind. Examples (illustrative):
  - 山水 race: `stat_modifiers: {wisdom: +1}` (山水 cultivates insight)
  - 流亡 race: smaller `weight`, `tags: ["liuchao", "exile"]`
  - 清谈 technique: `effects: [{extra_persuasion_strength: 2}]` if
    such effect kind exists in default — codex checks the default
    preset's effect vocabulary first
  - 玄学 technique: tier 1 but with prereq_realm to gate progression
  - 江左 weapon: `attributes: ["FAN"]` with `effects:
    [{extra_battle_strength_points: 1, extra_resist: 1}]` — mild,
    flavor-driven, no power creep
  - 门阀 weapon: tier 1 ceremonial blade with non-combat effect
- Codex does NOT need to be a 六朝 scholar; cite from common-knowledge
  历史 tropes (王羲之 / 陶渊明 / 谢安 / 桓玄 / 慧远 / 寒山 / 玄学
  / 山水诗 / 志怪小说 are all generic enough). If unsure about an
  entry's authenticity, prefer a generic Tang-or-earlier-flavored
  alternative rather than inventing implausible content.
- Each new entry needs a `description` field (where the schema has
  it) — 1-2 sentences of plain Chinese, no English in descriptions.
- After writing, validate JSON parses (`python -m json.tool < file`)
  and run the focused test suite.

## 7. Commit & push

- Codex sandbox cannot write `.git/index.lock`. Leave changes in
  working tree on `content/liuchao-preset-v1.2.1`. Hassan commits +
  pushes + ff-merges + tags `v1.2.1-liuchao-content`.
- Single commit on this branch (small content-only diff, no need for
  splits).
