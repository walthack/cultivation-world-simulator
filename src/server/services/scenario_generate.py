from __future__ import annotations

import copy
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths
from src.scenario.scenario_loader import ScenarioValidationError, validate_scenario_dir
from src.server.services.scenario_templates import _scenario_from_draft
from src.utils.llm.client import call_llm_json
from src.utils.llm.config import LLMMode


SCENARIO_SCHEMA_PROMPT = """
Return only valid JSON. The JSON must be a scenario draft object with:
{
  "scenario": {
    "schema_version": "0.1" or "0.2",
    "scenario_id": "lower_snake_case",
    "title": "non-empty string",
    "version": "1.0",
    "author": "optional string",
    "description": "short summary",
    "tags": ["optional"],
    "world_preset": {"preset_id": "liuchao|default|sanguo"},
    "initial_state": {
      "year": 1,
      "month": 1,
      "avatars": [
        {
          "id": "stable-avatar-id",
          "surname": "string",
          "given_name": "string",
          "gender": "男 or 女",
          "age": 20,
          "sect_id": null,
          "realm": "QI_REFINEMENT",
          "stage": "EARLY_STAGE",
          "level": 1,
          "persona_traits": ["RATIONAL"],
          "goldfinger_id": "CHILD_OF_FORTUNE"
        }
      ],
      "relationships": [{"a": "avatar-id", "b": "avatar-id", "value": 0, "tag": "string"}],
      "sects": [],
      "world_flags": {}
    }
  },
  "timeline": {
    "schema_version": "0.1",
    "events": [
      {
        "id": "stable-event-id",
        "type": "main",
        "trigger": {"year": 1, "month": 1},
        "name": "event name",
        "description": "event description",
        "effects": [{"type": "set_flag", "flag": "flag_name"}]
      }
    ]
  }
}
Use references that exist in the requested world preset. Prefer schema_version 0.1 unless hints require 0.2.
"""


@dataclass(slots=True)
class GenerateResult:
    ok: bool
    draft: dict[str, Any] | None = None
    raw_output: Any | None = None
    validation_errors: list[str] = field(default_factory=list)
    attempts: int = 0

    def model_dump(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "draft": self.draft,
            "raw_output": self.raw_output,
            "validation_errors": list(self.validation_errors),
            "attempts": self.attempts,
        }


def _build_prompt(description: str, hints: dict[str, Any], errors: list[str] | None = None) -> str:
    preset_id = str(hints.get("preset_id") or hints.get("world_preset") or "liuchao")
    prompt = (
        "You are generating a CWS scenario-engine draft.\n"
        f"Default world preset: {preset_id}.\n"
        f"Creator description: {description.strip()}\n"
        f"Hints JSON: {json.dumps(hints, ensure_ascii=False, sort_keys=True)}\n"
        f"{SCENARIO_SCHEMA_PROMPT.strip()}\n"
    )
    if errors:
        prompt += (
            "\nThe previous output failed validation. Fix these errors and return the full JSON draft again:\n"
            + "\n".join(f"- {error}" for error in errors)
        )
    return prompt


def _validate_generated_draft(draft: dict[str, Any], hints: dict[str, Any]) -> list[str]:
    # Deep copy so validation-time mutations (e.g. filling in preset_id from hints)
    # don't pollute the caller's draft dict, which downstream code preserves as
    # raw_output for the "raw LLM response" user-facing diagnostic.
    draft = copy.deepcopy(draft)
    scenario, timeline = _scenario_from_draft(draft)
    world_preset = scenario.get("world_preset")
    if not isinstance(world_preset, dict):
        world_preset = {}
        scenario["world_preset"] = world_preset
    if not world_preset.get("preset_id"):
        world_preset["preset_id"] = str(hints.get("preset_id") or hints.get("world_preset") or "liuchao")

    scenario_id = str(scenario.get("scenario_id", "generated_scenario"))
    data_root = get_data_paths().root
    data_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scenario-generate-", dir=str(data_root)) as tmp_name:
        scenario_dir = Path(tmp_name) / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        (scenario_dir / "scenario.json").write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (scenario_dir / "timeline.json").write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        validation = validate_scenario_dir(scenario_dir)
    return validation.warnings


async def generate_scenario_from_description(
    description: str,
    hints: dict[str, Any],
    *,
    retry: int = 1,
) -> GenerateResult:
    if not isinstance(description, str) or not description.strip():
        return GenerateResult(
            ok=False,
            raw_output=None,
            validation_errors=["description is required"],
            attempts=0,
        )
    if not isinstance(hints, dict):
        hints = {}

    max_attempts = max(1, int(retry) + 1)
    errors: list[str] = []
    raw_output: Any = None
    for attempt in range(1, max_attempts + 1):
        prompt = _build_prompt(description, hints, errors if attempt > 1 else None)
        try:
            raw_output = await call_llm_json(prompt, LLMMode.NORMAL, max_retries=0)
            if not isinstance(raw_output, dict):
                raise ValueError(f"LLM JSON root must be an object, got {type(raw_output).__name__}")
            _validate_generated_draft(raw_output, hints)
        except (ScenarioValidationError, ValueError) as exc:
            errors = [str(exc)]
            if attempt < max_attempts:
                continue
            return GenerateResult(
                ok=False,
                raw_output=raw_output,
                validation_errors=errors,
                attempts=attempt,
            )
        except Exception as exc:
            errors = [str(exc)]
            if attempt < max_attempts:
                continue
            return GenerateResult(
                ok=False,
                raw_output=raw_output,
                validation_errors=errors,
                attempts=attempt,
            )
        return GenerateResult(ok=True, draft=raw_output, raw_output=raw_output, attempts=attempt)

    return GenerateResult(ok=False, raw_output=raw_output, validation_errors=errors, attempts=max_attempts)
