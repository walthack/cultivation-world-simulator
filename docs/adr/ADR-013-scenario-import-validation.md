# ADR-013: Scenario Import Validation

Date: 2026-06-03

## Status

Accepted for v0.6.

## Context

Scenario import writes user-provided archives into the application data root. Validation must reject malformed packages before install and must protect the data directory from archive attacks.

## Decision

Import validation is strict. The backend rejects invalid zip files, packages without `<scenario_id>/scenario.json`, packages without `<scenario_id>/timeline.json`, invalid JSON, missing required scenario fields, `scenario_id` and folder mismatches, unknown `world_preset.preset_id`, and invalid timeline schemas. It also performs deep reference validation against the referenced preset for realms, sects, personas, goldfingers, and the v0.2 preset-backed references already covered by the scenario loader.

Unknown top-level scenario fields and missing optional metadata are warnings. They do not block import.

Security checks are mandatory:

1. Zip-bomb protection rejects archives whose total uncompressed size exceeds 100 times the compressed upload size or 100 MB absolute.
2. Path traversal protection rejects absolute paths, `..` segments, multiple top-level roots, and entries whose resolved target does not stay inside `<scenario_id>/`.
3. Symlink entries are rejected by checking `ZipInfo.external_attr`.
4. JSON is parsed only with `json.load` or `json.loads`, followed by type validation.
5. The multipart import endpoint caps request body size at 10 MB before extraction.

Bundled scenario id collisions are rejected with a 400-class error because bundled files are read-only. User-installed id collisions return a 409 conflict shape so the frontend can ask the user whether to overwrite, rename, or cancel. Overwrite re-posts the same package with `force=true`. Rename re-posts the same package with `rename_to=<new_id>`; the backend validates the original package, rewrites the package-local `scenario_id`, revalidates, and installs under the new id.

Scenario enablement is stored in `$CWS_DATA_DIR/scenarios_state.json` as:

```json
{
  "scenario_id": { "enabled": true }
}
```

Missing state defaults to `enabled: true`. Enable/disable applies to both bundled and user-installed scenarios. The registry returns all scenarios with `source` and `enabled`; the game-start picker filters out disabled scenarios while the browser/manager continues to show them.

## Consequences

Import-time validation catches authoring mistakes before files enter the active scenario directory. Returning disabled scenarios from the registry keeps one API useful for both the picker and manager while preserving the v0.6 rule that disabled only hides a scenario from start selection.
