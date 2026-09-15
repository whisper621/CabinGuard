import pytest
from cabinguard.scenario_matrix_v7 import (
    ScenarioContract,
    build_scenario_matrix,
    score_scenario_contract,
)

CASES = build_scenario_matrix()


def test_matrix_has_exactly_200_unique_cases_and_all_scenarios() -> None:
    assert len(CASES) == 200
    assert len({case.id for case in CASES}) == 200
    assert {case.scenario for case in CASES} == {
        "default",
        "rain",
        "highway",
        "low_battery",
        "child",
        "pickup",
        "rest",
        "air_quality",
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_v7_scenario_contract(case: ScenarioContract) -> None:
    score = score_scenario_contract(case)
    assert score["passed"], score
