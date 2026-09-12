# Agent 与自动化边界

## 自动化清单

| 链路 | 触发/所有者 | 可读输入 | 可调用工具/API | 硬约束 | 输出 |
| --- | --- | --- | --- | --- | --- |
| 首页稳定演示 | 用户点击/提交 | 浏览器模拟状态、文本 | DeepSeek 解析 API、本地模拟工具 | 本地确认和天气/车速规则 | 消息、状态、工具轨迹 |
| DeepSeek Agent Lab | 用户提交 | 服务端会话、有限历史、文本 | 8 个 Cabin 工具 | Zod、读取前置、风险规则、导航授权、6 轮上限 | 消息、状态、Trace、Token/延迟 |
| 回归评测 | 用户点击运行 | 10 个固定用例 | 会话 API、Agent API | 每例独立会话、有限重试 | 通过率和可下载 JSON |
| OpenAI Realtime | 用户建立语音连接 | 浏览器音频/文本、客户端模拟状态 | 8 个 Realtime 工具 | 独立客户端工具规则 | 实时音频、Transcript、事件 |

## Steering 与硬规则

- Steering：DeepSeek system prompt 和 Realtime instructions 决定模型应如何规划、何时澄清以及回复风格。
- Hard guardrails：`cabinTools.ts` 决定参数是否合法、前置读取是否完成、风险动作是否允许、导航是否获授权。
- 模型不能直接访问会话 Map，也不能提交一份伪造车辆状态替换服务端状态。
- 模型输出不是执行事实；只有工具 Trace 中的成功字段可以证明副作用。

## 输出、失败与控制

- Agent API 返回 `message/sessionId/vehicle/traces/model/turns/totalTokens`。
- 请求和工具参数失败时返回结构化错误或 blocked Trace；失败不得修改车辆状态。
- 模型最多 6 轮；单次供应商调用最多 3 次有限重试；客户端仅对 502 重试整条请求一次。
- 演示限流为每个来源窗口 30 次/5 分钟；服务重启可立即终止全部会话，是当前 Demo 的 kill switch。
- 真实副作用接入前，必须用幂等键替换“直接重试写操作”的做法。

