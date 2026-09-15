# CabinGuard 文档导航

仓库文档按“先看产品、再看系统、最后看证据”的顺序组织。首次了解项目建议依次阅读 README、产品案例页、PRD、架构说明和评测报告。

## 产品定义

| 文档 | 内容 | 适合读者 |
| --- | --- | --- |
| [当前状态](CURRENT_STATUS.md) | 版本、架构、工具、评测和测试数字的唯一事实源 | 所有人 |
| [PRD](PRD.md) | 用户问题、目标场景、产品目标、成功指标与 MVP 边界 | 产品经理、设计、研发 |
| [决策日志](DECISION_LOG.md) | 核心取舍、替代方案、风险与验证标准 | 面试官、产品负责人 |
| [作品集讲述手册](PORTFOLIO_PLAYBOOK.md) | 四类产品岗位的讲述重点、演示脚本与高频追问 | 招聘方、项目作者 |
| [用户研究执行方案](USER_RESEARCH_PROTOCOL.md) | 8–12 位目标用户的招募、场景任务、指标、同意与记录模板 | 产品、用户研究、设计 |

## 系统实现

| 文档 | 内容 | 适合读者 |
| --- | --- | --- |
| [系统架构](ARCHITECTURE.md) | 组件、数据流、信任边界、异常处理与生产化方向 | 研发、AI 产品经理 |
| [技术报告](TECHNICAL_REPORT.md) | 三条运行链路、工具系统、复核证据和技术边界 | 技术面试官、研发 |
| [工程交付地图](../documentation/architecture.md) | 代码入口、流程、权限、变量、自动化和测试覆盖 | 接手项目的研发 |
| [CAR-Bench 对比](CAR_BENCH_COMPARISON.md) | Python 技术栈、项目定位差异与可借鉴的评测方向 | AI 产品、技术面试官 |
| [Reliability Lab 升级决策](RELIABILITY_LAB_UPGRADE.md) | 三角色功能发散、Top 5 优先级、实现范围与非目标 | 产品、研发、评测 |
| [真实导航与驾驶舱升级](LIVE_NAVIGATION_UPGRADE.md) | 公开项目研究、15 个升级方向、真实地图实现与能力边界 | 产品、座舱、研发 |
| [参考架构升级记录](REFERENCE_ARCHITECTURE_UPGRADE.md) | 参考仓库许可核查、意图/实现差距、三视角创意与 v0.5 落点 | 产品、座舱、研发、面试官 |
| [混合多 Agent 演进决策](MULTI_AGENT_EVOLUTION_PLAN.md) | 单 Agent 是否足够、拆分阈值、15 个候选方向、Top 5 和四周路线 | AI 产品、座舱、具身、面试官 |
| [v0.6 可信出行协同升级方案](V06_TRUSTED_CABIN_COPILOT_PLAN.md) | 产品战略、可信任务图、VSS 数字孪生、分域委托、中文 HMI、结果路线图与 DoD | AI 产品、座舱、具身、研发、面试官 |
| [v0.6 实施与评测报告](V06_IMPLEMENTATION_REPORT.md) | 已落地代码、组合评测、意图/实现差距、产品边界和面试讲法 | AI 产品、座舱、具身、研发、面试官 |
| [v0.7 场景与 HMI 升级报告](V07_SCENARIO_HMI_UPGRADE.md) | 8 组可执行场景、地图优先布局、媒体/车身能力、安全设计与真实边界 | AI 产品、座舱、具身、研发、面试官 |

## 评测与证据

| 文档 | 内容 | 适合读者 |
| --- | --- | --- |
| [评测方案](EVALUATION.md) | 200 条确定性合同、24 条组合合同、50 个模型语义任务与五维评分 | AI 产品、测试、研发 |
| [评测报告](EVALUATION_REPORT.md) | 基线、失败归因、修复、复测和后续计划 | 面试官、项目评审 |

## 阅读路径

### 招聘方：3 分钟

1. 根目录 [README](../README.md) 的“30 秒了解项目”。
2. `/project` 产品说明页。
3. [评测报告](EVALUATION_REPORT.md) 的结果与当前结论。

### AI / 智能座舱产品经理：10 分钟

1. [PRD](PRD.md) 的问题和场景。
2. [决策日志](DECISION_LOG.md) 的关键取舍。
3. [系统架构](ARCHITECTURE.md) 的信任边界与安全策略。
4. [参考架构升级记录](REFERENCE_ARCHITECTURE_UPGRADE.md) 的取舍与证据。
5. [评测方案](EVALUATION.md) 的成功与越权断言。

### 研发接手：20 分钟

1. [技术报告](TECHNICAL_REPORT.md) 的运行链路。
2. [工程交付地图](../documentation/architecture.md)。
3. Python 主后端：`backend/cabinguard/agent.py`、`tools.py`、`signals.py`、`memory.py`、`capabilities.py`。
4. TypeScript 产品层：`src/app/`；兼容后端：`src/app/lib/` 与 `src/app/api/`。
5. `python -m pytest` 与 `npm run check` 验证本地环境。

## 文档维护规则

- 已完成结果和后续计划分开描述，不把模拟数据写成真实车辆数据。
- 所有当前数量和版本必须引用 [CURRENT_STATUS](CURRENT_STATUS.md)；版本报告中的旧数字必须标记为历史快照。
- 修改工具 Schema、安全阈值或成功条件时，同步更新 PRD、架构、评测用例和测试。
- 模型行为结果必须记录模型版本、Prompt/工具版本、运行日期、延迟和失败原因。
- 第三方组件与许可统一维护在根目录 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
