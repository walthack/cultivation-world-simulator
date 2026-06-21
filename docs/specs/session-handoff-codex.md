# Session Handoff — for Codex

**Repo:** /Users/clawbot/Projects/cws-fork · **Branch:** main · **Head:** `f1d9ec59` (pushed) · **Tests:** `.venv/bin/python -m pytest -q` → **2015 pass / 2 skip**, zero regression.

This is the live, self-contained handoff. Read these first, in order:
1. `docs/specs/v1.9-narrative-director.md` — the L4 engine spec + per-milestone log + every codex 二审 minute + the v1.9 完成宣告.
2. `docs/specs/scenario-package-authoring-guide.md` — the scenario plugin-package format contract (how to author/import a package).
3. `docs/specs/v1.9-remaining-work-codex-handoff.md` — the v1.9.x engine backlog.
4. This doc — current state across engine + content + packaging + ops.

---

## 1. Where things stand

### v1.9 L4 Narrative Director — COMPLETE
The engine ships. 6 bounded-hard director commands, all gated by **backbone (Q1/Q4: prohibited_predicates + irreversible_facts)** + **forward-replay reachability (Q3)**: `director_set_flag` / `director_clear_flag` / `director_relation_change` / `director_set_var` / `director_introduce_minor_npc` (canonical `npc_spawn` effect) / `director_local_crisis` (atomic primitive bundle). Plus enriched snapshot/prompt (real LLM drives in prod), M2a deterministic replay (frozen `director_cache`), M2b plot-ledger memory, M3 cadence, M5 30-year drift benchmark (the merge gate: `tests/test_scenario_director_drift_benchmark.py`). Core module: `src/scenario/narrative_director.py`.

### Three 六朝 scenario packages — authored, L4-ready, playable
御主 design: **one world preset, multiple per-arc packages** (like 三国 → 黄巾/官渡/三分). Anchored to the catalog `/Volumes/botsvault/06_material/六朝-XianTu-catalog-v1.md` (徐公子胜治 trilogy).

| dir `config/scenarios/<id>/` | 卷 | period | events | mandatory anchors | irreversible fact | branch / storylines |
|---|---|---|---|---|---|---|
| `liuchao` | 清羽记 (A) | 草原→太乙 | 11 | 6 | 段强之死 `duan_qiang_fallen` | 商人/依附 (path_merchant / path_retainer) |
| `yunlongyin` | 云龙吟 (B) | 临安/宋国官场 | 10 | 6 | 李师师灭族 `lishishi_clan_fallen` | 林冲/高俅 (ally_lin_chong / deal_gao_qiu) |
| `yangexing` | 燕歌行 (C) | 汉宫/汉国 | 10 | 5 | 手刃伪帝刘建 `liu_jian_slain` | 霍子孟善后 (huo_curbed / huo_empowered) |

Each: own `backbone` (in scenario.json) + `mandatory` anchors + a `branch` with two mutually-exclusive storylines + `narrative_fill` on key beats; all reuse the `liuchao` world_preset + generation_profile. Verified: all pass strict `validate_scenario_dir` + `load`; the L4 backbone gates engage on each (`tests/test_scenario_liuchao_l4.py`, parametrized over all 3); all play end-to-end through the real dispatch loop (see §3).

### 18+ / mature content direction — LOCKED at "直陈结构化" (frank structural)
御主 directive: encode the source's adult/dark themes **faithfully, frankly, as STRUCTURAL game facts/mechanics** — do NOT euphemize or scrub. Examples already in the packages: 采补双修 + 鼎炉 (women-as-cultivation-vessels) + 后宫 (liuchao); 御姬性役 + 瞑寂术奴役 + 阮香凝『珍品鼎炉』 (yunlongyin); 分筋错骨致残成光 + 挟质八岁幼主 (yangexing). Encoded as flags / relations / event mechanics + frank-but-non-explicit `description`/`narration_fallback`, each tagged「成人黑暗主题的结构事实，不含露骨描写」.
**The hard line (keep it):** NO sexually explicit / pornographic prose. The format is metadata, not erotica; fidelity to the source's adult nature does not require explicit text. Do NOT add a deeper engine subsystem for this unless asked — 直陈 structural is the agreed level.

---

## 2. Packaging & import

- A package = a zip of `<id>/scenario.json` + `<id>/timeline.json` (see authoring guide §1). It references a `world_preset` by id (presets in `config/presets/<id>/`, not embedded).
- **Built, signed packages live in `dist/scenarios/{liuchao,yunlongyin,yangexing}.zip`** (gitignored — build artifacts; the `config/scenarios/<id>/` dirs are the committed source of truth). Each has an embedded `fingerprint` (sha256) and imports as **verified**.
- Rebuild after editing source:
  ```python
  # for each id: load scenario.json+timeline.json, set scenario["fingerprint"]=compute_scenario_fingerprint(scenario,timeline),
  # zip as <id>/scenario.json + <id>/timeline.json (json indent=2, ensure_ascii=False) → dist/scenarios/<id>.zip
  ```
  (helpers: `src/scenario/scenario_fingerprint.compute_scenario_fingerprint`, layout mirrors `src/server/services/scenario_templates._zip_draft`.)
