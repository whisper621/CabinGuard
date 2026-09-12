from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from dotenv import load_dotenv

from .agent import AgentService, DeepSeekError
from .session import SessionStore
from .tools import ToolContext, execute_tool


def _load_environment() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")


def run_demo() -> None:
    """Run a deterministic Python-only workflow without an API key."""

    store = SessionStore()
    session = store.create_session("default")
    traces: list[dict[str, object]] = []

    read = execute_tool("get_climate_state", {}, session.vehicle)
    traces.append({"tool": "get_climate_state", "status": read.status, "output": read.output})
    write = execute_tool(
        "set_climate",
        {
            "target_temperature_c": 23,
            "fan_level": 3,
            "circulation": "外循环",
        },
        read.vehicle,
        ToolContext(prior_successful_tools=("get_climate_state",)),
    )
    store.update_vehicle(session, write.vehicle)
    traces.append({"tool": "set_climate", "status": write.status, "output": write.output})
    print(
        json.dumps(
            {
                "message": "Python 工具闭环执行完成",
                "vehicle": write.vehicle.public_dict(),
                "traces": traces,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def run_chat(scenario: str) -> None:
    store = SessionStore()
    session = store.create_session(scenario)  # type: ignore[arg-type]
    service = AgentService(store)
    history: list[dict[str, str]] = []
    print(f"CabinGuard Python Agent 已启动，会话 {session.id[:8]}，输入 exit 退出。")
    while True:
        try:
            text = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in {"exit", "quit", "退出"}:
            return
        if not text:
            continue
        try:
            result = await service.run(
                text=text,
                session_id=session.id,
                history=history[-10:],
            )
        except DeepSeekError as error:
            print(f"Agent 调用失败：{error}")
            continue
        message = str(result["message"])
        print(f"CabinGuard：{message}")
        history.extend(
            [
                {"role": "user", "content": text},
                {"role": "assistant", "content": message},
            ]
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabinguard",
        description="CabinGuard Python Agent backend",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="启动 FastAPI 服务（默认）")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--reload", action="store_true")

    subparsers.add_parser("demo", help="运行无需模型密钥的确定性 Python 演示")

    chat = subparsers.add_parser("chat", help="在终端运行 DeepSeek Tool Calling Agent")
    chat.add_argument(
        "--scenario",
        choices=["default", "rain", "moving"],
        default="default",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    _load_environment()
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "demo":
        run_demo()
        return
    if command == "chat":
        asyncio.run(run_chat(args.scenario))
        return

    import uvicorn

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    reload_enabled = getattr(args, "reload", False)
    uvicorn.run(
        "cabinguard.api:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )
