from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


def compute_scenario_fingerprint(scenario: dict[str, Any], timeline: dict[str, Any]) -> str:
    scenario_copy = copy.deepcopy(scenario)
    scenario_copy.pop("fingerprint", None)
    payload = json.dumps(
        {"scenario": scenario_copy, "timeline": timeline},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
