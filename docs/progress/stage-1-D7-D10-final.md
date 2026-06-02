# Stage 1 D7-D10 Final Report

## Summary

- D7: ✅ complete
- D8: ✅ complete
- D9: ⚠️ scenario data complete; uvicorn `--scenario` CLI wiring blocked by action_safety
- D10: ✅ in-process E2E complete

## D7

Implemented:

- `src/scenario/event_dispatcher.py`
- `src/scenario/condition_evaluator.py`
- `src/scenario/effect_applier.py`
- `src/scenario/state_access.py`

Validation:

- 13 predicate tests pass.
- 17 effect tests pass.
- `economy_event` is no-op + log.

## D8

Implemented:

- `src/scenario/event_handlers/main_event_handler.py`
- `src/scenario/event_handlers/character_introduction_handler.py`
- `src/scenario/event_handlers/relation_change_handler.py`
- `src/scenario/event_handlers/world_event_handler.py`
- `src/scenario/event_handlers/side_event_handler.py`
- `src/scenario/event_handlers/ending_handler.py`

Choice decision:

- Added one `ScenarioEventChoiceScenario` adapter.
- Reuses existing `resolve_single_choice()` when a real CWS controlled avatar object is available.
- Runtime-only/default path uses `default_outcome`; if absent, FIRST_OPTION.
- No parallel scenario choice model was introduced.

Validation:

- 6 independent handler tests pass.

## D9

Implemented:

- `config/scenarios/liuchao/scenario.json`
- `config/scenarios/liuchao/timeline.json`
- `config/presets/liuchao/sects.json`
- `config/presets/liuchao/realms.json`
- `config/presets/liuchao/personas.json`
- `config/presets/liuchao/goldfingers.json`

Liuchao minimal data:

- Starter avatars: 程宗扬, 王哲, 小紫.
- Timeline events: `liuchao-opening`, `wang-zhe-passes-jiuyang`.
- Y2.M3 王哲传功 event included.
- Nine-realm order included in liuchao preset.

Validation:

```text
{'scenario_id': 'liuchao', 'preset_id': 'liuchao', 'avatar_count': 3, 'events': ['liuchao-opening', 'wang-zhe-passes-jiuyang']}
```

Blocked item:

```text
python3.14 -m uvicorn src.server.host_app:app --host 127.0.0.1 --port 8003 --scenario liuchao
Error: No such option '--scenario'.
```

Reason: implementing uvicorn/server `--scenario` support requires changing `src/server/main.py` or related server files, which is outside this task's action_safety scope.

## D10

Implemented:

- `tests/test_scenario_e2e_liuchao.py`

E2E path:

- Load liuchao scenario.
- Treat 程宗扬 as controlled avatar.
- Dispatch Y1.M1 opening.
- Dispatch Y2.M3 王哲传功.
- Resolve choice through Stage 1 runtime/default path.
- Apply effects.
- Verify state changes.

Validation:

```text
tests/test_scenario_e2e_liuchao.py::test_liuchao_wang_zhe_passes_jiuyang_e2e PASSED
```

## Full Verification Loop

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/cws-stage1-data pytest tests/test_scenario_*.py -v 2>&1 | tail -30
```

Actual response:

```text
tests/test_scenario_effect_applier.py::test_lose_skill PASSED            [ 40%]
tests/test_scenario_effect_applier.py::test_gain_stat PASSED             [ 42%]
tests/test_scenario_effect_applier.py::test_lose_stat PASSED             [ 44%]
tests/test_scenario_effect_applier.py::test_set_stat PASSED              [ 46%]
tests/test_scenario_effect_applier.py::test_gain_item PASSED             [ 48%]
tests/test_scenario_effect_applier.py::test_lose_item PASSED             [ 51%]
tests/test_scenario_effect_applier.py::test_set_flag PASSED              [ 53%]
tests/test_scenario_effect_applier.py::test_clear_flag PASSED            [ 55%]
tests/test_scenario_effect_applier.py::test_npc_join PASSED              [ 57%]
tests/test_scenario_effect_applier.py::test_npc_leave PASSED             [ 60%]
tests/test_scenario_effect_applier.py::test_npc_die PASSED               [ 62%]
tests/test_scenario_effect_applier.py::test_npc_set_realm PASSED         [ 64%]
tests/test_scenario_effect_applier.py::test_npc_set_relation PASSED      [ 66%]
tests/test_scenario_effect_applier.py::test_relation_change PASSED       [ 68%]
tests/test_scenario_effect_applier.py::test_world_event_trigger PASSED   [ 71%]
tests/test_scenario_effect_applier.py::test_economy_event_noop PASSED    [ 73%]
tests/test_scenario_effect_applier.py::test_missing_npc_reference_raises_and_rolls_back PASSED [ 75%]
tests/test_scenario_effect_applier.py::test_unknown_effect_raises PASSED [ 77%]
tests/test_scenario_event_handlers.py::test_main_event_handler_uses_default_outcome_choice PASSED [ 80%]
tests/test_scenario_event_handlers.py::test_character_introduction_handler_spawns_npc PASSED [ 82%]
tests/test_scenario_event_handlers.py::test_relation_change_handler_applies_relation_delta PASSED [ 84%]
tests/test_scenario_event_handlers.py::test_world_event_handler_applies_effects PASSED [ 86%]
tests/test_scenario_event_handlers.py::test_side_event_handler_applies_effects PASSED [ 88%]
tests/test_scenario_event_handlers.py::test_ending_handler_sets_runtime_ending PASSED [ 91%]
tests/test_scenario_stage1.py::test_default_preset_sect_pool_preserves_current_ids PASSED [ 93%]
tests/test_scenario_stage1.py::test_default_preset_realm_order_preserves_current_order PASSED [ 95%]
tests/test_scenario_stage1.py::test_liuchao_preset_changes_generated_name_style PASSED [ 97%]
tests/test_scenario_stage1.py::test_scenario_loader_loads_sample_scenario PASSED [100%]

============================== 45 passed in 1.35s ==============================
```

## Commit-Ready Files

- `config/presets/liuchao/goldfingers.json`
- `config/presets/liuchao/personas.json`
- `config/presets/liuchao/realms.json`
- `config/presets/liuchao/sects.json`
- `config/scenarios/liuchao/scenario.json`
- `config/scenarios/liuchao/timeline.json`
- `src/scenario/__init__.py`
- `src/scenario/scenario_loader.py`
- `src/scenario/state_access.py`
- `src/scenario/condition_evaluator.py`
- `src/scenario/effect_applier.py`
- `src/scenario/event_dispatcher.py`
- `src/scenario/event_handlers/__init__.py`
- `src/scenario/event_handlers/main_event_handler.py`
- `src/scenario/event_handlers/character_introduction_handler.py`
- `src/scenario/event_handlers/relation_change_handler.py`
- `src/scenario/event_handlers/world_event_handler.py`
- `src/scenario/event_handlers/side_event_handler.py`
- `src/scenario/event_handlers/ending_handler.py`
- `tests/test_scenario_condition_evaluator.py`
- `tests/test_scenario_effect_applier.py`
- `tests/test_scenario_event_handlers.py`
- `tests/test_scenario_e2e_liuchao.py`
- `docs/progress/stage-1-D7-progress.md`
- `docs/progress/stage-1-D8-progress.md`
- `docs/progress/stage-1-D9-progress.md`
- `docs/progress/stage-1-D10-progress.md`
- `docs/progress/stage-1-D7-D10-final.md`
