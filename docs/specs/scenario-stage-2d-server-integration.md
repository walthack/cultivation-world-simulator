# Stage 2d D-d2 Spec — Server-Side Scenario Integration

Date: 2026-06-02
Author: Hassan
Status: Ready for codex implementation
Master signoff: 2026-06-02 22:12 SGT (Q1-Q6 全部拍板)

## Goal

把 scenario engine 从 pytest-only library 接成 live server 产品出口：CLI `--scenario <id>` 启动时 真激活，timeline 事件按 month tick 触发，roleplay 接管的 avatar 桥到 scenario state，事件 effect 落世界状态。

不在 D-d2 范围：API 入口、scenario 切换、scenario state 持久化。这些留 v0.3。

## Decision Matrix (御主 2026-06-02 拍板)

| Q | 决策 |
|---|---|
| Q1 hook 位置 | (a) 新增 phase 12.5「scenario timeline tick」，挂在 passive_effects 之后、autonomous_custom_creation 之前 |
| Q2 API 入口 | (a) D-d2 只做 CLI flag，不做动态 activate API |
| Q3 无 scenario 兼容 | 无 `--scenario` flag 时不 init dispatcher，phase 12.5 直接 return [] |
| Q4 roleplay 桥 | start / switch / stop roleplay 三个生命周期 hook 都同步 scenario state["controlled_avatar"] |
| Q5 state 持久化 | (b) D-d2 不做，留 v0.3 — active scenario 仅 server 进程内有效，restart 重新跑 timeline |
| Q6 多 scenario 切换 | 不适用（Q2 已锁 CLI-only） |

## Scope

### 1. CLI flag 激活

`src/server/main.py:198` 当前：
```python
ACTIVE_SCENARIO_ID = _read_cli_option("--scenario", None)
```
只赋值不用。改成：
- 若 `ACTIVE_SCENARIO_ID` 非 None，在 server bootstrap 阶段调 `src.scenario.scenario_loader.load(ACTIVE_SCENARIO_ID)` 得到 `ResolvedScenario`
- 把 `ResolvedScenario` 挂到 runtime（建议挂在 `GameSessionRuntime` 上：`runtime.scenario_resolved`），方便 simulator 取
- load 失败 → server 启动直接报错退出（不静默 fallback）
- 若 `ACTIVE_SCENARIO_ID` is None，runtime.scenario_resolved 保持 None，所有后续 hook noop

### 2. Game loop hook（phase 12.5）

新增 `src/sim/simulator_engine/phases/scenario.py`，导出 `phase_scenario_tick(world, ctx)`：
- 若 `world.runtime.scenario_resolved is None` → return []
- 否则用已有的 `src/scenario/event_dispatcher.py` 跑一轮 timeline 触发：
  - 输入：当前 year/month、scenario.state、scenario.triggered_events、living_avatars
  - 触发条件评估走 `condition_evaluator`，effect apply 走 `effect_applier`，event handler 派发走 `event_handlers/`
  - 返回新生成的 `Event` 列表，加进 ctx.events

在 `src/sim/simulator_engine/simulator.py` step() 第 12 步（passive_effects）之后、第 13 步（autonomous_custom_creation）之前插入：
```python
# 12.5 Scenario timeline tick
ctx.add_events(scenario_phase.phase_scenario_tick(self.world, ctx))
```

scenario.state 在 runtime 上保持单例（per server process），dispatcher 自己维护 triggered_events set 防重复触发。

### 3. Roleplay bridge（controlled_avatar 同步）

`src/server/services/roleplay_service.py` 三个写 `session["controlled_avatar_id"]` 的位置都加 hook 同步到 scenario state：
- `start_roleplay(runtime, avatar_id)` → 写完 session 后调 `_sync_scenario_controlled_avatar(runtime, avatar_id)`
- `stop_roleplay(runtime, avatar_id)` → clear 之后调 `_sync_scenario_controlled_avatar(runtime, None)`
- 其它会改 controlled_avatar_id 的位置（begin_roleplay_choice / begin_roleplay_conversation / finish_roleplay_choice_wait）也要 sync

