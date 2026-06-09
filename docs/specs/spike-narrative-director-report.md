# v1.9 Narrative Director Spike Report

Date: 2026-06-09

Status: architecture analysis complete; standalone POC implemented; live MiniMax generation blocked by the execution sandbox's DNS/network policy. No model responses are fabricated below.

## 1. Architecture analysis

### Current scripted flow

1. `scenario_loader.load()` reads `scenario.json` plus optional `timeline.json`, validates both, and returns `ResolvedScenario.timeline` (`src/scenario/scenario_loader.py:737-755`). Timeline validation requires unique IDs, a known event type, and an integer `trigger.year/month`; it also validates `requires_events` and `blocks_events` references (`src/scenario/scenario_loader.py:690-734`).
2. Scenario injection stores a copy of that timeline and initial runtime state on `world.scripted_scenario` (`src/scenario/injector.py:11-60`). The runtime container currently holds the static timeline, generation profile, mutable scenario state, triggered IDs, and a short dispatch log (`src/scenario/state.py:7-14`).
3. One simulator step owns one month. It accumulates all phase results in `SimulationStepContext.events` (`src/sim/simulator_engine/context.py:11-40`). The scripted scenario phase runs after passive/world effects and before autonomous creation and random events (`src/sim/simulator_engine/simulator.py:88-100`).
4. `phase_scripted_scenario_tick()` builds a dispatch view over live world/scenario state, creates `EventDispatcher(sc.timeline)`, dispatches the current month, syncs runtime bookkeeping, and converts fired scenario records to normal `Event` objects (`src/sim/simulator_engine/phases/scripted_scenario.py:49-111`).
5. `EventDispatcher.dispatch_month()` scans the complete timeline in author order. An event fires once only when it is scheduled for the exact current year/month, is not triggered or blocked, has all required events, and passes the condition DSL. It then invokes the type handler, records blocks/log data, and returns the fired records (`src/scenario/event_dispatcher.py:39-117`).
6. Handlers apply deterministic effects or resolve a bounded choice. Main/world events can use the unified single-choice engine; otherwise effects are applied directly (`src/scenario/event_handlers/main_event_handler.py:28-119`, `src/scenario/event_handlers/world_event_handler.py:9-13`). Effects include flags, stats, items, NPC state, relations, scenario variables, and registered mod effects (`src/scenario/effect_applier.py:99-186`).
7. At step end, all mechanical and scenario events are deduplicated by ID, enriched, written through `world.event_manager`, logged, and then the month advances (`src/sim/simulator_engine/finalizer.py:16-56`).

The Six Dynasties package demonstrates the current model: fixed dated events such as the opening, three roleplay-specific Lin'an arrivals, Wang Zhe's Nine Yang transfer, regional musters/edicts, and clan/tax developments live in `config/scenarios/liuchao/timeline.json`. This is a deterministic schedule with conditional gates, not a planner. The existing narrative prompt context is only `background/style/terminology` from `generation_profile` (`src/scenario/narrative_context.py:13-60`); it is useful input material but is not long-term plot memory.

### Extension points

- **Best tick-level hook:** add a future `phase_narrative_director_tick(world, ctx)` beside the scripted phase in the simulator phase list. It can see the current month's mechanical results through `ctx.events` and return normal `Event` objects without bypassing finalization. The orchestration boundary is explicit at `src/sim/simulator_engine/simulator.py:88-100`.
- **Best state adapter:** extend the dispatch-state/world-snapshot builder pattern at `src/sim/simulator_engine/phases/scripted_scenario.py:49-70`. It already exposes world, scenario runtime, roleplay session, flags, NPCs, and relations in one place.
- **Best deterministic application path:** translate an accepted director proposal into the existing event/effect vocabulary and execute it through handlers plus `apply_effects`, rather than allowing model-authored code or direct world mutation (`src/scenario/event_handlers/main_event_handler.py:114-119`, `src/scenario/effect_applier.py:206-230`).
- **Best event sink:** return events into `SimulationStepContext`; finalization already provides one deduplication, persistence, logging, and month-advance boundary (`src/sim/simulator_engine/context.py:36-40`, `src/sim/simulator_engine/finalizer.py:21-55`).
- **Existing but unsuitable late hook:** `on_step` is dispatched only after `finalize_step()` and month advancement (`src/sim/simulator_engine/simulator.py:126-132`). It is too late for same-tick ordering/persistence and should not become the Director integration point.

