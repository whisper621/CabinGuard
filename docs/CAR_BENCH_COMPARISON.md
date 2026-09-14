# CabinGuard 与 CAR-Bench 对比说明

> 调研快照：2026-09-12。该文档用于技术选型和面试边界说明；CabinGuard 不依赖、未复制 CAR-Bench 代码。

## 1. CAR-Bench 是什么

[CAR-Bench](https://github.com/CAR-bench/car-bench) 是一个面向车载语音助手领域的 Agent 可靠性评测基准。它重点检查多轮工具调用 Agent 在不确定、歧义和能力缺失条件下，是否知道何时执行、补充信息、澄清或拒绝。

它不是一款面向终端用户交付的智能座舱产品，核心交付物是合成环境、任务集、模拟用户、工具与策略、自动评分和 Pass^k/Pass@k 结果分析。

## 2. 它是不是 Python 项目

是。仓库要求 Python 3.11+，使用 `setup.py` 打包，以 `run.py`、`analyze_results.py` 和 `interactive_app.py` 作为运行入口，主要依赖包含 LiteLLM、Pydantic、Datasets、Pandas 和 NumPy。交互页面也由 Python Flask 启动。

按 GitHub Languages API 在调研日返回的代码字节统计：

| 语言 | 字节 | 占比 |
| --- | ---: | ---: |
| Python | 938,656 | 92.87% |
| HTML | 72,048 | 7.13% |

这说明 CAR-Bench 确实是 Python 主导的研究/评测工程，但不能推出“Agent 必须使用 Python”。语言选择取决于交付物：模型训练、数据分析与 benchmark 常以 Python 为主；浏览器产品、实时交互和全栈 SaaS 也经常使用 TypeScript。

## 3. 与 CabinGuard 的核心差异

| 维度 | CAR-Bench | CabinGuard |
| --- | --- | --- |
| 产品定位 | Agent 可靠性 benchmark | 可交互的可信智能座舱任务 Agent MVP |
| 主要用户 | 研究者、Agent 开发者、模型评测者 | 驾驶者；以及座舱产品、算法、安全和工程团队 |
| 核心产物 | 合成任务、模拟用户、58 个工具、19 类策略、自动评分 | Python Agent API、10 个领域工具、真实地点/道路适配器、服务端安全执行器、产品 UI、15 任务 Reliability Lab |
| 主要语言 | Python；少量 HTML | Python/FastAPI Agent 后端 + TypeScript/Next.js 产品前端 |
| 重点指标 | Pass^k、Pass@k、动作/策略/澄清/能力边界评分 | 五维评分、试次通过率、Pass^k、Pass@k、延迟、Token 与失败解释 |
| 展示价值 | 研究深度、评测规模和一致性分析 | 产品定义、交互取舍、可信执行、工程闭环和跨职能落地 |
| 真实车控 | 否，合成环境 | 否，服务端模拟状态 |

## 4. CabinGuard 的 Python 化决策

CabinGuard 没有把整个仓库机械重写成 Python。浏览器界面继续使用更适合 React 交互的 TypeScript/TSX；以下 Agent 核心已落到 Python：

- FastAPI 与 OpenAPI 接口；
- DeepSeek 多轮 Tool Calling 循环；
- 10 个 Pydantic 严格工具 Schema；
- 服务端模拟车辆状态、TTL 和来源限流；
- 高速天窗的一次性确认状态机；
- 导航显式授权、工具读取前置和执行结果依据校验；
- 15 个 Base / Hallucination / Disambiguation 任务的共享 JSON Schema；
- Python 多轮运行器、五维确定性评分器、Pass^k / Pass@k 聚合与版本化报告；
- 66 条 Python Agent、地图、工具、策略、会话、API 与评测测试。

这使项目可以准确表述为“Python Agent 后端 + Next.js 产品前端”，也能直接通过 `python -m cabinguard` 运行，而不需要伪装成全 Python 仓库。

## 5. 本轮吸收的方法与原创实现

CabinGuard 吸收了“按不确定性类型拆任务”和“重复运行观察一致性”这两类评测思想，但没有复制 CAR-Bench 的代码、任务数据、工具定义或评分实现。任务均围绕 CabinGuard 自己的 10 个座舱工具、安全状态机和产品场景重新定义，评分器也是面向本项目状态与 Trace 独立实现。

已完成：

1. 将原 10 类单次行为用例升级为 15 个 Base、Hallucination、Disambiguation 共享任务。
2. 支持同一任务 1/3 次运行，输出试次通过率、Pass^k 与 Pass@k。
3. 用同一会话运行高速确认和补槽等真实多轮轨迹。
4. 对工具链、最终状态、策略、结果依据和不确定性处理逐维解释失败。
5. 固化任务集、报告、模型、Prompt 与工具版本。

仍属于路线图、不能作为当前成果表述：

1. 加入独立模拟用户，实现开放式无人值守多轮评测。
2. 把任务扩展为足以计算置信区间的规模，并报告方差、P95 与成本。
3. 持久化多版本报告，形成模型、Prompt 和工具策略的纵向趋势。
4. 通过独立适配器接入公开 benchmark，避免评测框架耦合产品执行代码。
