# CabinGuard 系统架构与执行边界

## 1. v0.8 主链路与兼容运行方式

v0.8 的主演示统一位于 `/`：大地图作为工作画布，顶部只保留关键遥测，底部 Dock 收纳场景、温控、语音、媒体、车辆和路线入口；右侧 Driver Mode 只呈现统一对话、用户任务、偏好和历史。`/validation` 承载 WebSocket 时序场景、SQLite 证据复盘、策略与可靠性评测；`/project` 说明产品价值、真实边界与运行时能力注册表。旧地址只做兼容重定向。

```text
用户请求
  → FastAPI 请求生命周期（idempotencyKey + expectedStateVersion + timeout/cancel）
  → 会话（乘员角色 + stateVersion + memory consent）
  → TaskPlan Compiler（节点 + 依赖 + 波次 + 风险 + allowedTools）
  → 主 Agent / Orchestrator
  → Policy Kernel（TaskPlan allowlist + ABAC）
  → Navigation / Media Domain Boundary + Cabin Safety / Memory / Proactive Service
  → Pydantic + 41 个 VSS 信号 + 9 条声明式约束
  → Vehicle Sandbox / Nominatim / OSRM / Overpass / Media Catalog
  → SQLite Evidence Ledger + WebSocket Signal Stream + HMI
```

## 2. 信任边界

模型属于不可信规划层，可以选择工具和参数，但不能扩大 TaskPlan 的可执行范围，也不能直接修改车辆状态。服务端会话是演示状态边界，工具执行器从会话读取和写入模拟车辆状态，并负责乘员权限、参数范围、车速、天气和挡位校验；只有工具返回成功后，模型才能向用户声明执行完成。

当前强制规则：

- Python 主链路使用 Pydantic 严格校验所有 DeepSeek 工具参数；Next.js 兼容链路使用 Zod。类型、范围、枚举或多余字段错误时均不改变车辆状态。
- 空调目标温度限制为 16–30℃，风量限制为 1–5 档。
- 电量低于 10% 且请求 4–5 挡风量时，声明式规则将其降级到 3 挡并返回原因。
- 车速超过 100 km/h 且车窗请求超过 30% 时限幅；儿童锁开启时拒绝后排开窗。
- 空调写入、补能搜索、天窗和后备箱开启分别强制校验所需的状态读取前置。
- 降雨概率达到 50% 时阻止开启天窗。
- 车速达到 80 km/h 时，未获得明确且单义的确认不得开启天窗；取消优先，疑问句不构成授权。
- 后备箱使用显式挡位信号，非 P 挡时阻止开启。
- 启动导航必须有用户明确意图。补能目的地来自本轮充电站搜索；普通目的地必须来自本会话 `search_places` 候选 ID。
- 浏览器真实位置参与外部算路前必须记录用户同意；精确起点与道路折线不进入大模型工具回执。
- Nominatim/OSRM 失败时返回可识别阻断，不以模拟路线替代真实结果。
- 没有成功工具结果时，服务端阻止模型宣称副作用已经完成。
- 单个请求最多执行 6 个模型轮次，防止失控循环和费用异常。
- 高速天窗确认绑定到服务端会话，并在 2 分钟后失效；确认消息不再只依赖浏览器传入的对话文本。
- 每次 Agent 请求使用幂等键去重，期望状态版本不一致或已有任务执行时拒绝；单次最长 45 秒，并提供显式取消接口。网络重试复用同一幂等键。
- 偏好写入与删除必须由本轮用户明确提出；默认只保留在 30 分钟会话。开启长期偏好还需单独 UI 授权，匿名本地配置默认 90 天 TTL，可查看、遗忘或撤销并删除。
- 低电、雨天开窗、高 PM2.5 与结构化可视性事件只产生 `ProactiveSuggestion`；用户接受后重新进入同一可信执行链，不直接写车。

## 3. 可观测性

每次请求写入 `operation.started/completed/cancelled` 与 `plan.created`，每次调用写入 `policy.decision` 和 `tool.receipt`，场景仿真事件写入 `signal.injected`。Trace 关联 `planId`、`taskId`、领域、策略代码和执行前后 `stateVersion`；响应同时记录 `requestedModel` 与供应商返回的 `resolvedModel`。验证中心可按会话查看 SQLite 原始证据。

## 4. 数据边界

车辆、天气和车控动作为本地沙箱；普通地点由 Nominatim 检索，道路路线由 OSRM 计算，授权后的补能 POI 由 OpenStreetMap Overpass 查询。补能枪位、价格和营业状态不核验；服务失败时明确回退到 Demo Catalog。公共服务无 SLA，也不提供实时路况或车道级指引。当前不连接真实 CAN 或量产车控。本轮只增强软件原型的可信闭环，不实施 ROS2、KUKSA 或真实硬件接入。

当前数字与版本以 [`CURRENT_STATUS.md`](CURRENT_STATUS.md) 为准。完整的权限、运行流程、变量、Agent 边界和测试覆盖地图见 `documentation/`；求职讲述边界见 `PORTFOLIO_PLAYBOOK.md`。
