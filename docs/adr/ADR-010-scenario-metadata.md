# ADR-010: Scenario Metadata DTO

Date: 2026-06-03
Status: Accepted

## Context

v0.5 adds scenario discovery and selection. Existing bundled scenario files already contain top-level metadata, but the roadmap uses `name` while the files use `title`.

## Decision

The registry reads `config/scenarios/<id>/scenario.json` and exposes:

```json
{
  "id": "liuchao",
  "name": "六朝纪事",
  "version": "1.0",
  "author": "Chaldeas",
  "description": "...",
  "tags": [],
  "cover_image": null
}
```

`scenario_id` maps to API `id`; `title` maps to API `name`.

`tags` and `cover_image` are optional. Missing `tags` becomes `[]`; missing `cover_image` becomes `null`. `author` is recommended but optional in the discovery DTO.

## Consequences

Existing `liuchao` and `sanguo` files do not need a batch rename from `title` to `name`. The API gives the frontend a stable `name` field while preserving the current scenario authoring format.

The discovery scanner intentionally reads metadata directly rather than loading the full scenario. A broken directory is logged and skipped so one invalid scenario does not break the browser list.
