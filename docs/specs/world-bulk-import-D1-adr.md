# ADR: World Bulk Import D1

Date: 2026-06-01

## Status

Draft for Stage 1 D1.

## Context

The public control API is split into query and command routes under `src/server/api/public_v1/`. Command routes call closures created by `src/server/command_handlers.py`, and world mutations are serialized with `GameSessionRuntime.run_mutation()`. This keeps API-level writes from racing with `Simulator.step()`.

The current in-memory simulation state is rooted at `runtime.state`:

- `runtime["world"]` stores the active `World`.
- `World.avatar_manager.avatars` is the live avatar dictionary keyed by avatar id.
- `AvatarManager.register_avatar()` is the existing set-state API for adding a live avatar and optionally marking it as newly born for frontend sync.
- Sect runtime state is stored on static `Sect` objects and scoped through `World.sect_context`, `World.existed_sects`, and `SectManager` snapshots.
- Goldfinger state lives on each `Avatar` as `avatar.goldfinger` and `avatar.goldfinger_state`.
- Relationship state is object-linked: `avatar.relations` and `avatar.archived_relations` are keyed by other `Avatar` objects, with save/load converting those references to ids.
- There was no dedicated world flag store before D1. D1 adds `World.world_flags` as a plain JSON-compatible dict and exposes it in `/api/v1/query/world/state`.

## Decision

Add `POST /api/v1/command/world/bulk-import` as a minimal D1 command.

Payload supported in D1:

```json
{
  "avatars": [{"id": "test-1", "name": "TestAvatar"}],
  "world_flags": {"test_flag": true}
}
```

The route is registered in `src/server/api/public_v1/command.py`, the command closure is created in `src/server/command_handlers.py`, and the mutation logic lives in `src/server/services/world_bulk_import.py`.

D1 imports each avatar as a minimal Qi Refinement rogue cultivator with deterministic id/name and conservative defaults. If the runtime has no world yet, the handler creates a minimal 10x10 plain-map world at Year 1 / January so the import can be verified on a freshly started local server. It writes avatars through `world.avatar_manager.register_avatar(..., is_newly_born=True)` and merges `world_flags` into `world.world_flags`.

## Consequences

- Mutations are serialized through the existing runtime lock.
- D1 intentionally does not import sect membership, goldfinger, relationships, inventory, map regions, or save/load persistence for `world_flags`.
- Duplicate avatar ids return HTTP 409.
- Missing avatar id/name returns HTTP 400.
- A non-initialized world is bootstrapped only to the minimum state needed for D1 import and query verification; it does not create a `Simulator`.

## Follow-ups

D2+ should define a fuller import schema for sects, goldfingers, relationships, flags persistence, and validation rules before expanding this endpoint.