A clean production hook should therefore be a pure proposal boundary:

`snapshot -> Director proposal -> schema/ID/condition validation -> deterministic command/effect application -> Event list -> ctx.events`

The Director must not receive `world` as a mutable capability. It should return validated data containing narrative text, involved entity IDs, preconditions, priority, expiry, and a constrained effect/command plan. Invalid or stale proposals should be rejected or deferred without partially mutating the world.

## 2. Memory and coherence recommendation

Use a layered context rather than replaying raw event history:

1. **Immutable backbone:** a compact scenario thesis, themes, prohibited outcomes, key factions/characters, and a small set of mandatory/optional anchors. Version and hash this content.
2. **Authoritative world snapshot:** current time; living/dead/absent entities; faction control/resources; locations; relationship edges; active wars/crises; relevant flags; and pending player decisions. Values must be IDs plus short localized labels, not prose-only claims.
3. **Plot ledger:** unresolved threads, promises/debts, secrets and who knows them, completed anchors, blocked branches, and causal facts. Each fact needs a stable ID, source event ID, start/end time, confidence, and invalidation status.
4. **Rolling event digest:** keep the last few accepted narrative events verbatim, then progressively summarize older periods by arc/decade. Preserve irreversible facts separately so summarization cannot resurrect dead characters or undo territorial changes.
5. **Director plan state:** current arc, target tension, intended next beat, cooldowns, and why the last proposal was accepted/rejected. This prevents repeatedly proposing the same kind of event.

At each Director turn, retrieve only ledger entries relevant to involved parties, locations, active threads, and nearby anchors. After generation, run deterministic checks first, then a separate low-cost consistency critic if needed. Store the accepted normalized event and ledger delta, not hidden chain-of-thought. Periodically rebuild summaries from authoritative accepted events to limit accumulated summarization error.

## 3. Director-Simulator coordination

The Simulator should remain the sole tick owner and sole mutation coordinator. The Director is an asynchronous planner that can propose work but cannot advance time or write the world directly.

Recommended monthly order:

1. Execute mechanical phases that establish current facts: actions, interactions, deaths, births, passive effects.
2. Fire due scripted hard anchors. Anchors have the highest narrative priority and may declare protected preconditions/outcomes.
3. Build a post-anchor snapshot and ask the Director only when a cadence/budget/trigger policy says a narrative beat is needed.
4. Validate the proposal against current entity state, backbone constraints, duplicate/cooldown rules, and allowed effect types.
5. Apply accepted Director commands serially through the same mutation lane as all other world changes; append resulting events to `ctx.events`.
6. Run lower-priority ambient/random phases, suppressing or rescheduling events that conflict with a protected anchor/director beat.
7. Finalize once through the existing event sink.

Suggested priority classes are: `hard_anchor > player_pending_choice > accepted_director_main > mechanical_major > director_side > ambient_random`. Priority should settle scheduling conflicts, not silently overwrite already-applied mechanics. If a mechanical event invalidates a proposal between planning and application, reject it using a snapshot revision/precondition check and retry in a later tick.

LLM latency should not hold the simulation lock indefinitely. A production design should either plan one or more beats ahead from a revisioned snapshot, or impose a short timeout and skip the Director for that month. Only the final validation/application section needs serialization.

## 4. POC implementation and execution result

`tools/spike_narrative_director.py` is standalone and imports no `src` modules. It:

- calls `https://api.minimaxi.com/v1/chat/completions` with `MiniMax-M2.7-highspeed`;
- reads `MINIMAX_API_KEY` from the environment, falling back to `~/.openclaw/.env`;
- sends the Six Dynasties backbone, compact world snapshot, and strict six-field JSON contract;
- runs four rolling turns with `max_tokens=400` and feeds each accepted event back into the conversation;
- validates JSON shape and prints a lightweight backbone/duplicate/terminal-entity coherence check.

