from __future__ import annotations

import asyncio
import os
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import __version__
from .agent import AgentService, DeepSeekClient, DeepSeekError, SessionNotFoundError
from .capabilities import capability_manifest
from .evaluation_v6 import load_composite_suite, score_composite_case, suite_summary
from .planning import compile_task_plan
from .policy_kernel import OccupantRole
from .preference_store import MAX_PREFERENCE_TTL_DAYS, PreferenceStore
from .proactive import derive_proactive_suggestions
from .reliability import TrajectoryStep, evaluate_trial, load_suite
from .scenario_matrix_v7 import scenario_matrix_summary
from .session import SESSION_TTL_SECONDS, SessionStore
from .signal_player import EVENT_LABELS, SignalEventName, apply_signal_event
from .utterance import normalize_user_utterance

load_dotenv(".env.local")
load_dotenv(".env")


class BrowserLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(None, ge=0, alias="accuracyMeters")
    allow_external_routing: bool = Field(False, alias="allowExternalRouting")


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    scenario: Literal[
        "default",
        "rain",
        "moving",
        "highway",
        "low_battery",
        "child",
        "pickup",
        "rest",
        "air_quality",
    ] = "default"
    location: BrowserLocation | None = None
    occupant_role: OccupantRole = Field("driver", alias="occupantRole")
    memory_profile_id: str | None = Field(None, min_length=12, max_length=100, alias="memoryProfileId")
    memory_consent: bool = Field(False, alias="memoryConsent")


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class SignalEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    session_id: UUID = Field(alias="sessionId")
    event: SignalEventName


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    text: str = Field(min_length=1, max_length=500)
    session_id: UUID = Field(alias="sessionId")
    history: list[HistoryItem] = Field(default_factory=list, max_length=10)
    idempotency_key: str | None = Field(None, min_length=12, max_length=128, alias="idempotencyKey")
    expected_state_version: int | None = Field(None, ge=1, alias="expectedStateVersion")
    timeout_seconds: int = Field(45, ge=5, le=45, alias="timeoutSeconds")

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class InterpretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: str = Field(alias="caseId")
    trial: int = Field(default=1, ge=1, le=3)
    trajectory: list[TrajectoryStep] = Field(min_length=1, max_length=4)


class MemoryConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    granted: bool
    ttl_days: int = Field(90, ge=1, le=MAX_PREFERENCE_TTL_DAYS, alias="ttlDays")
    delete_preferences: bool = Field(True, alias="deletePreferences")


class OperationCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    idempotency_key: str | None = Field(None, min_length=12, max_length=128, alias="idempotencyKey")


store = SessionStore()
deepseek = DeepSeekClient()
preferences = PreferenceStore()
agent = AgentService(store, deepseek, preferences=preferences)

app = FastAPI(
    title="CabinGuard Python Agent API",
    version=__version__,
    description="可信智能座舱任务 Agent：模型规划，服务端工具授权、执行与核验。",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CABINGUARD_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "invalid_request",
                "message": "请求字段、类型或长度不符合接口约束",
                "details": [
                    {
                        "location": ".".join(str(part) for part in issue["loc"]),
                        "message": issue["msg"],
                        "type": issue["type"],
                    }
                    for issue in error.errors()
                ],
            }
        },
    )


def _client_key(request: Request, prefix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    host = request.client.host if request.client else "local-anonymous"
    return f"{prefix}:{forwarded or host}"


def _rate_limit(request: Request, prefix: str) -> JSONResponse | None:
    allowed, retry_after = store.consume_rate_limit(_client_key(request, prefix))
    if allowed:
        return None
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={"error": {"code": "rate_limited", "message": "请求过于频繁，请稍后再试"}},
    )


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "name": "CabinGuard Python Agent API",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
        "capabilities": "/api/cabin/capabilities",
    }


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "python", "version": __version__}


@app.get("/api/cabin/capabilities")
async def capabilities() -> dict[str, object]:
    """Return capabilities derived from the executable Python registries."""

    return capability_manifest()


@app.post("/api/cabin/session")
async def create_session(payload: SessionRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "session")
    if limited:
        return limited
    location = payload.location
    if payload.memory_consent and payload.memory_profile_id:
        preferences.grant(payload.memory_profile_id)
    session = store.create_session(
        payload.scenario,
        latitude=location.latitude if location else None,
        longitude=location.longitude if location else None,
        accuracy_meters=location.accuracy_meters if location else None,
        allow_external_routing=location.allow_external_routing if location else False,
        occupant_role=payload.occupant_role,
        memory_profile_id=payload.memory_profile_id,
        memory_consent=payload.memory_consent,
    )
    return JSONResponse(
        {
            "sessionId": session.id,
            "scenario": session.scenario,
            "vehicle": session.vehicle.public_dict(),
            "expiresInSeconds": SESSION_TTL_SECONDS,
            "occupantRole": session.occupant_role,
            "stateVersion": session.state_version,
            "memory": preferences.public_status(session.memory_profile_id)
            if session.memory_consent
            else {
                "scope": "current_demo_session",
                "consentGranted": False,
                "retention": "仅本次 30 分钟演示会话。",
                "preferences": dict(session.preferences),
                "deletion": "会话过期后自动清除。",
            },
            "proactiveSuggestions": [item.public_dict() for item in derive_proactive_suggestions(session.vehicle)],
        }
    )


