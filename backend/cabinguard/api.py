from __future__ import annotations

import os
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import __version__
from .agent import AgentService, DeepSeekClient, DeepSeekError, SessionNotFoundError
from .session import SESSION_TTL_SECONDS, SessionStore

load_dotenv(".env.local")
load_dotenv(".env")


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["default", "rain", "moving"] = "default"


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


store = SessionStore()
deepseek = DeepSeekClient()
agent = AgentService(store, deepseek)

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
    }


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "python", "version": __version__}


@app.post("/api/cabin/session")
async def create_session(payload: SessionRequest, request: Request) -> JSONResponse:
    limited = _rate_limit(request, "session")
    if limited:
        return limited
    session = store.create_session(payload.scenario)
    return JSONResponse(
        {
            "sessionId": session.id,
            "scenario": session.scenario,
            "vehicle": session.vehicle.public_dict(),
            "expiresInSeconds": SESSION_TTL_SECONDS,
        }
    )


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
        )
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
