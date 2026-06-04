# ADR-019: Scenario Dependency Management

Date: 2026-06-04
Status: Accepted

## Lenient Semver

v0.9 uses lenient semver for update detection and compatibility checks. Missing minor or patch segments are treated as `0`; prerelease tags compare lower than the matching release. Non-semver strings remain accepted as scenario versions, but semantic ordering is only applied when both sides can be parsed.

## Engine Compatibility

`scenario.json` may include:

```json
{
  "engine": {
    "schema_version_min": "0.2",
    "cws_version_min": "3.4.0"
  }
}
```

The field is optional for legacy compatibility. Creator-toolkit templates emit it so new packages can communicate author intent.

`schema_version_min` is fatal when it exceeds the current supported schema versions. `cws_version_min` is warning-only in v0.9 so users can decide whether to proceed.

## Dependency Types

v0.9 supports preset dependencies only:

```json
{"type": "preset", "id": "liuchao", "version_req": ">=1.0"}
```

Scenario-on-scenario, asset, and library dependencies are deferred to later mod-platform work. A preset dependency fails compatibility if the preset directory is missing.

## Check Timing And Policy

Compatibility checks run during install-from-download and update. Import validation accepts the new metadata fields and fingerprint, while repository listing shows compatibility status for local packages.

Policy:

- Schema incompatibility and missing preset dependency: reject.
- CWS version mismatch: warn and require user confirmation in the frontend.
- Warnings are non-fatal after confirmation.
