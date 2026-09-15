from cabinguard.api import app, store
from fastapi.testclient import TestClient

client = TestClient(app)


def setup_function() -> None:
    store.clear()


def test_health_identifies_python_runtime() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "python"


def test_capability_manifest_is_derived_from_runtime_registries() -> None:
    response = client.get("/api/cabin/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["agentCount"] == 3
    assert payload["toolCount"] == len(payload["tools"]) == 23
    assert payload["signalCount"] == len(payload["signals"]) == 41
    assert payload["constraintCount"] == len(payload["constraints"]) == 9
    assert any(tool["name"] == "control_cabin_device" for tool in payload["tools"])
    assert payload["agentArchitecture"]["orchestrator"] == 1
    assert len(payload["domains"]) == 6


def test_creates_rain_session_with_frontend_shape() -> None:
    response = client.post("/api/cabin/session", json={"scenario": "rain"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sessionId"]
    assert payload["vehicle"]["rainProbability"] == 70
    assert payload["vehicle"]["cabinTemperature"] == 26.5
    assert payload["vehicle"]["locationSource"] == "simulated"


def test_session_exposes_human_approved_proactive_suggestions() -> None:
    response = client.post("/api/cabin/session", json={"scenario": "low_battery"})
    assert response.status_code == 200
    suggestions = response.json()["proactiveSuggestions"]
    assert suggestions[0]["id"] == "low_battery_charge"
    assert suggestions[0]["requiresHumanConfirmation"] is True


def test_memory_consent_can_be_granted_and_revoked() -> None:
    created = client.post(
        "/api/cabin/session",
        json={"scenario": "default", "memoryProfileId": "test-browser-profile-0001"},
    ).json()
    granted = client.post(
        "/api/cabin/memory/consent",
        json={"sessionId": created["sessionId"], "granted": True, "ttlDays": 30},
    )
    assert granted.status_code == 200
    assert granted.json()["memory"]["consentGranted"] is True
    revoked = client.post(
        "/api/cabin/memory/consent",
        json={"sessionId": created["sessionId"], "granted": False},
    )
    assert revoked.status_code == 200
    assert revoked.json()["memory"]["consentGranted"] is False


def test_running_operation_has_a_cancel_endpoint() -> None:
    session = store.create_session()
    operation, decision = store.begin_operation(
        session,
        idempotency_key="api-cancel-key-0001",
        expected_state_version=session.state_version,
        timeout_seconds=45,
    )
    assert decision == "started"
    response = client.post(
        "/api/cabin/operations/cancel",
        json={"sessionId": session.id, "idempotencyKey": operation.idempotency_key},
    )
    assert response.status_code == 200
    assert response.json()["operation"]["status"] == "cancelled"


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


def test_session_exposes_occupant_role_and_state_version() -> None:
    response = client.post(
        "/api/cabin/session",
        json={"scenario": "default", "occupantRole": "rear_child"},
    )
    assert response.status_code == 200
    assert response.json()["occupantRole"] == "rear_child"
    assert response.json()["stateVersion"] == 1


def test_resumes_existing_session_without_resetting_vehicle() -> None:
    session = store.create_session("moving", occupant_role="front_passenger")
    session.vehicle = session.vehicle.model_copy(update={"battery": 27})
    store.update_vehicle(session, session.vehicle)

    response = client.get(f"/api/cabin/session/{session.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sessionId"] == session.id
    assert payload["scenario"] == "moving"
    assert payload["occupantRole"] == "front_passenger"
    assert payload["vehicle"]["battery"] == 27


def test_resume_missing_session_returns_404() -> None:
    response = client.get("/api/cabin/session/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_previews_task_plan_without_model_call() -> None:
    response = client.post("/api/cabin/plan", json={"text": "空调调到22度并导航去故宫"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "8.0.0"
    assert "set_climate" in payload["allowedTools"]
    assert "plan_navigation" in payload["allowedTools"]


def test_v8_scenario_matrix_endpoint_reports_200_passes() -> None:
    response = client.get("/api/evaluation/scenario-matrix-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "8.0.0"
    assert payload["caseCount"] == payload["passed"] == 200
    assert payload["passRate"] == 1.0
    assert set(payload["scenarioCounts"]) == {
        "default",
        "rain",
        "highway",
        "low_battery",
        "child",
        "pickup",
        "rest",
        "air_quality",
    }


def test_signal_event_updates_state_version_and_evidence() -> None:
    session = client.post(
        "/api/cabin/session", json={"scenario": "default"}
    ).json()
    response = client.post(
        "/api/cabin/signal-event",
        json={"sessionId": session["sessionId"], "event": "rain"},
    )
    assert response.status_code == 200
    assert response.json()["vehicle"]["rainProbability"] == 88
    assert response.json()["stateVersion"] == 2
    evidence = client.get(f"/api/cabin/evidence/{session['sessionId']}").json()
    assert evidence["eventCount"] == 1
    assert evidence["events"][0]["eventType"] == "signal.injected"


def test_websocket_streams_versioned_vehicle_state() -> None:
    session = client.post(
        "/api/cabin/session", json={"scenario": "default"}
    ).json()
    with client.websocket_connect(f"/ws/cabin/signals/{session['sessionId']}") as socket:
        message = socket.receive_json()
    assert message["type"] == "vehicle.state"
    assert message["stateVersion"] == 1


def test_composite_evaluation_suite_is_executable() -> None:
    response = client.get("/api/evaluation/composite-summary")
    assert response.status_code == 200
    assert response.json()["caseCount"] == 24
    assert response.json()["passRate"] == 1.0


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
    assert payload["version"] == "4.0.0"
    assert len(payload["cases"]) == 50


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
