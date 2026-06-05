# ADR-012: Scenario Packaging

Date: 2026-06-03

## Status

Accepted for v0.6.

## Context

Scenario v0.5 discovers bundled scenarios from `config/scenarios/`. v0.6 adds user import, but does not add a mod marketplace, authoring wizard, preset bundling, auto-update, or runtime scenario activation/deactivation.

## Decision

Scenario packages are `.zip` files only. A valid package contains exactly one top-level scenario directory whose name is the `scenario_id`:

```text
<scenario_id>/
  scenario.json
  timeline.json
```

The `scenario_id` in `scenario.json` must match the top-level directory name. The package must not bundle presets or write outside the scenario directory. `world_preset.preset_id` must reference an existing preset already available to the game.

Imported scenarios install to:

```text
$CWS_DATA_DIR/scenarios/<scenario_id>/
```

Bundled scenarios remain in:

```text
config/scenarios/<scenario_id>/
```

The registry distinguishes `source: "bundled"` from `source: "installed"`. Bundled content is read-only for file operations; user-installed content can be removed or overwritten through the import flow.

## Consequences

The v0.6 import path stays browser-friendly and uses Python's stdlib `zipfile`. Fully custom worlds that require new presets must install or ship those presets through a later feature. A user-installed package cannot shadow a bundled scenario id; that collision is rejected explicitly.
