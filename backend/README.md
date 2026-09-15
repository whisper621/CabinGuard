# CabinGuard Python Agent 后端

这里是 CabinGuard 的 Agent 主实现，不是占位脚本。它可以独立运行，并对现有 Next.js 产品界面提供相同形状的 API。

## 代码入口

| 文件 | 职责 |
| --- | --- |
| `cabinguard/api.py` | FastAPI、CORS、请求校验、限流与 OpenAPI |
| `cabinguard/agent.py` | DeepSeek 多轮 Tool Calling、工具结果回传、轮次/超时/重试 |
| `cabinguard/planning.py` | 将用户目标编译成带依赖、波次、风险与工具白名单的 TaskPlan |
| `cabinguard/domains.py` | 主编排、导航领域与确定性服务的 Manifest 和工具边界 |
| `cabinguard/policy_kernel.py` | TaskPlan 白名单与驾驶员/前排/儿童/访客 ABAC |
| `cabinguard/event_store.py` | SQLite 追加式计划、策略、工具与信号证据账本 |
| `cabinguard/signal_player.py` | 高速、驻车、降雨、低电量等 VSS 时序事件 |
| `cabinguard/evaluation_v6.py` | 24 个组合场景的确定性契约评分 |
| `cabinguard/scenario_matrix_v7.py` | 200 条场景、组合任务、口语变体与 ABAC 契约评分 |
| `cabinguard/tools.py` | 23 个 Pydantic 工具 Schema、前置条件和动作执行 |
| `cabinguard/signals.py` | 41 个 VSS 对齐信号、分段 glob 和 9 条声明式安全约束 |
| `cabinguard/capabilities.py` | 由真实注册表生成工具、信号、约束、集成与执行图清单 |
| `cabinguard/memory.py` / `preference_store.py` | 默认会话偏好、明确授权的 TTL 本地偏好与成功导航行程回执 |
| `cabinguard/proactive.py` | 低电、雨窗、空气与结构化感知事件的需用户接受建议 |
| `cabinguard/charging.py` | OpenStreetMap 补能 POI 查询与明确标注的 Demo Catalog 降级 |
| `cabinguard/navigation.py` | Nominatim 地点检索、OSRM 道路算路、缓存限流和坐标隔离 |
| `cabinguard/policy.py` | 高风险确认、导航意图和无依据成功反馈拦截 |
| `cabinguard/session.py` | 车辆状态、30 分钟会话、一次性确认、幂等/冲突/超时/取消和限流 |
| `cabinguard/reliability.py` | 共享任务加载、多轮运行、五维确定性评分和 Pass 指标 |
| `cabinguard/cli.py` | `serve`、`demo`、`capabilities`、`chat`、`benchmark` 五个 Python 入口 |
| `tests/` | 342 条多轮 Agent、任务图、生命周期、ABAC、证据、WebSocket、地图、工具与评测测试 |

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

列出评测任务，或只运行一类任务：

```powershell
python -m cabinguard benchmark --list
python -m cabinguard benchmark --task-type disambiguation --trials 1
```

`--trials 3` 会计算 Pass^k 与 Pass@k。为避免误触付费模型，全量任务重复 3 次还需显式传入 `--allow-large-run`。报告默认写入被 Git 忽略的 `evaluation/results/`。

测试命令：

```powershell
python -m pytest
python -m ruff check backend
```

## API

- `GET /api/health`：运行状态与 Python 版本标识。
- `GET /api/cabin/capabilities`：读取运行时工具、VSS 信号、声明式约束、集成与执行图。
- `POST /api/cabin/session`：创建 9 种场景会话，可附带定位、角色与匿名偏好授权。
- `POST /api/cabin/plan`：不调用模型，预演可信任务图。
- `POST /api/cabin/signal-event`：向数字孪生会话注入时序场景事件。
- `WS /ws/cabin/signals/{session_id}`：推送带版本号的车辆状态。
- `GET /api/cabin/evidence/{session_id}`：读取当前会话的因果证据账本。
- `GET /api/cabin/proactive/{session_id}`：读取不会自动执行的主动建议。
- `GET /api/cabin/memory/{session_id}` / `POST /api/cabin/memory/consent`：查看、授权或撤销 TTL 偏好。
- `POST /api/cabin/operations/cancel`：取消运行中任务。
- `POST /api/deepseek/agent`：执行多轮 Tool Calling 任务。
- `POST /api/deepseek/interpret`：为首页提供结构化意图解析。
- `GET /api/evaluation/cases`：读取 50 个版本化模型语义任务。
- `POST /api/evaluation/score`：用 Python 确定性评分器检查一条多轮轨迹。
- `GET /api/evaluation/composite-summary`：运行并汇总 24 个 v0.6 组合契约。
- `GET /api/evaluation/scenario-matrix-summary`：运行并汇总 200 个 v0.8 确定性场景矩阵合同。

该后端使用模拟车况和内存会话验证 Agent 策略；SQLite 只持久化演示证据，不代表账号或车辆身份系统。不可直接连接真实车控执行端。
