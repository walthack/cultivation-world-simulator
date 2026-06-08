# v1.3 Spec — Scenario-Aware Generation

## Status
Draft — 2026-06-08 (Hassan). Prereq: v1.2.3 game-loop-pickle-fix ✅.

> **v1.3 的定义:Scenario-aware generation,NOT social simulation。**
> v1.3 只做「让生成层吃 scenario context」(数据源 + LLM prompt 注入)。任何 simulator lifecycle 架构改动(自动社交 phase 等)**不属于 v1.3**,拆到 **v1.4 Social Simulation Phase**。dialogues/relationships=0 在 v1.3 内**只做 diagnosis(查清根因 + 文档化 + test 证明现状),不做实现修复**。

## Context / 诊断

v1.2.3 已证明 **simulator tick 能稳定跑**（liuchao sweep 58 月、226 events、0 pickle）。但同一 sweep 的数据暴露了真正的问题:**scenario 目前只控制「起步层」(scripted 角色 / 朝代事件 / scenario badge),「生成层」几乎完全不吃 scenario context。**

sweep 量化证据(liuchao,58 月):
- 六朝/历史词 vs 泛修真词 ≈ **13 : 183**(~7%)
- 宗派全是 default 池(凌霄剑宗 / 万兽魔山 / 厚土玄宫),**零历史势力**
- 地图全是 default 修真地名(无边碧海 / 西域流沙 / 沧海遗迹);建康 / 洛阳 / 长安各仅 1 次
- NPC 长期目标全 default 修真(突破元婴 / 称霸碧海 / 证道金丹)
- dialogues = 0,relationships = 0

### 根因(源码调研)
1. **数据源层**:存在 `resolve_source(...)` / generation_sources 机制(scenario 可指定某数据池用 scenario 版),已接 NPC 名(`name_generator.py:87`、`avatar_init.py:165`)、sect(`sect_manager.py`)、region(loader)。但**默认走 default preset 池**,且 sect 只用 scenario 数据去重、不覆盖属性(名/宗旨/技法)。
2. **LLM 叙事层完全不吃 scenario context**:persona/backstory(`long_term_objective.py:70`)、长期目标、事件叙事(`story_teller.py:59`、`story_event_service.py:81`)的 prompt 只注入 `world_lore` + avatar_info,**无 scenario background / style / 术语风格**。
3. **`generation_profile` 通道太窄**:仅 3 字段(`use_scripted_only` / `random_npc_count` / `random_sect_count`),且**只有 `init_flow.py:53` 读**;`avatar_init` / `sect_manager` / `story_teller` / `long_term_objective` / `backstory` 都没读。缺 narrative context 类字段。
4. **dialogues/relationships = 0 是独立架构缺口**:对话系统(`mutual_action/conversation.py:38`)需玩家或 `Talk` action 主动触发;simulator lifecycle **没有自动社交 phase**。关系仅由生育(`birth.py`)和显式创建(父子/师徒)驱动,**无陌生 NPC 间自动对话 + 关系演化**。

## Goal

**一个 scenario package 应同时控制运行时生成的两个正交维度:**

- **Generation Source（数据源）** — 运行时生成的 NPC 名/persona、sect、region 从 scenario 声明的数据池取(扩展现有 `resolve_source` 机制)。
- **Narrative Context（叙事上下文）** — LLM 生成(persona/backstory、长期目标、事件叙事)的 prompt 注入 scenario 的 background / style / 术语风格。

> 写成**通用能力**:任意 scenario package 通过 JSON 声明即可控制 generation source + narrative context。**六朝(liuchao)只是验证 example,三国 mock 同机制生效,无 scenario(default sandbox)行为不变。** 不做任何六朝 hardcode。

## Scope（6 项,映射两维度）

| # | 范围 | 维度 | 现状 | v1.3 目标 |
|---|---|---|---|---|
| 1 | NPC name + persona 生成用 scenario preset | Source + Narrative | name 有 hook 但默认 default;persona LLM 不吃 scenario | scenario 声明 npc_names/persona 源 → 生成器取之;persona prompt 注入 scenario context |
| 2 | sect/faction 生成用 scenario preset | Source | 仅去重用 scenario,属性全 default | scenario sects.json 覆盖 sect 名/宗旨/技法 |
| 3 | map/region 命名用 scenario preset | Source | 纯加载 default regions.json,无覆盖 | scenario regions.json 覆盖地名 |
| 4 | 事件叙事 prompt 注入 scenario background/style | Narrative | prompt 只有 world_lore | story_teller / story_event_service prompt 注入 scenario narrative_context |
| 5 | NPC 长期目标注入 scenario context | Narrative | LLM 不读 scenario | long_term_objective prompt 注入 scenario context |
| 6 | **查清** dialogues/relationships = 0 根因(**diagnosis only**) | (诊断) | 无自动社交 phase | 写明根因 + test 证明现状;**实现修复移 v1.4** |

## 设计决策

### D1 — `generation_profile` 扩展为 scenario→生成器的统一通道
现状只 3 字段、只 init_flow 读。扩展 schema + 让它经 `world.scripted_scenario` / `run_config` 流到各生成器:
```
generation_profile:
  use_scripted_only / random_npc_count / random_sect_count   # 现有
  generation_sources:        # 新:每类数据源选 scenario|default|mixed
    npc_names: scenario|default|mixed
    sects:     scenario|default|mixed
    regions:   scenario|default|mixed
  narrative_context:         # 新:注入 LLM prompt
    background:  <世界观/时代背景文本>
    style:       <叙事风格,如 "半文半白章回体">
    terminology: <术语倾向 hints,如 历史官职 vs 修真境界>
```
**所有字段 optional**;缺省 = 当前 default 行为(向后兼容,守 no-scenario sandbox)。

