# Scenario Metadata Schema

Date: 2026-06-03
Status: v0.5 contract

`config/scenarios/<scenario_id>/scenario.json` is the metadata source for bundled scenario discovery. v0.5 discovery reads only the top-level metadata fields and does not validate the full scenario engine payload.

## Required Fields

| Field | Type | Notes |
|---|---|---|
| `scenario_id` | string | Stable scenario identity. This is exposed as `id` in `/api/v1/query/scenarios`. |
| `title` | string | Display title. The API maps this to DTO field `name`. |
| `version` | string | Scenario content version. |
| `description` | string | Short browser summary. |

## Optional Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `author` | string | `null` | Recommended for bundled scenarios. |
| `tags` | string[] | `[]` | Browser chips. Missing or invalid values are treated as empty for v0.5 discovery. |
| `cover_image` | string | `null` | Scenario-local thumbnail path for browser display. |

## Existing Examples

`config/scenarios/liuchao/scenario.json`:

```json
{
  "scenario_id": "liuchao",
  "title": "六朝纪事",
  "version": "1.0",
  "author": "Chaldeas",
  "description": "Stage 1 minimal 六朝 scenario demo."
}
```

`config/scenarios/sanguo/scenario.json`:

```json
{
  "scenario_id": "sanguo",
  "title": "三国仙纪",
  "version": "1.0",
  "author": "Chaldeas",
  "description": "Stage 2d minimal 三国 scenario demo proving scenario engine generality."
}
```

The full files include engine fields such as `world_preset`, `world_background`, `initial_state`, and timeline references. Those fields remain governed by the scenario loader and engine schema, not by the v0.5 discovery DTO.
