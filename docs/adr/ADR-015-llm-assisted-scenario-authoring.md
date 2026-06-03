# ADR-015: LLM Assisted Scenario Authoring

Date: 2026-06-03
Status: Accepted

## Context

Creators may describe a world in natural language and ask CWS to generate a scenario skeleton. v0.7 must reuse the existing LLM stack and must not add a new provider dependency or a dedicated authoring mode.

## Decision

Scenario authoring calls `call_llm_json` with `LLMMode.NORMAL`. The prompt includes the scenario draft structure, asks for JSON-only output, and includes user hints such as the target preset.

Generated output is validated by materializing the draft into `scenario.json` and `timeline.json`, then calling `validate_scenario_dir`. If validation fails, the backend retries once with the validation errors included in the next prompt. If the second attempt still fails, the API returns:

- the raw parsed LLM output when available
- validation errors
- attempt count
- `ok: false`

The frontend keeps the raw-fallback path editable by the user rather than attempting further automatic repair.

## Consequences

The cost cap is predictable: at most two LLM JSON calls per generate request. Validation remains tied to the real scenario loader instead of a separate frontend-only schema. A future version may add a dedicated `LLMMode.AUTHORING`, but v0.7 intentionally keeps authoring on `NORMAL`.