新加 helper：
```python
def _sync_scenario_controlled_avatar(runtime, avatar_id: str | None) -> None:
    resolved = getattr(runtime, "scenario_resolved", None)
    if resolved is None:
        return
    resolved.state["controlled_avatar"] = avatar_id  # 或 None
```

`ResolvedScenario` 当前没 state 字段（见 `src/scenario/scenario_loader.py:61`），D-d2 要补：
- 给 `ResolvedScenario` 加 `state: dict[str, Any] = field(default_factory=dict)`
- load 时初始化为空 dict
- dispatcher / effect_applier 读 `resolved.state["controlled_avatar"]`，对接已有的 `controlled_avatar_is` predicate 和 `{controlled_avatar}` placeholder（Stage 2c-1 已落）

### 4. 无 scenario 兼容

- 启动 server 不带 `--scenario`：`ACTIVE_SCENARIO_ID = None`，dispatcher 不 init，phase 12.5 直接 return []，roleplay sync helper 看到 None 也 noop
- 现有所有 pytest（109 scenario + 1500+ 全栈）必须不变绿
- 现有 default 游戏体验完全不破坏

## Files to touch

新增：
- `src/sim/simulator_engine/phases/scenario.py` — phase_scenario_tick
- `tests/test_scenario_d2d_server_integration.py` — server bootstrap + phase tick + roleplay sync 三层 E2E

修改：
- `src/server/main.py` — 把 ACTIVE_SCENARIO_ID 真正消费，scenario_resolved 挂 runtime
- `src/scenario/scenario_loader.py` — `ResolvedScenario` 加 `state: dict` 字段，load 初始化
- `src/sim/simulator_engine/simulator.py` — step() 插 phase 12.5
- `src/sim/simulator_engine/phases/__init__.py` — 导出 scenario phase（如有 phases 注册表）
- `src/server/services/roleplay_service.py` — 3 处 controlled_avatar_id 写入加 sync helper
- 可能 `src/server/runtime/*` — runtime 加 `scenario_resolved` 字段

ADR：
- `docs/adr/ADR-006-scenario-stage-2d-server-integration.md` — codex 写

## Acceptance criteria

1. `uvicorn` / `python src/server/main.py --dev --scenario liuchao` 启动后 `runtime.scenario_resolved` 非 None
2. `python src/server/main.py --dev`（无 flag）启动后 `runtime.scenario_resolved is None`，行为零变化
3. 模拟器跑到 year 1 month 1，liuchao-opening 事件被触发（看 ctx.events 或 world flag）
4. roleplay 接管 cheng-zongyang 后，跑到 year 1 month 2，cheng-zongyang-arrives-at-linan-gate 触发，wang-zhe-arrives-at-linan-gate 不触发
5. roleplay 切到 wang-zhe，phase 12.5 下一 tick 看到 wang-zhe 的事件触发（验 controlled_avatar bridge）
6. `--scenario` flag 指了不存在的 scenario_id，server 启动报错退出
7. pytest 109 scenario 测试不回归；新加 server integration 测试 ≥ 4 个
8. ADR-006 落 `docs/adr/`，说明 phase 位置选择 / no-scenario noop 策略 / roleplay 桥时机

## Out of scope（D-d2 不做，留后续）

- POST /api/v1/command/scenario/activate（API 入口）→ v0.3
- save/load 写 scenario.state + triggered_events → v0.3
- 多 scenario 切换语义 → 不适用
- Scenario engine 触发的事件再触发 NPC 反应链 → 已有 event 派发，应该自然 work，不需要专门做
- D-d1 第二个示例 scenario 内容（simple_demo / 三国 mock）→ 紧接 D-d2 做

## 工程量预估

~3-4 天 codex 实装（含 ADR + tests）。
