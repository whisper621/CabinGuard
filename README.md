# CabinGuard

<div align="center">

### 可信智能座舱任务 Agent

让大模型负责理解与规划，让可信工具层负责状态读取、安全决策、动作执行与结果核验。

[![CI](https://github.com/whisper621/CabinGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/whisper621/CabinGuard/actions/workflows/ci.yml)
![Next.js](https://img.shields.io/badge/Next.js-16.3-000000?logo=nextdotjs)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Agent%20API-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-105%20passed-6E9F18)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

**[产品演示](#五分钟演示路径) · [Agent Lab](#五个产品入口) · [评测体系](#量化验证) · [案例页](#五个产品入口) · [项目文档](#项目文档)**

</div>

---

## 30 秒了解项目

CabinGuard 解决的不是“车载助手能否聊天”，而是“它能否在真实约束下把任务安全、可验证地做完”。

当用户说“把天窗开一半”时，系统不会立刻执行：它会先读取车速和天气；高速场景要求一次性明确确认，降雨场景由服务端直接阻止。只有工具返回真实成功结果后，Agent 才能向用户反馈“已完成”。

| 维度 | 项目成果 |
| --- | --- |
| 产品场景 | 空调舒适度、天窗、任意地点检索与真实道路导航、补能决策、后备箱、车辆状态 |
| Agent 能力 | 自然语言理解、多轮 Tool Calling、澄清、风险确认、失败回退 |
| 可信机制 | Python 服务端状态源、Pydantic 严格校验、动作前置、显式授权、结果依据校验 |
| 可观测性 | 工具名称、参数、输出、执行状态、模型轮次、Token 与延迟 |
| 评测资产 | 15 个三类可靠性任务、五维确定性评分、Pass^k / Pass@k、66 条 Python 测试、39 条 TypeScript 兼容测试 |
| 作品集资产 | 交互 MVP、Agent Lab、评测台、案例页、PRD、架构与决策记录 |

> 项目定位：单 Agent、多工具、服务端硬约束的智能座舱任务系统。当前使用车辆与环境模拟数据验证产品策略，不连接真实车辆控制器。

## 项目里到底有几个 Agent

当前可验证的主系统只有 **1 个任务 Agent**：Python `AgentService` 负责驱动 DeepSeek 多轮规划与工具调用。10 个领域工具、安全策略、会话状态机和 Reliability Lab 评分器都是 Agent 的支撑组件，不是 10 个 Agent。

仓库另有一个 `cabinPilotAgent` 的 OpenAI Realtime 实验配置，但它是独立语音路线，既不与主 Agent 协作，也尚未共用 Python 可信执行器，因此不应把项目包装成“2 Agent”或“多智能体”。这个取舍让项目重点落在任务完成、安全授权和可验证评测，而不是用名词制造复杂度。

## 语言与代码边界

CabinGuard 现在采用产品型 Agent 常见的前后端分工，而不是为了“全 Python”牺牲交互体验：

- **Python 是 Agent 主后端：** FastAPI 接口、多轮模型编排、Pydantic 工具 Schema、真实地点/道路服务适配、服务端会话、安全策略、可靠性评测器和 66 条测试均在 `backend/`。
- **TypeScript/TSX 是产品界面：** Next.js、React 页面、Agent Trace、评测台和浏览器语音交互在 `src/app/`。
- **TypeScript 后端是兼容回退：** 未启动 Python API 时，界面仍可通过 Next.js Route Handlers 演示；正式讲述应以 Python Agent 主链路为核心。

因此可以准确表述为“Python/FastAPI Agent 后端 + Next.js 产品前端”，不应表述为“整个仓库只有 Python”。

## 为什么做 CabinGuard

传统车载助手常见的失败并非“没听懂一句话”，而是执行链路不可信：

1. **模糊意图被擅自补全。** “调舒服一点”缺少温度、风量或通风偏好，直接执行容易违背用户预期。
2. **动作忽略实时上下文。** 开天窗、开后备箱、补能导航都依赖车速、天气、电量和路线状态。
3. **没有执行也报告成功。** 大模型可能生成自然流畅但没有工具结果支撑的完成文案。

CabinGuard 将任务拆为一条可检查的闭环：

```text
用户目标 → 意图理解 → 状态读取 → 必要澄清/确认
        → 安全校验 → 工具执行 → 状态更新 → 结果核验
```

## 核心产品设计

### 1. 模型是规划者，不是动作权限拥有者

模型可以决定“下一步应该调用什么工具”，但不能直接修改车辆状态。所有写操作统一进入 Python/FastAPI 服务端工具执行器，由应用层完成参数、前置状态、风险和授权校验；原有 Next.js API 保留为兼容回退链路。

### 2. 风险策略同时存在于软、硬两层

- 系统提示词负责引导模型先读状态、必要时澄清并解释风险。
- 服务端工具负责最终拦截，即使模型选错工具或伪造参数，也不能绕过规则。

### 3. 成功反馈必须有工具结果作证

只有工具返回 `executed=true` 或 `navigation_started=true` 等成功副作用时，Agent 才能声称任务完成；否则回复会被约束为澄清、阻止、失败或能力边界说明。

### 4. 稳定演示与开放探索分开

- 首页使用“LLM 增强理解 + 确定性执行”，即使模型不可用也能回退本地规则。
- Agent Lab 使用 DeepSeek 多轮 Tool Calling，用于观察模型如何自主选择工具和继续规划。
- 两条路径服务于不同验证目标，但共享相同的安全语义。

### 5. 语音、定位与真实导航是输入/环境能力，不是额外 Agent

- Agent Lab 使用浏览器 Web Speech API 完成中文语音转文字与回复播报；识别结果先进入输入框，由用户核对后发送。
- 当前位置必须由用户点击授权。服务端记录 WGS84 坐标、位置来源、精度与外部算路同意状态，默认仍提供可复现的京承高速模拟起点；精确坐标不写入发给模型的工具回执。
- 普通地址与 POI 由 OpenStreetMap Nominatim 按用户提交动作检索，道路距离、ETA、备选路线、步骤与 GeoJSON 折线由 OSRM 计算；页面用 Leaflet 和 OpenStreetMap 瓦片展示真实道路形状。
- 公共服务是无 SLA 的作品集原型数据源，不含实时交通、封路、车道级引导或量产导航能力；提供者失败时系统返回明确阻断，不以模拟折线冒充真实结果。

## 场景与安全策略

| 用户任务 | 系统先读取 | 正常动作 | 风险处理 |
| --- | --- | --- | --- |
| “把空调调到 23℃” | 当前温度、风量、循环模式 | 更新目标温度与送风 | 参数越界直接拒绝 |
| “把天窗开一半” | 车速、天气 | 更新天窗与遮阳帘 | 高速需确认；降雨禁止开启 |
| “找个顺路快充” | 电量、续航、当前路线 | 返回候选站 | 不得擅自启动导航 |
| “找快充并导航” | 车辆状态、候选站 | 搜索后启动导航 | 必须有明确导航意图 |
| “导航到昌平区政府” | 当前位置、实时地点候选 | 真实道路算路并展示地图 | 只接受本会话检索出的候选 ID；外部失败不伪造 |
| “打开后备箱” | 车速与挡位 | 驻车时开启 | 行驶中由工具层阻止 |
| “调舒服一点” | 当前座舱状态 | 等待偏好明确后执行 | 关键条件不足时先澄清 |

## 可信架构

```mermaid
flowchart LR
    U[用户文本 / 语音] --> UI[产品交互层]
    UI --> S[Python FastAPI 会话层]
    S --> LLM[DeepSeek 规划层]
    LLM -->|tool_calls| EX[Python 可信工具执行器]
    EX --> V[Pydantic 参数校验]
    V --> P[状态前置与授权检查]
    P --> G[安全规则]
    G --> SIM[车辆 / 天气模拟器]
    G --> MAP[Nominatim / OSRM 地图适配器]
    SIM -->|真实工具结果| EX
    EX -->|Trace + 状态| LLM
    LLM --> R[依据校验后的回复]
    R --> UI

    T[Pytest + Vitest + 行为评测] -.验证.-> EX
    T -.验证.-> R
```

### 信任边界

| 层级 | 可以做什么 | 不可以做什么 |
| --- | --- | --- |
| 浏览器 | 提交文本、会话 ID、有限历史；展示 Trace | 提交并覆盖可信车辆状态 |
| 大模型 | 理解意图、选择工具、组织回复 | 绕过 Schema、安全规则或直接写状态 |
| 工具执行器 | 校验参数、读取状态、执行模拟动作、记录结果 | 把失败包装成成功 |
| 模拟器 | 提供确定性车况、天气、补能和动作回执 | 代表真实车辆或量产能力 |
| 地图适配器 | 按授权检索地点并规划道路路线 | 提供实时路况、车道级引导或可用性 SLA |

详细设计见 [架构说明](docs/ARCHITECTURE.md) 与 [权限边界](documentation/permissions.md)。

## 十个领域工具

| 工具 | 职责 | 关键约束 |
| --- | --- | --- |
| `get_vehicle_state` | 读取车速、挡位、电量、续航、位置来源、路线状态 | 车辆动作与补能任务的可信前置 |
| `get_weather` | 读取天气与降雨概率 | 天窗开启前必须调用 |
| `get_climate_state` | 读取温度、风量与循环模式 | 空调写操作前必须调用 |
| `set_climate` | 调节温度、风量与循环模式 | 严格范围与枚举校验 |
| `search_charging_stations` | 搜索顺路充电站并返回候选坐标 | 必须先读取车辆状态；当前为演示目录 |
| `start_navigation` | 启动补能导航并生成距离、ETA、路线折线 | 需要显式导航意图和本轮候选站 |
| `search_places` | 实时检索普通地点、地址与行政区 | 用户触发、缓存限流；坐标留在服务端会话 |
| `plan_navigation` | 生成真实道路距离、ETA、步骤、备选路线与折线 | 先读车辆、先检索地点、候选 ID 绑定、外部算路同意 |
| `control_sunroof` | 控制天窗与遮阳帘 | 降雨阻止，高速确认绑定会话与动作 |
| `control_trunk` | 开关后备箱 | 行驶中禁止开启 |

## 五个产品入口

| 路径 | 用途 | 是否需要模型密钥 |
| --- | --- | --- |
| `/` | 稳定可复现的座舱任务 MVP，包含本地规则回退 | 否；DeepSeek 可选增强 |
| `/agent-lab` | 多轮 Tool Calling、中文语音输入/播报、授权定位、真实道路地图、能耗预测、工具轨迹与策略观察 | 是，`DEEPSEEK_API_KEY` |
| `/evaluation` | 按 Base / Hallucination / Disambiguation 运行多轮评测，展示五维得分与一致性 | 是，`DEEPSEEK_API_KEY` |
| `/case-study` | 面向招聘方的产品问题、取舍、证据与路线图 | 否 |
| `/realtime?agentConfig=cabinPilot` | 可选的实时语音实验入口 | 是，`OPENAI_API_KEY` |

## 量化验证

| 验证层 | 当前结果 | 说明 |
| --- | --- | --- |
| Python Agent 测试 | **66 / 66 通过** | 多轮编排、FastAPI、Pydantic 工具、真实地点/道路适配、定位同意、安全策略、评测 Schema、五维评分与一致性聚合 |
| TypeScript 兼容测试 | **39 / 39 通过** | 验证内置回退链路与 Python 可信语义保持一致 |
| 模型行为评测 | **15 个任务 / 3 类** | Base、Hallucination、Disambiguation 各 5 个，支持单次或 3 次重复运行 |
| 评测指标 | **5 维 + 3 个聚合指标** | 工具链、最终状态、策略、依据、歧义处理；试次通过率、Pass^k、Pass@k |
| v3 真实冒烟 | **D05 1 / 1 通过** | 两轮补槽后完成 23℃外循环；`deepseek-flash`，10.4 秒，8656 Token |
| 历史基线批次 | **9 / 10** | 旧版单次评测一次失败来自网络 TLS 瞬断；不冒充新版 15 任务结果 |
| 本地质量门禁 | **通过** | Ruff、Pytest、ESLint、TypeScript、Vitest、Next.js 生产构建 |
| 依赖安全检查 | **0 个已知漏洞** | `npm audit --omit=dev` |

为避免把模型随机性、网络波动和付费 API 变成每次提交的合并门槛，CI 默认只运行确定性质量门禁；真实模型回归由评测页触发并单独留档。完整记录见 [评测报告](docs/EVALUATION_REPORT.md)。

## 五分钟演示路径

1. **确定性任务：** 首页输入“把空调调到 23 度”，展示状态读取、参数化执行和工具轨迹。
2. **Human-in-the-loop：** Agent Lab 选择“高速”场景，输入“把天窗开一半”；首次被拦截，再输入“确认继续”完成一次性授权。
3. **同意图、不同结果：** 切换“降雨”场景重复天窗请求，展示服务端硬阻止。
4. **真实地点与导航：** 点击“授权定位并用于算路”，输入“导航到昌平区政府”，展示在线地点检索、真实道路折线、距离、ETA、步骤、备选路线与到达电量。
5. **自动评测：** 打开评测页，说明系统检查的是工具有序链、最终状态、澄清和禁止动作，而不只是回复文案。

更完整的求职讲述方式见 [作品集讲述手册](docs/PORTFOLIO_PLAYBOOK.md)。

## 快速开始

### Windows 一键演示（推荐）

首次完成下方依赖安装和 `.env.local` 配置后，可以直接在 PyCharm / VS Code 中运行根目录的 `start_demo.py`。也可以双击 `start-demo.cmd`，或在终端运行：

```powershell
npm run demo:start
```

在 Python IDE 中运行时，解释器选择 `.venv\Scripts\python.exe`，工作目录选择仓库根目录，然后直接运行 `start_demo.py`，不需要给它填写额外参数。

启动器会检查 Python/Node 环境，依次启动 FastAPI 与 Next.js，等待两个健康检查通过，并自动打开 Agent Lab；运行日志直接显示在 Python IDE 控制台，进程记录写入本地 `.runtime/` 且不会提交到 Git。按 `Ctrl+C` 或点击 IDE 的停止按钮即可关闭；也可以运行：

```powershell
npm run demo:stop
```

### 环境要求

- Python 3.11+
- Node.js 20+
- npm 10+
- 可选：DeepSeek API Key、OpenAI API Key

### 1. 安装 Python Agent

PowerShell：

```powershell
git clone https://github.com/whisper621/CabinGuard.git
cd CabinGuard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS / Linux 激活命令为 `source .venv/bin/activate`。

无需模型密钥即可验证 Python 工具闭环：

```bash
python -m cabinguard demo
```

### 2. 启动 FastAPI

```bash
python -m cabinguard
```

访问 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) 查看并直接调用 OpenAPI 接口。健康检查位于 `GET /api/health`。

### 3. 连接产品界面

复制环境变量文件并启用 Python API 地址：

```powershell
Copy-Item .env.sample .env.local
```

在 `.env.local` 中取消以下配置的注释：

```dotenv
NEXT_PUBLIC_CABINGUARD_API_URL=http://127.0.0.1:8000
```

另开终端启动界面：

```bash
npm ci
npm run dev
```

访问 [http://localhost:3000](http://localhost:3000)。Agent Lab、评测页和首页意图解析会直接调用 Python 后端；未配置该地址时自动使用仓库内置的 Next.js 兼容 API。

### 4. 启用 DeepSeek Tool Calling

在 `.env.local` 中填写：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_MODEL=deepseek-v4-flash
```

可以在终端直接运行 Agent：

```bash
python -m cabinguard chat --scenario default
```

也可以重启两个服务后访问 [http://localhost:3000/agent-lab](http://localhost:3000/agent-lab)。

### 5. 运行质量门禁

```bash
npm run check
```

该命令依次运行：

```text
ESLint → TypeScript → 39 条 Vitest → Ruff → 66 条 Pytest → Next.js 生产构建
```

常用单项命令：

```bash
npm run lint
npm run typecheck
npm run test:run
npm run python:lint
npm run python:test
npm run python:benchmark -- --task-type disambiguation --trials 1
npm run build
```

## 项目结构

```text
CabinGuard/
├─ backend/
│  ├─ cabinguard/
│  │  ├─ api.py                     # FastAPI 与 OpenAPI 入口
│  │  ├─ agent.py                   # DeepSeek 多轮 Tool Calling 主循环
│  │  ├─ tools.py                   # 10 个 Pydantic 工具与可信执行器
│  │  ├─ navigation.py              # 地点检索、道路算路、缓存限流与隐私边界
│  │  ├─ policy.py                  # 确认、导航授权与结果依据策略
│  │  ├─ session.py                 # 会话、TTL、限流与一次性确认
│  │  ├─ reliability.py             # 多轮运行、五维评分与 Pass 指标
│  │  └─ cli.py                     # serve / demo / chat / benchmark 入口
│  └─ tests/                        # 66 条 Python Agent、工具、地图、API 与评测测试
├─ evaluation/cases.json            # Python / TypeScript 共用的 15 个版本化任务
├─ pyproject.toml                   # Python 包、依赖和 cabinguard 命令
├─ src/app/
│  ├─ CabinDemo.tsx                 # 稳定产品演示与本地回退
│  ├─ agent-lab/                    # DeepSeek 多轮 Tool Calling 实验台
│  ├─ evaluation/                   # 三类任务、多轮轨迹、一致性与报告导出
│  ├─ case-study/                   # 招聘方快速阅读的产品案例页
│  ├─ realtime/                     # 可选实时语音入口
│  ├─ api/
│  │  ├─ cabin/session/             # 服务端模拟会话
│  │  ├─ deepseek/agent/            # Agent 编排、超时与结果返回
│  │  └─ deepseek/interpret/        # 结构化意图解析
│  └─ lib/
│     ├─ apiBase.ts                 # Python API / Next.js API 运行时切换
│     ├─ cabinTools.ts              # TypeScript 兼容工具执行器
│     ├─ cabinPolicy.ts             # 确认、授权与结果依据策略
│     ├─ cabinSession.ts            # 会话、待确认动作、TTL 与限流
│     └─ __tests__/                 # 39 条 TypeScript 兼容测试
├─ docs/                            # PRD、架构、评测、决策与作品集说明
├─ documentation/                   # 工程交付所需的流程、变量、权限和测试地图
└─ .github/workflows/ci.yml         # 自动质量门禁
```

## 项目文档

| 文档 | 解决的问题 |
| --- | --- |
| [文档导航](docs/README.md) | 按产品、技术、评测和求职场景快速定位材料 |
| [PRD](docs/PRD.md) | 用户问题、目标场景、成功指标与 MVP 边界 |
| [系统架构](docs/ARCHITECTURE.md) | 组件关系、信任边界、数据流与安全策略 |
| [评测方案](docs/EVALUATION.md) | 用例设计、断言方法与报告字段 |
| [评测报告](docs/EVALUATION_REPORT.md) | 基线结果、失败分析、修复与复测记录 |
| [Reliability Lab 升级决策](docs/RELIABILITY_LAB_UPGRADE.md) | 功能发散、优先级、实现范围与产品取舍 |
| [真实导航与座舱 UI 升级](docs/LIVE_NAVIGATION_UPGRADE.md) | 外部项目研究、15 个升级方向、优先级、隐私与服务边界 |
| [决策日志](docs/DECISION_LOG.md) | 为什么这样做、替代方案和验证标准 |
| [技术报告](docs/TECHNICAL_REPORT.md) | 实现原理、复核结果与生产化差距 |
| [作品集手册](docs/PORTFOLIO_PLAYBOOK.md) | 面向 AI、互联网、具身智能和座舱 PM 的讲述重点 |

## 关键产品取舍

- **可信性优先于全自动。** 高风险动作增加一次确认成本，换取更低的误执行风险。
- **可验证优先于炫技。** 工具 Trace、最终状态和失败原因比一段“聪明回复”更重要。
- **先验证策略，再接真实设备。** 当前模拟车况便于稳定复现；真实接入前必须补充身份、权限、签名、幂等和审计。
- **确定性 CI 与模型评测分层。** 代码规则每次提交都验证，非确定性模型行为以独立批次评测。

## 当前边界与路线图

当前版本是产品与技术 MVP，不是量产车控系统：

- 车辆、天气、车控和充电站目录仍为服务端模拟数据；普通地点与道路路线来自 OpenStreetMap/Nominatim/OSRM，但不含实时路况、车道级引导或正式 SLA。
- 会话使用单进程内存存储，不具备分布式持久化和正式身份认证。
- OpenAI Realtime 为可选实验入口，当前核心可验证链路是 DeepSeek Agent Lab。
- 15 个模型任务的真实运行需要有效密钥并产生调用成本，因此不在默认 CI 中运行；任务 Schema 与评分器仍由无密钥测试覆盖。

下一阶段优先级：

1. 接入 VSS / WebSocket 车辆模拟器，验证异步状态、延迟、冲突和动作回执。
2. 加入任务幂等键、用户身份、多乘员权限和持久化审计。
3. 将模型行为集扩展到 30–50 条同义、多轮、中断和恶意输入用例。
4. 建立 Prompt、模型、工具版本的成功率、P95 延迟和单任务成本趋势。
5. 通过真实目标用户访谈与可用性测试验证风险提示对信任和完成率的影响。

## 安全提示

- 不要把 API Key 写入代码或提交 `.env.local`；仓库只保留占位符 `.env.sample`。
- 不要将模拟工具连接到真实车辆执行端。
- 公网部署前必须增加鉴权、分布式限流、预算上限和持久化审计。

## License

项目采用 MIT License。第三方组件与相应许可信息见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
