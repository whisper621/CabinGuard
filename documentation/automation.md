# Agent 与自动化边界

## 自动化清单

| 链路 | 触发/所有者 | 可读输入 | 可调用工具/API | 硬约束 | 输出 |
| --- | --- | --- | --- | --- | --- |
| 智能座舱主智能体 | 用户提交中文文字/语音 | Python 会话、有限历史、角色、文本、幂等键和状态版本 | 确定性 TaskPlan 编译器、有边界的主编排器、导航/媒体领域边界、23 个工具 | 计划白名单、四类乘员 ABAC、Pydantic、读取前置、VSS 约束、候选绑定、45 秒超时、取消、6 轮上限 | Driver Mode 消息/地图/任务/偏好；Validation Mode 策略、工具回执、版本与延迟 |
| 场景仿真 | 用户点击事件 | 当前会话与服务端车辆状态 | 信号事件 API、WebSocket | 事件枚举、会话隔离、状态版本递增 | 时序车辆信号与证据事件 |
| 执行追溯 | 用户打开/刷新 | 当前演示会话 ID | SQLite 证据读取 API | 只读；会话 ID 不作为生产身份 | TaskPlan、策略裁决、工具回执、状态版本 |
| 主动建议 | 车辆信号或结构化感知事件变化 | 电量、续航、天气、车窗、PM2.5、可视性事件 | 只生成建议文本与可执行 prompt | 永不自动写车；用户接受后重新经过 TaskPlan、ABAC 与策略核 | 可忽略的建议卡与来源 |
| 可靠性评测 | 页面或 Python CLI | 50 个共享语义任务，可按三类筛选并重复 1/3 次 | 会话 API、Agent API、Python 评分 API | 每试次独立会话、超过 30 个付费试次需显式解锁 | 五维得分、P95、Pass^k、Pass@k、请求/解析模型、版本化 JSON |

## Steering 与硬规则

- Steering：DeepSeek system prompt 和 Realtime instructions 决定模型应如何规划、何时澄清以及回复风格。
- Hard guardrails：Python 的 `backend/cabinguard/tools.py` 是主执行边界，决定参数是否合法、前置读取是否完成、风险动作是否允许、导航是否获授权；`cabinTools.ts` 保留相同语义作为兼容回退。
- 模型不能直接访问会话 Map，也不能提交一份伪造车辆状态替换服务端状态。
- 模型输出不是执行事实；只有工具 Trace 中的成功字段可以证明副作用。

## 输出、失败与控制

- Agent API 返回 `message/sessionId/vehicle/traces/model/turns/totalTokens/operation/requestedModel/resolvedModel`。
- 请求和工具参数失败时返回结构化错误或 blocked Trace；失败不得修改车辆状态。
- 模型最多 6 轮；单次供应商调用最多 3 次有限重试；客户端仅对 502 重试整条请求一次。
- 演示限流为每个来源窗口 30 次/5 分钟；服务重启可立即终止全部会话，是当前 Demo 的 kill switch。
- 客户端重试复用同一幂等键；状态冲突、超时和取消都返回可审计生命周期状态。
