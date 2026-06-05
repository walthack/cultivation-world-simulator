# ADR-022: Mod LLM Prompt Overrides

## Status

Accepted for v1.0.

## Decision

Mods may declare LLM prompt overrides with `extensions.llm.prompts`. Each entry maps a stable key to a plain text template file in the mod directory.

`call_llm_with_template` checks the active mod overlay registry before reading the bundled template path. Templates use the existing lightweight `{name}` formatting behavior; no new templating dependency is introduced.

## Consequences

Prompt overrides are data-only and are active by default for enabled mods. If no override exists, the bundled template path is used unchanged.