- Import path: `import_scenario_zip` (`src/server/services/scenario_import.py`) → validate → install under data root → enable → `load(id)`.

---

## 3. Playtest harness (game testing without server/LLM)

`tools/playtest_scenario.py` drives a package through the REAL scripted-scenario dispatch loop (production `_HANDLERS`) and prints the player-visible event log + mandatory coverage + storylines + flags. No server/frontend/LLM needed (shows the deterministic scripted spine; the L4 director adds emergent beats on top when an LLM key is configured).
```
.venv/bin/python tools/playtest_scenario.py <scenario_id> [months] [flag=val ...]
# e.g. liuchao 14 cheng_chose_merchant=1   (flag=val drives a branch)
```
Confirmed: all 3 packages fire every mandatory anchor in order, both branches resolve, storylines activate, and the 18+ structural facts land.

---

## 4. Running game server (LAN game testing) — CURRENTLY UP

- **A backend is running** for LAN web testing: `SERVER_HOST=0.0.0.0 SERVER_PORT=8088 .venv/bin/python src/server/main.py --scenario liuchao` (PID **42869** at handoff; log `/tmp/cws-server.log`). Serves the built SPA (`web/dist`) + API on one port.
- **URL: http://192.168.50.51:8088** (LAN). Status `idle` until a game is started from the UI (then a scenario becomes active). All 3 六朝 packages are bundled + selectable.
- Stop: `kill 42869`. Restart (e.g. after config change): same env+command. `--dev` instead would also spawn the Vite dev server (frontend at :5173); not needed here since `web/dist` is built.
- Build frontend if `web/dist` missing: `cd web && npm run build` (node_modules present).

### LLM = MiniMax — PENDING (open item)
The L4 director needs an LLM key to generate emergent beats; with none it degrades to the scripted spine (still fully playable). 御主 wants **MiniMax** (OpenAI-compatible API).
- Config lives in the **settings service** (`settings.json` in the data root `/Users/clawbot/.local/share/CultivationWorldSimulator-dev/52a0939b/`), or env seed `CWS_DEFAULT_LLM_BASE_URL` / `CWS_DEFAULT_LLM_API_KEY` / model names. Fields: `base_url`, `model_name`, `fast_model_name`, `api_key`, `api_format="openai"` (`src/config/settings_service.py`, `src/utils/llm/config.py`).
- MiniMax OpenAI-compatible: base_url `https://api.minimax.chat/v1` (CN) or `https://api.minimaxi.chat/v1` (intl); a text model (e.g. `MiniMax-Text-01`); api_format `openai`.
- **The API key is the user's to provide** (do NOT scan credential stores — that was correctly blocked). Recommended: 御主 enters MiniMax base_url/model/key in the running app's **Settings UI** (no secret through an agent). Then restart isn't required (settings read per-call), but a restart is safe.

---

## 5. Remaining work / backlog

### v1.9.x engine (deferred by 御主 — see `v1.9-remaining-work-codex-handoff.md`)
- `emit_director_event` (HARDEST remaining command: scheduling/priority Q6; do NOT reuse `world_event_trigger`; likely needs central scheduler first).
- `protected entity/faction IDs` (Q1): PREMATURE alone — no live command can harm an entity, so it'd gate nothing; ship it WITH a harm command (e.g. `director_kill_npc`), which is high-stakes + mostly fail-closed → low utility. Decide before building.
- central-scheduler rewrite (finer priority arbitration + ambient suppression); structured plot ledger (threads/secrets + LLM arc-summary).
- Pre-existing gap: normal scenario `set_flag` event effects don't persist across save/reload (`world.world_flags` never serialized); fix in `_sync_dispatch_state` or serialize it + save/reload test. (Director flag/relation/var/npc writes ARE persisted.)

### Content
- **Fidelity (剧情贴合) review of all 3 packages is 御主's** (人审 per division). The 剧情走向 layer was codex-reviewed already (all findings fixed @3a3b4590); per-beat fidelity/数值/取名/分支取舍 await 御主.
- Optional expansion: each book is currently a spine (~10 events). Can be deepened (more 章回 beats / more branches) — keep the 直陈 standard.
- v2: novel→scenario auto-generator should emit exactly this package format (authoring guide §9).

---

## 6. Process & invariants (KEEP)

- Per milestone: tight slice → **codex 二审 FOREGROUND** (`--resume --wait`; background jobs stalled this session — run foreground, kill+rerun if stalled) → FIX-FIRST → negative tests → full suite green (the drift benchmark is the merge gate) → ff-merge → push → spec log + memory.
- codex's recurring lessons: reuse real machinery (no reimplementation drift = false-green); fail-closed on anything not exactly modelled; persistence must land in the DURABLE store (`sc.state`), not ephemeral (`world.world_flags`); place new gating BEFORE any early-return guard; don't assert a root cause you can't prove.
- Scenario authoring gotchas: `mandatory:true` requires `anchor:true`; backbone predicates must be deterministic builtins (no `random_chance`); a `dynasty_id` event needs `trigger.at_region_id` in preset regions; `narrative_fill:true` needs `narration_fallback`; `persona_traits` must be preset persona ids; avatar `realm`/`location_region_id`/`sect_id` must resolve in the preset (sect_id nullable); generated narration is display-only (never in effects/conditions).