@app.get("/api/cabin/session/{session_id}")
async def resume_session(session_id: UUID) -> JSONResponse:
    session = store.get_session(str(session_id))
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "session_not_found", "message": "演示会话已过期"}},
        )
    return JSONResponse(
        {
            "sessionId": session.id,
            "scenario": session.scenario,
            "vehicle": session.vehicle.public_dict(),
            "expiresInSeconds": SESSION_TTL_SECONDS,
            "occupantRole": session.occupant_role,
            "stateVersion": session.state_version,
            "memory": preferences.public_status(session.memory_profile_id)
            if session.memory_consent
            else {
                "scope": "current_demo_session",
                "consentGranted": False,
                "retention": "仅本次 30 分钟演示会话。",
                "preferences": dict(session.preferences),
                "deletion": "会话过期后自动清除。",
            },
            "proactiveSuggestions": [item.public_dict() for item in derive_proactive_suggestions(session.vehicle)],
        }
    )


@app.post("/api/cabin/plan")
async def preview_plan(payload: PlanRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "plan")
    if limited:
        return limited
    return JSONResponse(compile_task_plan(normalize_user_utterance(payload.text)).public_dict())


@app.get("/api/cabin/evidence/{session_id}")
async def evidence(session_id: UUID) -> JSONResponse:
    session = store.get_session(str(session_id))
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "session_not_found", "message": "演示会话已过期"}},
        )
    events = agent.events.list_events(session.id)
    return JSONResponse(
        {
            "sessionId": session.id,
            "occupantRole": session.occupant_role,
            "stateVersion": session.state_version,
            "eventCount": len(events),
            "events": events,
        }
    )


@app.get("/api/cabin/proactive/{session_id}")
async def proactive_suggestions(session_id: UUID) -> JSONResponse:
    session = store.get_session(str(session_id))
    if session is None:
        return JSONResponse(status_code=404, content={"error": {"code": "session_not_found", "message": "演示会话已过期"}})
    return JSONResponse(
        {
            "sessionId": session.id,
            "suggestions": [item.public_dict() for item in derive_proactive_suggestions(session.vehicle)],
            "executionBoundary": "建议不会自动执行；用户接受后仍需经过 TaskPlan、ABAC 与策略核。",
        }
    )


@app.get("/api/cabin/memory/{session_id}")
async def memory_status(session_id: UUID) -> JSONResponse:
    session = store.get_session(str(session_id))
    if session is None:
        return JSONResponse(status_code=404, content={"error": {"code": "session_not_found", "message": "演示会话已过期"}})
    if session.memory_consent:
        payload = preferences.public_status(session.memory_profile_id)
    else:
        payload = {
            "scope": "current_demo_session",
            "consentGranted": False,
            "preferences": dict(session.preferences),
            "deletion": "当前偏好会随演示会话过期；开启长期偏好前需要明确授权。",
        }
    return JSONResponse({"sessionId": session.id, **payload})


@app.post("/api/cabin/memory/consent")
async def set_memory_consent(payload: MemoryConsentRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "memory-consent")
    if limited:
        return limited
    session = store.get_session(str(payload.session_id))
    if session is None:
        return JSONResponse(status_code=404, content={"error": {"code": "session_not_found", "message": "演示会话已过期"}})
    if not session.memory_profile_id:
        return JSONResponse(status_code=400, content={"error": {"code": "memory_profile_missing", "message": "当前浏览器未提供匿名偏好档标识，无法开启长期偏好。"}})
    if payload.granted:
        preferences.grant(session.memory_profile_id, ttl_days=payload.ttl_days)
        store.set_memory_consent(session, True)
    else:
        preferences.revoke(session.memory_profile_id, delete_preferences=payload.delete_preferences)
        store.set_memory_consent(session, False)
    agent.events.append(
        session_id=session.id,
        plan_id=session.active_plan_id,
        event_type="memory.consent",
        state_version=session.state_version,
        payload={"granted": payload.granted, "ttlDays": payload.ttl_days, "deletePreferences": payload.delete_preferences},
    )
    return JSONResponse({"sessionId": session.id, "memory": preferences.public_status(session.memory_profile_id)})