Compilation succeeded with:

```text
python3 -m py_compile tools/spike_narrative_director.py
```

The live run was attempted on 2026-06-09 with a present API key. The environment blocked DNS before any HTTP response was received:

```text
RuntimeError: MiniMax request failed: [Errno 8] nodename nor servname provided, or not known
```

An independent attempt through the locally installed OpenClaw MiniMax provider failed at the same boundary:

```text
[provider-transport-fetch] ... code=ENOTFOUND ... message=getaddrinfo ENOTFOUND api.minimaxi.com
FailoverError: LLM request failed: DNS lookup for the provider endpoint failed.
```

Therefore there are **zero real generated event JSONs to paste**. Parseability, plot adherence, and cross-turn consistency could not be measured in this sandbox. Adding invented examples would violate the spike's requirement to use real MiniMax output.

Reproduction command in a network-enabled shell:

```bash
python3 tools/spike_narrative_director.py
```

## 5. Top five risks and unknowns

- [ ] **Authority boundary:** Which world mutations may a generated event request, and which outcomes must remain exclusively mechanical or player-controlled?
- [ ] **Long-horizon evaluation:** What automated benchmark detects drift, forgotten deaths, repeated beats, and violated anchors across decades rather than four turns?
- [ ] **Scheduling semantics:** How are due anchors, pending choices, mechanical crises, and Director beats deferred or cancelled without contradictory same-month outcomes?
- [ ] **Persistence/replay:** Which Director ledger/plan fields are saved, and can a save replay deterministically when the original model response is unavailable or the model version changes?
- [ ] **Operational budget:** What cadence, timeout, retry, fallback, and token budget keeps month advancement responsive while still giving the Director enough context to be coherent?

---

## 6. CLI 补跑验证结果（2026-06-09，Hassan）

codex sandbox 的 DNS 挡了 live 调用(§4),Hassan CLI(网络通)补跑确证。修复脚本两处:`MAX_TOKENS 400→3000`(minimax M2.7 是 thinking 模型,400 被 think 块吃光、JSON 被截断)、`parse_event` 剥 `<think>...</think>` + 提取 ```json``` fence。

**4 轮滚动生成,真实结果(非编造):**
- Turn 3「商帮内部分裂」:程宗扬入临安商帮,仙门背景引发赵三爷(拓西北军镇贸易)vs 陈掌柜(联建康士族)两派角力,被密报建康,小紫暗察。
- Turn 4「小紫现身」:小紫以**商帮侍女**身份接近,以建康情报换九阳传承用途,王哲远处留意。trigger_conditions 引用「陈掌柜已密报→建康已知程宗扬存在」。

**连贯性观察(强正面):**
- **跨轮记忆成立**:Turn 4 承接 Turn 3(程宗扬入商帮 → 小紫以商帮侍女接近;密报 → 建康已知),非孤立生成。
- **顺剧本脉络**:商帮/士族/军镇/粮道博弈,符合「六朝权力冲突逐步交汇」backbone。
- **纯六朝政治语境**:商帮/士族/军镇/情报网/密报,零修真术语。
- **结构化 JSON 全可解析**,self-check 全 `parseable=yes / follows_backbone=yes / contradicts_previous=no`。
- reasoning_tokens 300-489/轮,thinking 在真推演。

**结论:v1.9 核心可行性确证** —— LLM(minimax M2.7-highspeed)能连贯、顺剧本、六朝语境地生成结构化剧情事件,跨轮连贯/记忆成立。架构(§1-3)+ LLM 能力均验证,v1.9 不再是纯未知。

**v1.9 实现注意**:① thinking 模型需留足 token(think+输出)或禁 thinking;② parse 须剥 think 块;③ 本次仅 4 轮短验,长程(几十年)漂移仍需 §5 的自动化 benchmark(未验)。
