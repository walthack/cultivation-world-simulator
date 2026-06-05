# ADR-014: Scenario Authoring Templates

Date: 2026-06-03
Status: Accepted

## Context

v0.7 adds creator-facing scenario authoring. Players need a low-friction starting point that still produces normal scenario engine packages: `scenario.json` plus `timeline.json`, referencing existing bundled presets.

## Decision

Ship three local starter templates under `config/templates/scenario/`:

- `historical.json`
- `fantasy.json`
- `sandbox.json`

Each template is a JSON object with category metadata plus a full draft:

- `category`
- `summary`
- `scenario`
- `timeline`

The backend template service exposes summary metadata for browsing and full template payloads for wizard population. Templates reference existing presets only; v0.7 does not introduce template-specific presets.

The frontend uses a 6-step wizard:

1. Basics
2. World preset selection
3. LLM Assisted
4. Initial state
5. Timeline
6. Review/Save

Schema reference content is shown through a modal opened from `?` buttons inside the wizard.

## Consequences

Templates are versioned with the application and validated by the existing `validate_scenario_dir` path after being materialized into draft package files. The format remains close to importable scenario packages, so wizard output can be saved to disk and exported as a zip without a separate authoring schema.

Online/community template distribution remains out of scope for v0.7.
