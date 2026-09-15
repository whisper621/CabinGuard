import json
from pathlib import Path

from cabinguard import DeepSeekClient, __version__
from cabinguard.capabilities import capability_manifest
from cabinguard.evaluation_v6 import load_composite_suite
from cabinguard.reliability import load_suite
from cabinguard.scenario_matrix_v7 import build_scenario_matrix


def test_current_status_matches_executable_registries(monkeypatch) -> None:
    path = Path(__file__).resolve().parents[2] / "docs" / "CURRENT_STATUS.json"
    status = json.loads(path.read_text(encoding="utf-8"))
    capabilities = capability_manifest()
    matrix = build_scenario_matrix()
    live_suite = load_suite()
    composite_suite = load_composite_suite()

    assert status["version"] == __version__
    assert status["architecture"]["agentBoundaries"] == capabilities["agentCount"]
    assert status["architecture"]["orchestratorAgents"] == capabilities["agentArchitecture"]["orchestrator"]
    assert status["architecture"]["domainAgentBoundaries"] == capabilities["agentArchitecture"]["domainAgents"]
    assert status["architecture"]["deterministicServices"] == capabilities["agentArchitecture"]["deterministicServices"]
    assert status["architecture"]["domains"] == len(capabilities["domains"])
    assert status["runtime"]["registeredTools"] == capabilities["toolCount"]
    assert status["runtime"]["vssAlignedSignals"] == capabilities["signalCount"]
    assert status["runtime"]["declarativeConstraints"] == capabilities["constraintCount"]
    assert status["evaluation"]["deterministicScenarioCases"] == len(matrix) == 200
    assert status["evaluation"]["compositeContracts"] == len(composite_suite.cases) == 24
    assert status["evaluation"]["liveSemanticTasks"] == len(live_suite.cases) == 50
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert status["runtime"]["defaultChatModelRequest"] == DeepSeekClient().model
