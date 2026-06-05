# ADR-018: Scenario Distribution

Date: 2026-06-04
Status: Accepted

## Local-Only Scope

v0.9 implements a local community scenario ecosystem. There is no marketplace endpoint, no hosted repository, no polling, and no account or auth layer. Sharing is file-based: export an installed scenario as a zip, move it through any external channel, then place or install it locally.

## Export Format

Exports are zip packages matching the v0.6 import layout:

- `<scenario_id>/scenario.json`
- `<scenario_id>/timeline.json`
- scenario-local static files

Exports do not include runtime state. `scenario_state.json` and enabled/disabled state remain local to the receiving installation.

## Repository Tabs

The system menu scenario browser uses three local tabs:

- Installed: scenarios under `$CWS_DATA_DIR/scenarios/`
- Downloaded: unpacked scenario directories under `$CWS_DATA_DIR/scenarios_downloads/`
- Updates: downloaded scenarios whose `scenario_id` matches an installed scenario and whose version compares newer under lenient semver rules

Downloaded is intentionally separate from the v0.6 import flow. Import still installs directly. Downloaded is a local staging folder for packages a user wants to inspect before installing.

## Updates And Backup

Update activation archives the current installed directory before replacing it:

`$CWS_DATA_DIR/scenarios_archive/<scenario_id>/<old_version>/`

The replacement then moves the downloaded directory into `$CWS_DATA_DIR/scenarios/<scenario_id>/`.

## Fingerprint

Scenario fingerprint is a content hash stored at top-level `scenario.fingerprint` in exported `scenario.json`. The value format is `sha256:<hex>`.

Algorithm:

1. Deep-copy `scenario.json`.
2. Remove `fingerprint` from the copy.
3. Serialize `{"scenario": scenario_copy, "timeline": timeline}` with sorted keys, `ensure_ascii=False`, and compact separators.
4. Return `sha256:` plus the SHA-256 digest of the UTF-8 bytes.

Timing:

- Export computes the fingerprint and injects it only into the zip's `scenario.json`.
- Export does not rewrite the installed scenario file on disk.
- Import/install/repository listing recomputes the fingerprint from current content and compares it with the claimed field.

Verification states:

- `verified`: claimed fingerprint exists and matches current content.
- `modified`: claimed fingerprint exists and does not match current content.
- `unsigned`: no claimed fingerprint exists, including legacy or hand-written local scenarios.

Not rewriting the installed source during export keeps local authoring directories clean and avoids turning a read-only package operation into a metadata mutation.
