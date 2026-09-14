from cabinguard.api import app, store
from fastapi.testclient import TestClient

client = TestClient(app)


def setup_function() -> None:
    store.clear()


def test_health_identifies_python_runtime() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "python"


def test_creates_rain_session_with_frontend_shape() -> None:
    response = client.post("/api/cabin/session", json={"scenario": "rain"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sessionId"]
    assert payload["vehicle"]["rainProbability"] == 70
    assert payload["vehicle"]["cabinTemperature"] == 26.5
    assert payload["vehicle"]["locationSource"] == "simulated"


def test_creates_session_with_browser_location() -> None:
    response = client.post(
        "/api/cabin/session",
        json={
            "scenario": "default",
            "location": {
                "latitude": 31.2304,
                "longitude": 121.4737,
                "accuracyMeters": 18,
                "allowExternalRouting": True,
            },
        },
    )
    assert response.status_code == 200
    vehicle = response.json()["vehicle"]
    assert vehicle["locationSource"] == "browser_geolocation"
    assert vehicle["currentLocation"] == "浏览器授权位置"
    assert vehicle["latitude"] == 31.2304
    assert vehicle["locationAccuracyMeters"] == 18
    assert vehicle["externalRoutingConsent"] is True


def test_rejects_invalid_browser_location() -> None:
    response = client.post(
        "/api/cabin/session",
        json={"location": {"latitude": 120, "longitude": 121}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_rejects_invalid_scenario() -> None:
    response = client.post("/api/cabin/session", json={"scenario": "snow"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_rejects_blank_agent_text_as_json_error() -> None:
    response = client.post(
        "/api/deepseek/agent",
        json={
            "text": "   ",
            "sessionId": "00000000-0000-0000-0000-000000000000",
            "history": [],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["location"] == "body.text"


def test_confirmation_path_runs_without_calling_model() -> None:
    session = store.create_session("default")
    store.create_sunroof_confirmation(session, 50)
    response = client.post(
        "/api/deepseek/agent",
        json={"text": "确认继续", "sessionId": session.id, "history": []},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "server-confirmation"
    assert payload["vehicle"]["sunroof"] == 50
    assert payload["traces"][0]["output"]["executed"] is True


def test_missing_session_is_404_before_model_call() -> None:
    response = client.post(
        "/api/deepseek/agent",
        json={
            "text": "把空调调到23度",
            "sessionId": "00000000-0000-0000-0000-000000000000",
            "history": [],
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_lists_versioned_reliability_cases() -> None:
    response = client.get("/api/evaluation/cases")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "3.0.0"
    assert len(payload["cases"]) == 15


def test_scores_a_trajectory_with_python_evaluator() -> None:
    vehicle = store.create_session().vehicle.public_dict()
    vehicle["targetTemperature"] = 23
    response = client.post(
        "/api/evaluation/score",
        json={
            "caseId": "B01",
            "trial": 1,
            "trajectory": [
                {
                    "input": "把空调调到23度",
                    "response": "已将空调设置为23℃。",
                    "traces": [
                        {
                            "id": "read",
                            "name": "get_climate_state",
                            "input": {},
                            "output": {},
                            "status": "success",
                        },
                        {
                            "id": "write",
                            "name": "set_climate",
                            "input": {"target_temperature_c": 23},
                            "output": {"executed": True},
                            "status": "success",
                        },
                    ],
                    "vehicle": vehicle,
                    "model": "test-model",
                    "turns": 2,
                    "tokens": 20,
                    "latencyMs": 50,
                    "promptVersion": "test-prompt",
                    "toolVersion": "test-tools",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["passed"] is True
