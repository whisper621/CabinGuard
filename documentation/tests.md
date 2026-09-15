# 测试覆盖地图

## Existing coverage

| 用例 | 规则与拒绝路径 | 类型 | 证据 | 状态/门禁 |
| --- | --- | --- | --- | --- |
| 明确确认、否定优先、疑问不授权 | 高速动作只能由单义回复确认 | 自动单元 | `cabinPolicy.test.ts` | existing / CI required |
| 无工具依据的成功表述 | 没有 `executed`/`navigation_started` 不得声称完成 | 自动单元 | `cabinPolicy.test.ts` | existing / CI required |
| 非法模型工具参数 | 类型、范围或枚举错误时不改变状态 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 空调读取前置 | 未读当前空调状态时拒绝写入 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 天窗读取前置、降雨、高速确认 | 所有失败路径均不得打开天窗 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 行驶中后备箱 | 车速大于 0 时拒绝开启 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 补能绕行筛选 | 最大绕行参数影响候选结果 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 导航授权和候选绑定 | 未明确要求或目的地非本轮候选时拒绝 | 自动单元 | `cabinTools.test.ts` | existing / CI required |
| 会话场景、确认 TTL、一次性消费和限流 | 过期/重复确认不得执行，第 31 次窗口请求被拒绝 | 自动单元 | `cabinSession.test.ts` | existing / CI required |
| Python 多轮编排、TaskPlan、ABAC、证据账本、WebSocket、API、工具、VSS 约束、记忆、安全策略与评分器 | Python Agent 主后端与 TypeScript 兼容语义一致 | 自动单元/API | `backend/tests/`（342 条） | existing / CI required |
| 地点/道路提供者协议 | 候选坐标隔离、外部算路同意、服务失败不生成假路线 | 自动单元 | `backend/tests/test_navigation.py` | existing / CI required |
| 幂等、状态冲突、超时与取消 | 重试不重复调用；陈旧状态不执行；超时/取消留下生命周期状态 | 自动单元/API | `test_operation_lifecycle.py`、`test_api.py` | existing / CI required |
| 授权偏好、主动建议、补能 POI 降级 | 授权/撤销/TTL、建议不自动执行、公开数据与沙箱来源可区分 | 自动单元/API | `test_preference_store.py`、`test_proactive.py`、`test_charging.py` | existing / CI required |
| 50 个三类模型任务 | 有序工具链、最终状态、策略、依据、歧义/能力边界、跨试次一致性 | guarded live | `/validation?tab=evaluation` 或 `python -m cabinguard benchmark` | existing / manual, costs API |

CI 依次运行 ESLint、TypeScript、43 条 Vitest、Ruff、342 条 Pytest 和生产构建；共 385 条自动化测试，不要求任何供应商密钥。

## Proposed tests

| 用例 | 预期 | 类型 | 优先级 |
| --- | --- | --- | --- |
| API 两轮高速确认 | 首次创建待确认；明确确认执行；模糊回复不执行 | 自动集成 | P0 |
| 会话过期与一次性消费 | 超时或重复确认均不执行 | 自动集成 | P0 |
| Prompt injection 工具越权 | 模型指令不能绕过参数、导航和安全约束 | guarded live | P1 |
| 修复后全量 50 条语义任务 × 3 次复跑 | 对比 2026-09-15 首轮 75.3% 基线，报告 Pass^3、Pass@3、P95、Token 和失败类型 | guarded live | P1（首轮已运行；定向问题集已闭环） |
| Realtime 断连/重连 | 不重复执行动作；状态可恢复 | guarded live + manual | P1 |

## Gaps

| 未验证规则 | 暴露面 | 当前状态 |
| --- | --- | --- |
| 多实例/Serverless 下的会话一致性 | 会话丢失、确认状态漂移 | none；当前明确限制为单进程 Demo |
| 身份与真实车辆所有权 | 越权车控 | none；项目没有真实车控且禁止生产使用 |
| 跨服务事务补偿 | 外部工具已完成但后续任务失败 | partial；请求级取消/超时已实现，不承诺跨供应商回滚 |
| 完整模型回归自动化 | 模型升级后行为漂移 | guarded live；50 个任务需主动运行并产生 API 成本，不进入默认 CI |
