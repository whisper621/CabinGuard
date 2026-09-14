# CabinGuard 系统架构与执行边界

## 1. v0.6 主链路与兼容运行方式

v0.6 的主演示位于 `/mission`：FastAPI 先把用户目标编译为可信 TaskPlan，再让主 Agent 在白名单内规划；每次工具调用必须通过乘员 ABAC 与 VSS 约束，计划、策略和回执写入 SQLite 证据账本。`/twin-lab` 用 WebSocket 展示时序车辆状态，`/ops` 负责证据复盘。经典主页和 `/agent-lab` 继续保留；Next.js Route Handlers 仅是兼容回退，不包含 v0.6 全部能力。

```text
用户请求
  → FastAPI 会话（乘员角色 + stateVersion）
  → TaskPlan Compiler（节点 + 依赖 + 波次 + 风险 + allowedTools）
  → 主 Agent / Orchestrator
  → Policy Kernel（TaskPlan allowlist + ABAC）
  → Navigation Domain Agent / Cabin Safety / Memory / System Service
  → Pydantic + 25 个 VSS 信号 + 5 条声明式约束
  → Vehicle Sandbox / Nominatim / OSRM
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
- 偏好写入与删除必须由本轮用户明确提出，且只保留在 30 分钟会话；行程记录只接受成功导航回执。

## 3. 可观测性

每次请求写入 `plan.created`，每次调用写入 `policy.decision` 和 `tool.receipt`，数字孪生事件写入 `signal.injected`。Trace 关联 `planId`、`taskId`、领域、策略代码和执行前后 `stateVersion`；Ops 页面可按会话筛选并查看 SQLite 原始证据。

## 4. 数据边界

车辆、天气、车控动作与充电站目录为本地模拟；普通地点由 Nominatim 检索，道路路线由 OSRM 计算并用 OpenStreetMap 瓦片展示。公共地图服务无 SLA，也不提供实时路况、车道级指引或量产导航能力。当前实现不连接真实 CAN 总线或车控系统，不能用于真实驾驶控制。后续接入真实系统时，应增加地图商业 SLA、身份认证、权限分级、幂等键、超时补偿、审计日志和车端网关。

完整的权限、运行流程、变量、Agent 边界和测试覆盖地图见 `documentation/`；求职讲述边界见 `docs/PORTFOLIO_PLAYBOOK.md`。
