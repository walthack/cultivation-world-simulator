# Schema v0.2 Batch B Spec Update

## Changelog Additions

### Stage 2b-1 Dynasty

- New preset file: `config/presets/<preset_id>/dynasties.json`.
- New optional scenario field: `scenario.initial_state.dynasties`.
- Dynasty entries use mid-granularity schema:
  - `id: string`
  - `name: string`
  - `description: string`
  - `capital_region_id: string | null`
  - `ruler_avatar_id: string | null`
  - `territory_region_ids: string[]`
  - `status: "active" | "declining" | "fallen"`
  - `founding_year: number`
  - `relations: [{other_dynasty_id, type, value}]`
  - `orthodoxy_ids: string[]`
- Validation:
  - `ruler_avatar_id` references `scenario.initial_state.avatars`.
  - `capital_region_id` and `territory_region_ids` reference `preset.regions`.
  - `orthodoxy_ids` reference `preset.orthodoxies`.
  - `relations[].type` enum: `ally | rival | vassal | enemy | neutral`.
  - `relations[].value` range: `-100..100`.
  - Reference validation is gated on `schema_version: "0.2"`.

### Stage 2b-2 Orthodoxy

- New preset file: `config/presets/<preset_id>/orthodoxies.json`.
- Orthodoxy entries use multi-axis ideology schema:
  - `id: string`
  - `name: string`
  - `description: string`
  - `axes: dict<string, number>`
  - `tags: string[]`
- Validation:
  - `axes` must be an object.
  - Every axis key must be non-empty string.
  - Every axis value must be numeric.
  - `tags` must be `list[str]`.

### Stage 2b-3 Region Vocab

- New preset file: `config/presets/<preset_id>/regions.json`.
- Region entries use vocab + event reference schema:
  - `id: string`
  - `name: string`
  - `type: "city" | "cultivate" | "normal"`
  - `description: string`
  - `dynasty_id: string | null`
  - `climate: string`
  - `economic_focus: string`
  - `key_landmarks: string[]`
  - `tags: string[]`
- New optional scenario fields:
  - `scenario.initial_state.avatars[].location_region_id`
  - `scenario.initial_state.sects[].headquarters_region_id`
  - `timeline.events[].trigger.at_region_id`
- Validation:
  - Region `type` must be one of `city`, `cultivate`, `normal`.
  - Region `dynasty_id` references `preset.dynasties`.
  - Avatar/sect/event region refs reference `preset.regions`.
  - Reference validation is gated on `schema_version: "0.2"`.

### Stage 2b-4 Region Map Skeleton

- New preset file: `config/presets/<preset_id>/region_adjacency.json`.
- Region adjacency schema:

```json
{
  "preset_id": "default",
  "edges": [
    {
      "from_region_id": "101",
      "to_region_id": "102",
      "relation": "neutral",
      "difficulty": 1
    }
  ]
}
```

- Edge relation enum: `friendly | hostile | neutral | restricted`.
- `difficulty` is a positive number and represents traversal cost proxy only.
- One edge is undirected and represents both directions.
- Validation:
  - `from_region_id` and `to_region_id` reference `preset.regions`.
  - Self edges are rejected.
  - Invalid relation names are rejected.
  - Non-positive difficulty is rejected.

## Scope Notes

`region_map.csv` is tile-level CWS data. v0.2 deliberately exposes an abstract graph only. Tile coordinates, terrain editor, pathfinding, and full map topology remain v0.3+ scope. See `docs/adr/ADR-004-region-map-abstract-graph.md`.

## Backward Compatibility

- v0.1 scenarios continue to load without all Batch B fields.
- All new fields are optional.
- v0.2 validation only applies when the new fields are present and the scenario declares `schema_version: "0.2"`.
- Default preset data is additive and does not alter CWS default startup behavior.
