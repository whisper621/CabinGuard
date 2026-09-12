"""One-click CabinGuard launcher for Python IDEs and terminals."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_DIRECTORY = PROJECT_ROOT / ".runtime"
STATE_PATH = RUNTIME_DIRECTORY / "demo-processes.json"
API_HEALTH_URL = "http://127.0.0.1:8000/api/health"
AGENT_LAB_URL = "http://localhost:3000/agent-lab"


def python_executable() -> Path:
    if os.name == "nt":
        path = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        path = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not path.exists():
        raise RuntimeError(
            '未找到 .venv。请先创建虚拟环境并执行：python -m pip install -e ".[dev]"'
        )
    return path


def endpoint_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:  # noqa: S310 - fixed localhost URLs
            return response.status == 200
    except (OSError, URLError):
        return False


def port_is_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def wait_for_endpoint(
    name: str,
    url: str,
    timeout_seconds: int,
    process: subprocess.Popen[Any],
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if endpoint_is_ready(url):
            print(f"[OK] {name} 已就绪：{url}", flush=True)
            return
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"{name} 启动失败，退出码：{exit_code}")
        time.sleep(0.5)
    raise RuntimeError(f"{name} 在 {timeout_seconds} 秒内没有就绪")


def process_flags() -> int:
    if os.name == "nt":
        return subprocess.CREATE_NEW_PROCESS_GROUP
    return 0


def stop_process_tree(process_id: int) -> None:
    if process_id <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process_id), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(process_id, signal.SIGTERM)
    except ProcessLookupError:
        pass


def read_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def stop_saved_processes() -> None:
    state = read_state()
    if not state:
        print("没有找到由一键启动器创建的运行进程。")
        return
    print("正在停止 CabinGuard...", flush=True)
    stop_process_tree(int(state.get("frontendPid", 0)))
    stop_process_tree(int(state.get("backendPid", 0)))
    STATE_PATH.unlink(missing_ok=True)
    print("[OK] CabinGuard 已停止。", flush=True)


def frontend_command(npm_path: str) -> list[str]:
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", npm_path, "run", "dev"]
    return [npm_path, "run", "dev"]


def start_showcase(*, open_browser: bool) -> None:
    python_path = python_executable()
    npm_path = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm_path is None:
        raise RuntimeError("未找到 npm，请先安装 Node.js 20+")
    if not (PROJECT_ROOT / "node_modules").exists():
        raise RuntimeError("未找到 node_modules，请先在项目根目录执行：npm install")

    os.chdir(PROJECT_ROOT)
    RUNTIME_DIRECTORY.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["NEXT_PUBLIC_CABINGUARD_API_URL"] = "http://127.0.0.1:8000"

    print("CabinGuard Python 一键演示启动器", flush=True)
    print(f"项目目录：{PROJECT_ROOT}", flush=True)
    print(f"Python：{python_path}", flush=True)
    print("按 Ctrl+C 或点击 IDE 的停止按钮可关闭全部服务。\n", flush=True)

    owned_processes: list[subprocess.Popen[Any]] = []
    backend_pid = 0
    frontend_pid = 0
    previous_state = read_state()

    try:
        if endpoint_is_ready(API_HEALTH_URL):
            print("[OK] Python API 已在运行，直接复用。", flush=True)
            backend_pid = int(previous_state.get("backendPid", 0))
        else:
            if port_is_in_use(8000):
                raise RuntimeError("8000 端口已被其他程序占用")
            print("[1/2] 启动 Python/FastAPI...", flush=True)
            backend = subprocess.Popen(
                [str(python_path), "-m", "cabinguard"],
                cwd=PROJECT_ROOT,
                env=environment,
                creationflags=process_flags(),
                start_new_session=os.name != "nt",
            )
            owned_processes.append(backend)
            backend_pid = backend.pid
            wait_for_endpoint("Python API", API_HEALTH_URL, 30, backend)

        if endpoint_is_ready(AGENT_LAB_URL):
            print("[OK] Next.js 网页已在运行，直接复用。", flush=True)
            frontend_pid = int(previous_state.get("frontendPid", 0))
        else:
            if port_is_in_use(3000):
                raise RuntimeError("3000 端口已被其他程序占用")
            print("[2/2] 启动 Next.js，并连接 Python API...", flush=True)
            frontend = subprocess.Popen(
                frontend_command(npm_path),
                cwd=PROJECT_ROOT,
                env=environment,
                creationflags=process_flags(),
                start_new_session=os.name != "nt",
            )
            owned_processes.append(frontend)
            frontend_pid = frontend.pid
            wait_for_endpoint("Next.js Agent Lab", AGENT_LAB_URL, 45, frontend)

        STATE_PATH.write_text(
            json.dumps(
                {
                    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "backendPid": backend_pid,
                    "frontendPid": frontend_pid,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print("\nCabinGuard 已完整启动。", flush=True)
        print("产品主页：       http://localhost:3000", flush=True)
        print("Agent Lab：      http://localhost:3000/agent-lab", flush=True)
        print("Reliability Lab：http://localhost:3000/evaluation", flush=True)
        print("Python API：     http://127.0.0.1:8000/docs", flush=True)

        if open_browser:
            webbrowser.open(AGENT_LAB_URL)

        if not owned_processes:
            return
        while True:
            for process in owned_processes:
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(f"服务进程 {process.pid} 意外退出：{exit_code}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到停止指令。", flush=True)
    finally:
        for process in reversed(owned_processes):
            stop_process_tree(process.pid)
        if owned_processes:
            STATE_PATH.unlink(missing_ok=True)
            print("[OK] CabinGuard 全部服务已关闭。", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CabinGuard Python one-click launcher")
    parser.add_argument("--stop", action="store_true", help="停止启动器记录的服务")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stop:
        stop_saved_processes()
        return
    start_showcase(open_browser=not args.no_browser)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"\n启动失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error
