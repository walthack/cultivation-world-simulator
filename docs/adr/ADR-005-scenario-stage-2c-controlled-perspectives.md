# ADR-005: Scenario Stage 2c Controlled Perspectives

## Status

Accepted for Stage 2c.

## Context

Stage 2b established v0.2 scenario data for dynasty, orthodoxy, region vocab, and an abstract region graph. The liuchao scenario still has only a minimal linear timeline, and Stage 2c needs the first content pass that can express:

- Different text for the same scene when the controlled avatar changes.
- Main events anchored to six-dynasty political geography.
- A partial but testable timeline across Qin, Han, Jin, and Song.

The scenario dispatcher already evaluates event trigger conditions and records triggered event ids in runtime state. The effect applier already treats effects as data dictionaries and rolls state back on clean failures.

## Decision

Add `controlled_avatar_is(target_id)` as a canonical predicate. It reads `state["controlled_avatar"]` and returns true only when it matches the supplied `target_id`. Missing controlled-avatar state evaluates false, matching existing boolean predicate behavior where absent state is not a hard schema error.

Add `{controlled_avatar}` substitution inside effect dictionaries before effect dispatch. The placeholder resolves from `state["controlled_avatar"]`. If an effect string asks for the placeholder and the state does not provide it, effect application raises `EffectError` and rolls back the whole effect batch.

Model multi-perspective scenes as separate main events with the same trigger date and scene anchor, each gated by `controlled_avatar_is`. This avoids nesting perspective text inside handler code and keeps the timeline inspectable as data.

Use v0.2 liuchao timeline metadata for dynasty anchors. Stage 2c events may include `dynasty_id` and region trigger metadata; the dispatcher ignores these fields unless a trigger needs them, while tests can still assert coverage and load-time validity.

## Consequences

The controlled-avatar concept becomes scenario state, not a hard dependency on roleplay runtime internals. Runtime integration can map roleplay `controlled_avatar_id` into `state["controlled_avatar"]` before scenario dispatch.

Perspective selection stays deterministic: for one scene, only the event whose controlled-avatar predicate matches can fire. No handler branching or text templating layer is required for Stage 2c.

Effect placeholders remain deliberately narrow. Stage 2c only defines `{controlled_avatar}` because it is needed by the perspective contract; broader templating can be added later with explicit schema and escaping rules.

The six-dynasty timeline remains partial. Stage 2c proves the data shape with Qin, Han, Jin, and Song anchors before expanding to full campaign coverage.

## Alternatives

One alternative was to read `scenario_runtime.controlled_avatar_id` directly in the predicate. That would couple scenario data to current roleplay runtime naming and make fixture-driven scenario tests less explicit.

Another alternative was a single event with a `perspectives` map. That would require new handler semantics before the MVP has enough content volume to justify it.

A third alternative was adding a general string-template engine for all event fields. Stage 2c only needs effect-string substitution, so a general templating surface would expand the public contract too early.
