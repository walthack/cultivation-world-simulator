# ADR-021: Mod Asset and Localization Overlay

## Status

Accepted for v1.0.

## Decision

Asset files shipped by enabled mods are treated as overlay directories. Resolution checks enabled mod asset directories in load order, with later mods taking precedence, then falls back to bundled assets.

Localization overlays are JSON files declared from `mod.json` under `extensions.assets.localizations`. They are merged at runtime and looked up before gettext catalogs. If multiple enabled mods provide the same locale key, the loader records a conflict for the Mod Manager.

## Consequences

Mods never overwrite bundled assets or locale catalogs. Disabling a mod removes its overlay entries on the next loader refresh.
