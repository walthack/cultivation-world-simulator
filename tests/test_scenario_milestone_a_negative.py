"""Milestone A engine-core negative tests.

御主 2026-06-04 02:47 SGT 拍 "4 层都做 + 每 milestone ≥ 1 negative test"。
审计后 Milestone A 唯一缺口：condition_evaluator + effect_applier 已有 happy
path 覆盖 (Stage 1 D7-D10 的 13 predicate + 17 effect)，但没有显式 negative
test 验保护机制（unknown predicate / unknown effect type / missing params）。

本文件背填两个核心负面测试，关闭 Layer 5 backfill 需求。
"""

from __future__ import annotations

import pytest

from src.scenario.condition_evaluator import (
    ConditionEvaluationError,
    evaluate_condition,
)
from src.scenario.effect_applier import EffectError, apply_effects


def test_unknown_predicate_name_raises_condition_evaluation_error() -> None:
    """
    Negative: scenario timeline 引用未注册的 predicate 名时，condition_evaluator
    必须显式报错（ConditionEvaluationError），而非静默 false 或 crash。

    保证：mod / scenario author 拼错 predicate 名时立刻得到反馈，不漂移成
    "条件评估为 false 所以事件不触发" 这种 silent failure。
    """
    expression = {"this_predicate_does_not_exist": {"arg": "value"}}
    with pytest.raises(ConditionEvaluationError) as exc_info:
        evaluate_condition({}, expression)
    assert "unknown predicate" in str(exc_info.value).lower()
    assert "this_predicate_does_not_exist" in str(exc_info.value)


def test_unknown_effect_type_raises_effect_error_and_rolls_back_state() -> None:
    """
    Negative: scenario timeline 用未知 effect type 时 effect_applier 必须显式
    报错并 roll back 前序 effects 的副作用，不留下半应用的 state。

    保证：一个事件的 effect 链中一个错的 effect type 不会导致前面 effects
    持久化但后面 effects 没跑这种损坏状态。
    """
    state = {"world_flags": {}, "npcs": {}, "relations": {}}
    effects = [
        # 第一个 effect 是合法的 set_flag，会先 mutate state
        {"type": "set_flag", "flag": "marker_should_rollback"},
        # 第二个是非法 effect type，触发 EffectError
        {"type": "this_effect_type_does_not_exist", "arg": "value"},
    ]
    with pytest.raises(EffectError) as exc_info:
        apply_effects(state, effects)
    assert "Unknown effect type" in str(exc_info.value)
    # state must be rolled back — the partial set_flag from effect 1 must NOT persist
    assert state.get("world_flags", {}) == {}, "state must roll back on EffectError"
