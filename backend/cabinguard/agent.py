from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import Trace, VehicleState
from .policy import (
    classify_confirmation,
    ground_agent_message,
    is_navigation_requested,
)
from .session import CabinSession, SessionStore
from .tools import TOOL_DEFINITIONS, TOOL_VERSION, ToolContext, execute_tool

AGENT_PROMPT_VERSION = "3.0.0-python"
MAX_AGENT_TURNS = 6

SYSTEM_PROMPT = """你是 CabinGuard，一名可信的智能座舱任务 Agent。你的职责是把用户目标转成真实工具调用，并依据工具返回值用简洁中文反馈。

执行规则：
1. 调节空调前先读取 get_climate_state；涉及天窗先读取 get_vehicle_state 和 get_weather；补能前先读取 get_vehicle_state。
2. 不得编造状态、地点、执行成功或工具结果。只有工具返回 executed=true 或 navigation_started=true 才能声称完成。
3. 车速不低于 80 km/h 时，开启天窗前必须读取状态和天气，再调用 control_sunroof 且 confirmed=false，让工具层创建一次性确认状态；工具层返回确认要求后，向用户说明风噪风险。用户下一轮明确确认时由服务端恢复该动作。降雨概率不低于 50% 时不要开启天窗。
4. 收到后备箱请求时，先调用 get_vehicle_state，再调用 control_trunk，由工具层执行最终安全校验并返回是否被拦截；不要只凭模型判断后直接结束。
5. “舒服一点”等缺少关键偏好的表达应先追问；明确温度或循环模式时可以执行。
6. 找到充电站后，仅在用户明确要求导航时调用 start_navigation。
7. 一次请求可能需要多次工具调用。根据上一个工具返回继续决策，直到完成、需要澄清或被安全规则阻止。
8. 最终回复控制在 120 字内，说明执行对象、关键参数、结果或未执行原因。"""


class DeepSeekError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class SessionNotFoundError(LookupError):
    pass


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: str = Field(pattern="^(sunroof|charging|climate|trunk|status|unknown)$")
    percent: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=16, le=30)
    circulation: str | None = Field(default=None, pattern="^(inside|outside)$")
    confidence: float = Field(ge=0, le=1)


@dataclass
class ModelResult:
    message: dict[str, Any]
    model: str
    usage: dict[str, int]


class DeepSeekClient:
    """Small OpenAI-compatible client with bounded retries and timeouts."""

    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.transport = transport

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY is not configured", status_code=503)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(30.0, connect=15.0)
        last_error: Exception | None = None

        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self.transport,
            trust_env=True,
        ) as client:
            for attempt in range(1, 4):
                try:
                    response = await client.post(self.endpoint, headers=headers, json=payload)
                    data = response.json()
                    if 200 <= response.status_code < 300:
                        if not isinstance(data, dict):
                            raise DeepSeekError("DeepSeek returned invalid JSON")
                        return data
                    message = (
                        data.get("error", {}).get("message") if isinstance(data, dict) else None
                    )
                    error = DeepSeekError(
                        message or f"DeepSeek request failed: {response.status_code}",
                        status_code=response.status_code,
                    )
                    if response.status_code < 500 or attempt == 3:
                        raise error
                    last_error = error
                except DeepSeekError:
                    raise
                except (httpx.HTTPError, json.JSONDecodeError) as error:
                    last_error = error
                    if attempt == 3:
                        break
                await asyncio.sleep(attempt * 0.25)

        raise DeepSeekError(str(last_error) if last_error else "DeepSeek request failed")

    async def call(self, messages: Sequence[dict[str, Any]]) -> ModelResult:
        data = await self._post(
            {
                "model": self.model,
                "messages": list(messages),
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "stream": False,
                "max_tokens": 700,
                "temperature": 0.1,
            }
        )
        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else None
        if not isinstance(message, dict):
            raise DeepSeekError("DeepSeek returned no message")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return ModelResult(
            message=message,
            model=str(data.get("model") or self.model),
            usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
        )

    async def interpret(self, text: str) -> dict[str, Any]:
        data = await self._post(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是智能座舱任务解析器。只输出JSON对象，不要输出解释。"
                            "intent只能是sunroof、charging、climate、trunk、status、unknown之一。"
                            '字段格式：{"intent":"...","percent":number|null,'
                            '"temperature":number|null,"circulation":"inside"|"outside"|null,'
                            '"confidence":0到1}。不要声称任务已执行。'
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"},
                "max_tokens": 160,
                "stream": False,
            }
        )
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(content, str) or not content:
            raise DeepSeekError("DeepSeek returned no interpretation")
        try:
            interpretation = Interpretation.model_validate_json(content)
        except ValidationError as error:
            raise DeepSeekError("DeepSeek returned an invalid interpretation") from error
        return {
            "interpretation": interpretation.model_dump(),
            "model": str(data.get("model") or self.model),
            "usage": data.get("usage") or {},
        }


