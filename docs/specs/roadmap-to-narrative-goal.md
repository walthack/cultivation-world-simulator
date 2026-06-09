# CWS Scenario Engine — Roadmap to Narrative Goal

Draft — 2026-06-09 (Hassan)。从「当前 v1.3 已发布」推到**总目标**,每版细化到 milestone。

## 总目标

> CWS 新建世界时**导入一个剧本设定**,用 LLM **根据剧本故事自动生成对应世界**,并能**进一步发展剧情 + 扩展人物关系**。

4 个能力链:① 导入剧本 ② 世界按剧本生成(骨架+质感) ③ 剧情自动发展 ④ 人物关系扩展。

## 已达成（v0.5 → v1.3）

| 链 | 能力 | 状态 |
|---|---|---|
| ① | Discovery / .zip Import / Creator Toolkit / Mod Platform(v0.5-v1.0) | ✅ |
| — | Scenario Engine 架构:timeline + condition DSL + 17 effect + 6 event types + v0.2 Schema | ✅ |
| ② | **Source Control**(v1.3):NPC 名/sect/region 按剧本池(程绾/太乙真宗/建康) | ✅ 骨架是剧本的 |
| ② | **Narrative Injection**(v1.3):prompt 通了但 LLM 没遵循(hierarchy 90% 修仙) | ⚠️ 部分 |

## Roadmap（细化到 milestone）

### v1.4 — Scenario-Aware Simulation Text + Social Simulation
补 ②质感 + ④关系(近 gap)。
- **M1** Mechanical Event Localization:sect_decider / 结算 / 突破 / 移动 / 招募 文本 scenario 化(占 events 51%)
- **M2** Narrative 强化:scenario-aware world_lore 替换 + 术语映射(灵石→资财、宗门→门阀)+ prompt 权重/位置(修 v1.3 hierarchy)
- **M3** Social Simulation Phase:lifecycle 加自动社交(同 region NPC 自动 Conversation + 关系演化)
- **M4** 关系进 LLM 决策 context(NPC 行为/对话考虑关系)
- 验收:terms ratio 实质提升(localization 后重定目标)+ dialogues/relationships > 0
- 产出:**长得像、读着像、人物会动**的剧本世界

### v1.5 — Content Depth / World Polish
- **M1** 六朝/三国 scripted 内容厚度(更多事件/角色/历史势力)
- **M2** 地图可视化 / 势力外交 / 宗派体验
- **M3** Scenario Editor UI(玩家不手写 JSON)

### v1.6 – v1.9 — 剧情能力阶梯（③ 剧情自动发展,渐进暴露风险）
> 把「剧情自动发展」从 scripted 渐进到 LLM 自主,每级一版、可玩可验。**架构 spike 在 v1.4/v1.5 期间并行**(探 L3/L4 的记忆/连贯/约束方案,降低后期未知)。

- **v1.6 — L1 剧情分支化**:timeline 支持条件分支(按世界状态选不同剧情线)。仍 scripted,但脱离单线。工程可控。
- **v1.7 — L2 剧情细节 LLM 填充**:timeline 事件是「骨架」(发生什么),LLM 据世界状态生成具体叙事/对话文本。走向仍 scripted,表现 LLM 化。
- **v1.8 — L3 剧情衔接 LLM 生成**:剧本只写关键**锚点**事件,LLM 生成锚点之间的过渡剧情。剧本定大走向,LLM 填中间。半 AI。
- **v1.9 — L4 剧情自主演化(完整 Narrative Director)**:LLM 理解剧本脉络 + 世界状态,自主生成符合走向的剧情(超越预设锚点)。**真 narrative AI 攻坚 —— ③ 达成,总目标灵魂落地。**
  - 设计挑战:剧情连贯/长程记忆、剧本约束 vs 涌现、director 与模拟引擎协调、成本/延迟。

### v2 — Novel-to-Scenario（① 的「自动」生成）
- 喂小说/剧本文本 → LLM 抽取角色/势力/地理/关系/timeline → 自动生成 scenario JSON
- 与 v1.8/v1.9 共享「剧本理解」内核;依赖 v0.7 LLM Authoring 雏形

## 离总目标进度

| 能力链 | v1.3 now | v1.4 | v1.5 | v1.6 | v1.7 | v1.8 | v1.9 | v2 |
|---|---|---|---|---|---|---|---|---|
| ① 导入剧本 | ✅ | | Editor UI | | | | | **自动生成** |
| ② 骨架按剧本 | ✅ | | | | | | | |
| ② 质感按剧本 | ⚠️ | ✅ | | | | | | |
| ④ 人物关系 | ❌ | ✅ | | | | | 深化 | |
| ③ 剧情自动发展 | ❌ | | | L1 分支 | L2 填充 | L3 衔接 | **L4 自主** | |

## 关键判断

- **断层已填平**:v1.5(polish)→ v1.6(L1 分支,仍 scripted)平滑过渡,不再从打磨直跳 AI 攻坚。
- **风险渐进**:v1.6/v1.7 工程可控、快速交付;v1.8/v1.9 才碰真 narrative AI,且届时已有 L1-L2 剧情基建垫底。
- **架构 spike 必须早做**:v1.4/v1.5 期间并行探 L4 的记忆/连贯/约束方案 —— 这是整个目标最大未知,不能等到 v1.9 才开始想。
- **v1.9(L4 Narrative Director)是总目标的灵魂**:从「世界模拟器 + 剧本皮肤」跃迁到「剧本驱动的故事引擎」的关键一跳。
- v1.0-v1.3 把地基+骨架打牢(顺序对);v1.4-v1.5 让世界「像+动」;v1.6-v1.9 让剧情「会写」;v2 让世界「自动从小说长出来」。
