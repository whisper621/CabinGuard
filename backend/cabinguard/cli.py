from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from .agent import AgentService, DeepSeekError
from .reliability import load_suite, run_suite
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


def run_benchmark(args: argparse.Namespace) -> None:
    suite = load_suite()
    if args.list:
        for case in suite.cases:
            print(f"{case.id}\t{case.task_type}\t{case.title}\t{len(case.turns)} turn(s)")
        return
    if args.task_type == "all" and args.trials == 3 and not args.allow_large_run:
        raise SystemExit(
            "为控制模型成本，all + 3 trials 需要显式添加 --allow-large-run；"
            "面试演示建议先选择单一 --task-type。"
        )

    store = SessionStore()
    report = asyncio.run(
        run_suite(
            AgentService(store),
            store,
            task_type=args.task_type,
            trials=args.trials,
            case_ids=args.case,
        )
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.output:
        output_path = Path(args.output)
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output_path = Path("evaluation") / "results" / f"reliability-{stamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已保存：{output_path}")


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

    benchmark = subparsers.add_parser(
        "benchmark", help="运行 Base / Hallucination / Disambiguation 可靠性评测"
    )
    benchmark.add_argument(
        "--task-type",
        choices=["all", "base", "hallucination", "disambiguation"],
        default="all",
    )
    benchmark.add_argument("--trials", choices=[1, 3], type=int, default=1)
    benchmark.add_argument("--case", action="append", default=[])
    benchmark.add_argument("--output")
    benchmark.add_argument("--list", action="store_true")
    benchmark.add_argument("--allow-large-run", action="store_true")
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
    if command == "benchmark":
        run_benchmark(args)
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
