#!/usr/bin/env python3
"""Standalone Narrative Director spike using MiniMax's OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://api.minimaxi.com/v1"
MODEL = "MiniMax-M2.7-highspeed"
TURN_COUNT = 4
MAX_TOKENS = 3000
ENV_PATH = Path.home() / ".openclaw" / ".env"

BACKBONE = (
    "六朝并立，皇权、士族、军镇与隐世仙门彼此牵制，乱局正从局部争端扩散。"
    "异世来客程宗扬要在各方博弈中求生并逐渐掌握主动权。"
    "太乙真宗高人王哲正在判断是否把九阳传承托付给程宗扬，小紫则暗中观察他的选择。"
    "后续剧情应让个人传承线与临安、建康、洛阳、关中等地的六朝权力冲突逐步交汇。"
)

WORLD_SNAPSHOT = {
    "time": "第2年6月",
    "parties": {
        "程宗扬": "已入临安，接受九阳传承，在乱世中寻求主动权",
        "王哲": "太乙真宗高人，仍在世，与程宗扬关系亲近",
        "小紫": "来历不明，持续观察程宗扬",
        "宋地临安官府": "新设水路税卡，与商帮互相试探",
        "晋地建康士族": "已召开族议，争夺江南粮道与朝中人事",
        "秦地军镇": "已在关中点兵，西北诸关紧张",
        "汉廷": "已在洛阳重申汉统名分，整肃北境驿路",
    },
    "happened": [
        "程宗扬、王哲、小紫抵达临安",
        "王哲将九阳传承交给程宗扬",
        "秦军关中点兵",
        "汉廷洛阳颁诏",
        "建康士族分配江南粮道与人事",
        "临安增设水路税卡",
    ],
}

REQUIRED_FIELDS = (
    "event_id",
    "title",
    "description",
    "involved_parties",
    "trigger_conditions",
    "expected_consequences",
)
BACKBONE_TERMS = {
    "程宗扬",
    "王哲",
    "小紫",
    "九阳",
    "太乙真宗",
    "临安",
    "建康",
    "洛阳",
    "关中",
    "宋",
    "晋",
    "秦",
    "汉",
    "士族",
    "军镇",
    "粮道",
    "水税",
}
TERMINAL_MARKERS = ("身亡", "死亡", "被杀", "覆灭", "灭亡", "处死")


def load_dotenv_if_needed() -> None:
    if os.environ.get("MINIMAX_API_KEY") or not ENV_PATH.is_file():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key != "MINIMAX_API_KEY":
            continue
        value = value.strip().strip("\"").strip("'")
        if value:
            os.environ[key] = value
        return


def build_initial_prompt() -> str:
    snapshot = json.dumps(WORLD_SNAPSHOT, ensure_ascii=False, separators=(",", ":"))
    return f"""剧情骨架：{BACKBONE}
世界快照：{snapshot}
生成紧接当前状态的下一个剧情事件。先在内部检查它符合骨架且不重复已发生事件。
只输出一个 JSON 对象，不要 Markdown。字段必须且只能是：
event_id, title, description, involved_parties, trigger_conditions, expected_consequences。
event_id 用简短 kebab-case；其余字段用中文；involved_parties 和 expected_consequences 用短字符串数组；trigger_conditions 用简短对象。"""


def call_chat(api_key: str, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.45,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiniMax request failed: {exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected MiniMax response: {body}") from exc
    return str(content), dict(body.get("usage") or {})


def parse_event(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    # MiniMax M2.7 is a thinking model: strip <think>...</think> first
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1)
    elif cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    elif not cleaned.startswith("{"):
        obj = re.search(r"\{.*\}", cleaned, re.S)
        if obj:
            cleaned = obj.group(0)
    event = json.loads(cleaned)
    if not isinstance(event, dict):
        raise ValueError("response is not a JSON object")
    missing = [field for field in REQUIRED_FIELDS if field not in event]
    extras = [field for field in event if field not in REQUIRED_FIELDS]
    if missing or extras:
        raise ValueError(f"schema mismatch; missing={missing}, extra={extras}")
    if not isinstance(event["involved_parties"], list):
        raise ValueError("involved_parties must be a list")
    if not isinstance(event["expected_consequences"], list):
        raise ValueError("expected_consequences must be a list")
    if not isinstance(event["trigger_conditions"], dict):
        raise ValueError("trigger_conditions must be an object")
    return event


def event_text(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, sort_keys=True)


def find_terminal_entities(events: list[dict[str, Any]]) -> set[str]:
    terminal: set[str] = set()
    for event in events:
        text = event_text(event)
        if any(marker in text for marker in TERMINAL_MARKERS):
            terminal.update(str(party) for party in event.get("involved_parties", []))
    return terminal


def coherence_check(event: dict[str, Any], previous: list[dict[str, Any]]) -> str:
    text = event_text(event)
    anchors = sorted(term for term in BACKBONE_TERMS if term in text)
    follows_backbone = bool(anchors)
    duplicate_id = any(item.get("event_id") == event.get("event_id") for item in previous)
    resurrected = sorted(find_terminal_entities(previous) & set(map(str, event.get("involved_parties", []))))
    contradiction = duplicate_id or bool(resurrected)
    contradiction_note = "none detected"
    if duplicate_id:
        contradiction_note = "duplicate event_id"
    elif resurrected:
        contradiction_note = f"terminal entity reused: {', '.join(resurrected)}"
    return (
        f"parseable=yes; follows_backbone={'yes' if follows_backbone else 'uncertain'} "
        f"(anchors={','.join(anchors) or 'none'}); contradicts_previous="
        f"{'yes' if contradiction else 'no'} ({contradiction_note}; heuristic)"
    )


def main() -> int:
    load_dotenv_if_needed()
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("MINIMAX_API_KEY is missing from the environment and ~/.openclaw/.env", file=sys.stderr)
        return 2

    messages = [
        {
            "role": "system",
            "content": (
                "你是六朝剧情导演。保持长程因果、人物存活状态和阵营动机一致；"
                "推进而非复述剧情；严格输出请求的 JSON。"
            ),
        },
        {"role": "user", "content": build_initial_prompt()},
    ]
    events: list[dict[str, Any]] = []

    for turn in range(1, TURN_COUNT + 1):
        content, usage = call_chat(api_key, messages)
        try:
            event = parse_event(content)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"Turn {turn} invalid response: {exc}\n{content}", file=sys.stderr)
            return 1

        print(f"\n=== Turn {turn} ===")
        print(json.dumps(event, ensure_ascii=False, indent=2))
        print(f"Self-check: {coherence_check(event, events)}")
        if usage:
            print(f"Usage: {json.dumps(usage, ensure_ascii=False, sort_keys=True)}")

        events.append(event)
        messages.append({"role": "assistant", "content": json.dumps(event, ensure_ascii=False)})
        if turn < TURN_COUNT:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "把上一个事件视为已发生。生成下一个事件，推进同一主线但不要重复；"
                        "保持人物、阵营与因果一致。仍只输出相同六字段 JSON。"
                    ),
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