@app.post("/api/cabin/operations/cancel")
async def cancel_operation(payload: OperationCancelRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "operation-cancel")
    if limited:
        return limited
    session = store.get_session(str(payload.session_id))
    if session is None:
        return JSONResponse(status_code=404, content={"error": {"code": "session_not_found", "message": "演示会话已过期"}})
    operation = store.cancel_operation(session, idempotency_key=payload.idempotency_key)
    if operation is None:
        return JSONResponse(status_code=409, content={"error": {"code": "operation_not_running", "message": "没有可取消的运行中任务"}})
    event = agent.events.append(
        session_id=session.id,
        plan_id=session.active_plan_id,
        event_type="operation.cancelled",
        state_version=session.state_version,
        payload=operation.public_dict(),
    )
    return JSONResponse({"sessionId": session.id, "operation": operation.public_dict(), "event": event})


@app.post("/api/cabin/signal-event")
async def inject_signal_event(payload: SignalEventRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "signal-event")
    if limited:
        return limited
    session = store.get_session(str(payload.session_id))
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "session_not_found", "message": "演示会话已过期"}},
        )
    result = apply_signal_event(payload.event, session.vehicle)
    before = session.state_version
    store.update_vehicle(session, result.vehicle)
    event = agent.events.append(
        session_id=session.id,
        plan_id=session.active_plan_id,
        event_type="signal.injected",
        state_version=session.state_version,
        payload={
            "event": result.name,
            "label": result.label,
            "changedSignals": result.changed_signals,
            "stateVersionBefore": before,
        },
    )
    return JSONResponse(
        {
            "event": event,
            "vehicle": result.vehicle.public_dict(),
            "stateVersion": session.state_version,
            "proactiveSuggestions": [item.public_dict() for item in derive_proactive_suggestions(result.vehicle)],
        }
    )


@app.get("/api/cabin/signal-events")
async def signal_events() -> dict[str, object]:
    return {
        "events": [
            {"id": event, "label": label} for event, label in EVENT_LABELS.items()
        ]
    }


@app.websocket("/ws/cabin/signals/{session_id}")
async def signal_stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    last_version = -1
    try:
        while True:
            session = store.get_session(session_id)
            if session is None:
                await websocket.send_json({"type": "session.expired"})
                await websocket.close(code=1008)
                return
            if session.state_version != last_version:
                last_version = session.state_version
                await websocket.send_json(
                    {
                        "type": "vehicle.state",
                        "sessionId": session.id,
                        "stateVersion": session.state_version,
                        "vehicle": session.vehicle.public_dict(),
                    }
                )
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return


@app.post("/api/deepseek/agent")
async def run_agent(payload: AgentRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "agent")
    if limited:
        return limited
    try:
        result = await agent.run(
            text=payload.text,
            session_id=str(payload.session_id),
            history=[item.model_dump() for item in payload.history],
            idempotency_key=payload.idempotency_key,
            expected_state_version=payload.expected_state_version,
            timeout_seconds=payload.timeout_seconds,
        )
        session = store.get_session(str(payload.session_id))
        if session is not None:
            result["proactiveSuggestions"] = [item.public_dict() for item in derive_proactive_suggestions(session.vehicle)]
        return JSONResponse(result)
    except SessionNotFoundError as error:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "session_not_found", "message": str(error)}},
        )
    except DeepSeekError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": "provider_error", "message": str(error)}},
        )


@app.post("/api/deepseek/interpret")
async def interpret(payload: InterpretRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "interpret")
    if limited:
        return limited
    try:
        return JSONResponse(await deepseek.interpret(payload.text))
    except DeepSeekError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": "provider_error", "message": str(error)}},
        )


@app.get("/api/evaluation/cases")
async def evaluation_cases() -> dict[str, object]:
    suite = load_suite()
    return suite.model_dump(by_alias=True)


@app.get("/api/evaluation/composite-cases")
async def composite_evaluation_cases() -> dict[str, object]:
    return load_composite_suite().model_dump(by_alias=True)


@app.get("/api/evaluation/composite-summary")
async def composite_evaluation_summary() -> dict[str, object]:
    return suite_summary()


@app.get("/api/evaluation/scenario-matrix-summary")
async def scenario_matrix_evaluation_summary() -> dict[str, object]:
    return scenario_matrix_summary()


@app.get("/api/evaluation/composite-score/{case_id}")
async def composite_evaluation_score(case_id: str) -> JSONResponse:
    case = next((item for item in load_composite_suite().cases if item.id == case_id), None)
    if case is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "evaluation_case_not_found", "message": "组合评测用例不存在"}},
        )
    return JSONResponse(score_composite_case(case).model_dump(by_alias=True))


@app.post("/api/evaluation/score")
async def score_evaluation(payload: ScoreRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "evaluation")
    if limited:
        return limited
    suite = load_suite()
    case = next((item for item in suite.cases if item.id == payload.case_id), None)
    if case is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "evaluation_case_not_found",
                    "message": "评测用例不存在",
                }
            },
        )
    evaluation = evaluate_trial(case, payload.trajectory, trial=payload.trial)
    return JSONResponse(evaluation.public_dict())
