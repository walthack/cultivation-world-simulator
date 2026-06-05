# ADR-004: Region Map Abstract Graph

## Status

Accepted for Stage 2b Batch B.

## Context

CWS currently stores map data as tile-level CSV grids:

- `static/game_configs/region_map.csv` contains region ids per tile.
- `static/game_configs/tile_map.csv` contains terrain tile ids per tile.

Batch B scope asks for a v0.2 region map skeleton as an abstract adjacency graph, and explicitly excludes tile-level editor, full X/Y coordinates, and pathfinding.

## Decision

Do not expose the existing tile grid as v0.2 schema. Instead, derive a lossy abstract graph:

- Scan adjacent cells in `region_map.csv`.
- For every orthogonal neighbor pair with two known region ids, emit one undirected edge.
- Store only `{from_region_id, to_region_id, relation, difficulty}`.
- Default relation is `neutral`.
- Difficulty is a traversal-cost proxy, not pathfinding: cultivate edges get higher default difficulty than ordinary region/city edges.

Liuchao uses a hand-authored minimal graph because its v0.2 region vocab is scenario-scale and does not have tile-level source data yet.

## Consequences

The v0.2 schema can express region connectivity for event references and lightweight travel reasoning without committing to CWS internal tile layout. Full tile topology, coordinates, terrain editing, and pathfinding remain v0.3+ scope.
