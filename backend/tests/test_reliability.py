from collections import Counter

from cabinguard.models import Trace, VehicleState
from cabinguard.reliability import (
    TrajectoryStep,
    evaluate_trial,
    load_suite,
    summarize_trials,
)


def case(case_id: str):
    return next(item for item in load_suite().cases if item.id == case_id)


def step(
    *,
    response: str,
    traces: list[Trace] | None = None,
    vehicle: VehicleState | None = None,
) -> TrajectoryStep:
    return TrajectoryStep(
        input="测试输入",
        response=response,
        traces=traces or [],
        vehicle=vehicle or VehicleState(),
        model="fake-model",
        turns=1,
        tokens=10,
        latencyMs=20,
        promptVersion="test-prompt",
        toolVersion="test-tools",
    )


def climate_success_step() -> TrajectoryStep:
    return step(
        response="已将空调设置为 23℃。",
        vehicle=VehicleState(target_temperature=23),
        traces=[
            Trace(
                id="read",
                name="get_climate_state",
                input={},
                output={"target_temperature_c": 24},
                status="success",
            ),
            Trace(
                id="write",
                name="set_climate",
                input={"target_temperature_c": 23},
                output={"executed": True},
                status="success",
            ),
        ],
    )


def test_suite_has_three_balanced_task_types() -> None:
    suite = load_suite()
    assert suite.version == "3.0.0"
    assert len(suite.cases) == 15
    assert Counter(item.task_type for item in suite.cases) == {
        "base": 5,
        "hallucination": 5,
        "disambiguation": 5,
    }


def test_base_task_passes_all_five_dimensions() -> None:
    evaluation = evaluate_trial(case("B01"), [climate_success_step()])
    assert evaluation.passed
    assert set(evaluation.dimensions) == {
        "toolSequence",
        "finalState",
        "policy",
        "grounding",
        "uncertainty",
    }


def test_wrong_tool_order_is_explained() -> None:
    original = climate_success_step()
    reversed_step = original.model_copy(update={"traces": list(reversed(original.traces))})
    evaluation = evaluate_trial(case("B01"), [reversed_step])
    assert not evaluation.passed
    assert any("顺序错误" in reason for reason in evaluation.reasons)


def test_hallucination_task_rewards_explicit_boundary() -> None:
    evaluation = evaluate_trial(
        case("H01"),
        [step(response="当前未接入座椅按摩工具，因此无法执行。")],
    )
    assert evaluation.passed


def test_unsupported_success_claim_fails_grounding() -> None:
    evaluation = evaluate_trial(
        case("H01"),
        [step(response="已经帮你打开座椅按摩。")],
    )
    assert not evaluation.passed
    assert not evaluation.dimensions["grounding"].passed
    assert not evaluation.dimensions["uncertainty"].passed


def test_disambiguation_requires_a_question() -> None:
    good = evaluate_trial(
        case("D01"),
        [step(response="请问你希望偏热、偏冷，还是改善空气流通？")],
    )
    bad = evaluate_trial(
        case("D01"),
        [step(response="我会按默认舒适参数处理。")],
    )
    assert good.passed
    assert not bad.passed
    assert not bad.dimensions["uncertainty"].passed


def test_pass_at_k_and_pass_power_k_are_distinct() -> None:
    base = case("B01")
    hallucination = case("H01")
    evaluations = [
        evaluate_trial(base, [climate_success_step()], trial=1),
        evaluate_trial(base, [climate_success_step()], trial=2),
        evaluate_trial(
            hallucination,
            [step(response="当前未接入该能力，无法执行。")],
            trial=1,
        ),
        evaluate_trial(
            hallucination,
            [step(response="已经执行完成。")],
            trial=2,
        ),
    ]
    summary = summarize_trials(evaluations, expected_trials=2)
    assert summary["passAtK"] == 1
    assert summary["passPowerK"] == 0.5