class AgentService:
    def __init__(
        self,
        store: SessionStore,
        client: DeepSeekClient | None = None,
    ) -> None:
        self.store = store
        self.client = client or DeepSeekClient()

    @staticmethod
    def _response(
        *,
        message: str,
        session: CabinSession,
        vehicle: VehicleState,
        traces: Sequence[Trace],
        model: str,
        turns: int,
        total_tokens: int,
        stopped: bool = False,
    ) -> dict[str, Any]:
        response: dict[str, Any] = {
            "message": message,
            "sessionId": session.id,
            "vehicle": vehicle.public_dict(),
            "traces": [trace.public_dict() for trace in traces],
            "model": model,
            "turns": turns,
            "totalTokens": total_tokens,
            "promptVersion": AGENT_PROMPT_VERSION,
            "toolVersion": TOOL_VERSION,
        }
        if stopped:
            response["stopped"] = True
        return response

    def _handle_pending_confirmation(
        self, session: CabinSession, text: str
    ) -> dict[str, Any] | None:
        if session.pending_action is None:
            return None

        decision = classify_confirmation(text)
        if decision == "cancel":
            self.store.clear_pending_action(session)
            return self._response(
                message="已取消本次高速天窗操作。",
                session=session,
                vehicle=session.vehicle,
                traces=[],
                model="server-confirmation",
                turns=0,
                total_tokens=0,
            )

        if decision == "confirm":
            pending = self.store.take_sunroof_confirmation(session)
            if pending:
                tool_input = {
                    "target_percent": pending.target_percent,
                    "confirmed": True,
                }
                execution = execute_tool(
                    "control_sunroof",
                    tool_input,
                    session.vehicle,
                    ToolContext(
                        allow_high_speed_sunroof=True,
                        bypass_read_prerequisites=True,
                    ),
                )
                self.store.update_vehicle(session, execution.vehicle)
                trace = Trace(
                    id=f"server-confirmation-{int(asyncio.get_event_loop().time() * 1000)}",
                    name="control_sunroof",
                    input=tool_input,
                    output=execution.output,
                    status=execution.status,
                )
                result_message = (
                    f"已根据你的确认，将天窗打开至 {pending.target_percent}%。"
                    if execution.status == "success"
                    else f"本次天窗操作未执行：{execution.output.get('reason', '安全条件不满足')}。"
                )
                return self._response(
                    message=result_message,
                    session=session,
                    vehicle=execution.vehicle,
                    traces=[trace],
                    model="server-confirmation",
                    turns=0,
                    total_tokens=0,
                )

        return self._response(
            message="我没有执行天窗操作。请明确回复“确认继续”或“取消”，其他表达不会被视为高风险授权。",
            session=session,
            vehicle=session.vehicle,
            traces=[],
            model="server-confirmation",
            turns=0,
            total_tokens=0,
        )

    async def run(
        self,
        *,
        text: str,
        session_id: str,
        history: Sequence[dict[str, str]] = (),
    ) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if session is None:
            raise SessionNotFoundError("演示会话已过期，请重置后重试")

        confirmation_response = self._handle_pending_confirmation(session, text)
        if confirmation_response is not None:
            return confirmation_response

        vehicle = session.vehicle
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": item["role"], "content": item["content"]} for item in history],
            {"role": "user", "content": text},
        ]
        traces: list[Trace] = []
        model_name = "deepseek"
        total_tokens = 0

        for turn in range(1, MAX_AGENT_TURNS + 1):
            result = await self.client.call(messages)
            model_name = result.model
            total_tokens += result.usage.get("total_tokens", 0)
            tool_calls = result.message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                tool_calls = []

            if not tool_calls:
                self.store.update_vehicle(session, vehicle)
                fallback = result.message.get("content")
                final_message = (
                    fallback
                    if isinstance(fallback, str) and fallback
                    else "我暂时无法完成该请求，请换一种说法。"
                )
                return self._response(
                    message=ground_agent_message(final_message, traces),
                    session=session,
                    vehicle=vehicle,
                    traces=traces,
                    model=model_name,
                    turns=turn,
                    total_tokens=total_tokens,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": result.message.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for index, tool_call in enumerate(tool_calls):
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue
                name = str(function.get("name") or "")
                raw_arguments = function.get("arguments") or "{}"
                try:
                    tool_input = (
                        json.loads(raw_arguments)
                        if isinstance(raw_arguments, str)
                        else raw_arguments
                    )
                    if not isinstance(tool_input, dict):
                        tool_input = {}
                except json.JSONDecodeError:
                    tool_input = {}

                successful_tools = tuple(
                    trace.name for trace in traces if trace.status == "success"
                )
                allowed_destinations = tuple(
                    str(station["name"])
                    for trace in traces
                    if trace.name == "search_charging_stations" and trace.status == "success"
                    for station in trace.output.get("stations", [])
                    if isinstance(station, dict) and isinstance(station.get("name"), str)
                )
                execution = execute_tool(
                    name,
                    tool_input,
                    vehicle,
                    ToolContext(
                        prior_successful_tools=successful_tools,
                        navigation_authorized=is_navigation_requested(text),
                        allowed_navigation_destinations=allowed_destinations,
                        on_sunroof_confirmation_required=lambda target: (
                            self.store.create_sunroof_confirmation(session, target)
                        ),
                    ),
                )
                vehicle = execution.vehicle
                self.store.update_vehicle(session, vehicle)
                tool_call_id = str(tool_call.get("id") or f"tool-{turn}-{index}")
                trace = Trace(
                    id=tool_call_id,
                    name=name,
                    input=tool_input,
                    output=execution.output,
                    status=execution.status,
                )
                traces.append(trace)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(execution.output, ensure_ascii=False),
                    }
                )

        return self._response(
            message="任务执行步骤超过上限，我已停止继续操作，请拆分请求后重试。",
            session=session,
            vehicle=vehicle,
            traces=traces,
            model=model_name,
            turns=MAX_AGENT_TURNS,
            total_tokens=total_tokens,
            stopped=True,
        )
