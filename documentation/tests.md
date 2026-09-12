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
| Python 多轮编排、API、Pydantic 工具、会话与安全策略 | Python Agent 主后端与 TypeScript 兼容语义一致 | 自动单元/API | `backend/tests/`（51 条） | existing / CI required |
| 10 类模型行为 | 有序关键工具链、状态、拦截、澄清、能力边界 | guarded live | `/evaluation` | existing / manual, costs API |

CI 依次运行 Ruff、51 条 Pytest、ESLint、TypeScript、35 条 Vitest 和生产构建；不要求任何供应商密钥。

## Proposed tests

| 用例 | 预期 | 类型 | 优先级 |
| --- | --- | --- | --- |
| API 两轮高速确认 | 首次创建待确认；明确确认执行；模糊回复不执行 | 自动集成 | P0 |
| 会话过期与一次性消费 | 超时或重复确认均不执行 | 自动集成 | P0 |
| 请求级重试 | 相同幂等键最多产生一次写副作用 | 自动集成 | P0（真实接入前） |
| Prompt injection 工具越权 | 模型指令不能绕过参数、导航和安全约束 | guarded live | P1 |
| 30–50 条同义表达 | 报告均值、方差、P95、成本和失败类型 | guarded live | P1 |
| Realtime 断连/重连 | 不重复执行动作；状态可恢复 | guarded live + manual | P1 |

## Gaps

| 未验证规则 | 暴露面 | 当前状态 |
| --- | --- | --- |
| 多实例/Serverless 下的会话一致性 | 会话丢失、确认状态漂移 | none；当前明确限制为单进程 Demo |
| 身份与真实车辆所有权 | 越权车控 | none；项目没有真实车控且禁止生产使用 |
| 持久化审计与幂等 | 重试后重复动作、无法追责 | none；真实接入前必须完成 |
| Realtime 与 DeepSeek 策略一致性 | 两条链路行为不同 | partial；当前只对 DeepSeek 可信链路设 CI 门禁 |
