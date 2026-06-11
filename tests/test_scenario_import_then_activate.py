"""P1-a diagnostic — does an IMPORTED scenario actually take effect?

The cross-schema sweep only covers scenarios pre-installed under
config/scenarios. Real imports (import_scenario_zip) install under the user
DATA root. This test closes the seam: import a zip → activate it the way the
runtime does (scenario_loader.load(scenario_id)) → dispatch its opening event
and assert the effect lands.

If this fails at load(), imported scenarios are discoverable-but-not-runnable —
the "import takes effect" guarantee is broken at the import↔loader seam.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.scenario_loader import load
from src.server.services.scenario_import import import_scenario_zip
from src.server.services.scenario_registry import list_installed_scenarios


def _zip_min_scenario(scenario_id: str) -> bytes:
    scenario = {
        "schema_version": "0.1",
        "scenario_id": scenario_id,
        "title": f"{scenario_id} title",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {"year": 1, "month": 1, "avatars": [], "relationships": [], "sects": [], "world_flags": {}},
    }
    timeline = {
        "schema_version": "0.1",
        "events": [{
            "id": f"{scenario_id}-opening",
            "type": "side_event",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "effects": [{"type": "set_flag", "flag": "imported_opening_seen"}],
        }],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{scenario_id}/scenario.json", json.dumps(scenario))
        zf.writestr(f"{scenario_id}/timeline.json", json.dumps(timeline))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_imported_scenario_is_discoverable_then_loads_and_takes_effect():
    scenario_id = "imported_demo"

    # import → installs under the data root
    import_scenario_zip(_zip_min_scenario(scenario_id))

    # discoverable in the registry
    assert scenario_id in {meta.id for meta in list_installed_scenarios()}

    # activatable through the runtime load path
    resolved = load(scenario_id)
    assert len(resolved.timeline) == 1

    # and its opening event takes effect
    state = {
        "world": {"year": 1, "month": 1, "world_flags": {}},
        "scenario_runtime": {"scenario_id": scenario_id, "triggered_event_ids": []},
    }
    await EventDispatcher(resolved.timeline, handlers={"side_event": handle_side_event}).dispatch_month(state)
    assert state["world"]["world_flags"].get("imported_opening_seen") is True
