# CabinGuard Python Agent 后端

这里是 CabinGuard 的 Agent 主实现，不是占位脚本。它可以独立运行，并对现有 Next.js 产品界面提供相同形状的 API。

## 代码入口

| 文件 | 职责 |
| --- | --- |
| `cabinguard/api.py` | FastAPI、CORS、请求校验、限流与 OpenAPI |
| `cabinguard/agent.py` | DeepSeek 多轮 Tool Calling、工具结果回传、轮次/超时/重试 |
| `cabinguard/tools.py` | 8 个 Pydantic 工具 Schema、前置条件和动作执行 |
| `cabinguard/policy.py` | 高风险确认、导航意图和无依据成功反馈拦截 |
| `cabinguard/session.py` | 车辆模拟状态、30 分钟会话、2 分钟一次性确认和限流 |
| `cabinguard/cli.py` | `serve`、`demo`、`chat` 三个 Python 入口 |
| `tests/` | 51 条多轮 Agent、确定性工具与 API 测试 |

## 运行

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m cabinguard demo
python -m cabinguard
```

API 默认地址为 `http://127.0.0.1:8000`，交互文档为 `http://127.0.0.1:8000/docs`。

配置 `DEEPSEEK_API_KEY` 后还可以运行终端 Agent：

```powershell
python -m cabinguard chat --scenario default
```

测试命令：

```powershell
python -m pytest
python -m ruff check backend
```

## API

- `GET /api/health`：运行状态与 Python 版本标识。
- `POST /api/cabin/session`：创建 `default`、`rain` 或 `moving` 演示会话。
- `POST /api/deepseek/agent`：执行多轮 Tool Calling 任务。
- `POST /api/deepseek/interpret`：为首页提供结构化意图解析。

该后端使用模拟车况和内存会话验证 Agent 策略，不可直接连接真实车控执行端。