### D2 — Generation Source Control（数据池）
- `avatar_init` / `name_generator`:按 `generation_sources.npc_names` 决定取 scenario 还是 default 名池。
- `sect_manager`:scenario `sects.json` 不仅去重,**提供新 sect 的属性**(名/宗旨/技法倾向)。
- region:scenario `regions.json` 覆盖地名池。
- 每个生成器从统一通道(D1)读 generation_sources,**不各自硬接**。

### D3 — Narrative Context Injection（LLM）
- 新增统一 helper `build_scenario_context_block(world) -> str`,把 `narrative_context`(background/style/terminology)渲染成 prompt 片段。
- 注入点:`long_term_objective.py`(目标 + persona)、`story_teller.py` / `story_event_service.py`(事件叙事)。
- 与现有 `world_lore` 通道协同(world_lore 是世界设定,narrative_context 是 scenario 叙事风格指令)。
- **no-scenario 时该 block 为空**,prompt 退回当前形态。

### D4 — dialogues/relationships = 0 诊断（diagnosis only;实现移 v1.4）
**v1.3 不加任何 simulator lifecycle phase。** 只做诊断 + 文档 + test:
- **查清并写明根因**:当前系统**没有自动社交 phase**——`Conversation` 仅由玩家或 `Talk` action 主动触发,关系仅由生育(`birth.py`)+ 显式创建(父子/师徒)驱动;故 50+ 月无玩家交互的 sweep 必然 0 dialogues / 0 relationship changes。这是**预期现状,不是 bug**。
- **补 test 证明现状**:断言「无自动社交 phase 时,纯 NPC sweep 的 dialogues 维持 0、relationship changes 仅来自生育/显式创建」,锁住当前行为,防止后续误判为回归。
- **真正的自动社交实现(新增 lifecycle phase:同 region NPC 按 friendliness/概率自动发起 Conversation + 关系演化)→ 拆到 v1.4 Social Simulation Phase**,属 simulator 架构改动,不混进 v1.3 的 generation/prompt 注入。

## 验收标准（v1.3 RC target — liuchao sweep 50+ months）

> **这些是 v1.3 RC target,不是永久标准**(御主 2026-06-08 定)。用统一 sweep 脚本前后对比(基线 = v1.2.3 sweep:terms ~7% / sect 0% scenario / dialogue 0 / relationship 0)。

1. **scenario/historical terms ratio ≥ 40%**:events content 里 scenario/历史词占比从 ~7% 提到 ≥ 40%。
2. **sect names from scenario pool ≥ 60%**:运行时生成的 sect 名来自 scenario pool 占比 ≥ 60%;default 池地名出现率显著下降。
3. **dialogues > 0 / relationship changes > 0** — ⚠️ **不在 v1.3 RC target 内**:v1.3 对这两项只做**诊断 + test 证明现状**(无自动社交 phase → 纯 NPC sweep 必然 0,属预期)。真正做到 `dialogues > 0 / relationship changes > 0` 是 **v1.4 Social Simulation Phase** 的验收目标(D4 实现已拆出)。
4. **no-scenario sandbox: zero regression**:`--scenario default`(及无 scenario)与 v1.2.3 **零 diff**,回归测试守护(每个 milestone 至少 1 个 negative test)。

## 通用性保证（非六朝专属）
- 全部机制走 scenario package 的 `generation_profile` 声明,**零六朝 hardcode**。
- 第二 example(三国 mock)同 sweep 应显示三国辨识度提升 → 证明通用。
- default sandbox = scenario 缺省 = 当前行为(回归守护)。

## 非目标（v1.3 之后的版本）

**v1.4 Social Simulation Phase**(御主 2026-06-08 定;属 simulator 架构改动,与 v1.3 的 generation/prompt 注入隔离):
- simulator lifecycle 新增**自动社交 phase**:同 region NPC 按 friendliness / 概率自动发起 `Conversation` + 关系演化。
- 验收目标:`dialogues > 0` / `relationship changes > 0`。
- v1.3 只为它做了诊断 + 现状 test(见 D4),**不碰 lifecycle**。

**后续 Content Depth / World Polish**(原 v1.4,版本号因 Social Simulation 插入而顺延,待御主重排):
- 六朝/三国 scripted 内容厚度(更多事件/角色/历史势力数据)。
- 地图可视化 / 势力外交 / 宗派体验打磨。
- scenario editor UI。

> v1.3 只建**机制**(scenario 控制 generation source + narrative context);内容厚度、社交模拟都不在内。

## 实施顺序（codex 开发,每 phase 配 negative test + sweep 量化对比）
1. **Phase 1** — D1:`generation_profile` schema 扩展 + 流到各生成器(通道先通)。
2. **Phase 2** — D2:Generation Source Control(name / sect / region 数据池)。
3. **Phase 3** — D3:Narrative Context Injection(LLM prompt)。
4. **Phase 4** — D4:dialogues/relationships **诊断 only**(查清根因 + 文档化「当前无自动社交 phase」+ test 证明现状;**实现移 v1.4 Social Simulation Phase**)。

## 验收前提
- sweep 脚本固化为可复跑的量化工具(基线 vs v1.3 对比),含 terms ratio / sect-source / dialogue-relationship 计数。
- LLM 用 minimax M2.7-highspeed(与 v1.2.3 验收一致)。
