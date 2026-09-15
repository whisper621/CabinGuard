# CabinGuard 可审查架构

## 产品概览

CabinGuard 是智能座舱可信任务 Agent MVP。它用模拟车辆状态验证“理解目标—可信任务编译—有边界工具选择—权限/安全校验—确定性执行—证据核验”的闭环；可接收用户明确授权的浏览器坐标，并接入 Nominatim、OSRM 与 OpenStreetMap/Overpass 公共数据，但不接入真实车辆或商业导航平台。

关键假设：

- TaskPlan 由确定性编译器生成；模型是可出错的边界内工具选择器，不能扩权或直接修改车辆状态。
- 服务端工具执行器是动作边界，负责参数、前置条件和风险规则。
- `/` 是唯一 Driver Mode，展示大地图、任务、主动建议、偏好与用户回执；详细工具参数、策略码和状态版本在 `/validation`。
- 所有状态和策略都属于演示级实现，不能直接用于量产车控。

## 技术栈与入口

| 层级 | 实现 | 入口 |
| --- | --- | --- |
| 智能座舱 | DeepSeek Chat Completions、浏览器语音/定位、真实道路地图、TaskPlan、任务生命周期、主动建议与授权偏好 | `/` |
| 验证中心 | 场景信号注入、SQLite 证据追溯、组合契约与模型可靠性评测 | `/validation`、`evaluation/cases.json`、`backend/cabinguard/reliability.py` |
| 项目说明 | 产品故事、真实边界与 Python 动态能力注册表 | `/project` |
| 核心语音 | Web Speech API 中文识别与播报 | `/` |
| Python Agent API | FastAPI、DeepSeek 多轮编排、OpenAPI | `backend/cabinguard/api.py` |
| 服务端会话 | Python 内存 Store、TTL、限流、幂等、状态冲突、取消与超时 | `backend/cabinguard/session.py` |
| 本地偏好 | 用户明确授权、90 天 TTL、查看/遗忘/撤销删除 | `backend/cabinguard/preference_store.py` |
| 外部补能 POI | OpenStreetMap Overpass 查询与 Demo Catalog 明确降级 | `backend/cabinguard/charging.py` |
| 可信工具边界 | Pydantic 参数校验、领域执行器 | `backend/cabinguard/tools.py` |
| 兼容回退 | Next.js Route Handlers、Zod | `src/app/api/`、`src/app/lib/` |

## 状态与信任边界

```text
浏览器（不可信输入）
  ├─ text/history/sessionId/idempotencyKey/expectedStateVersion ──> Python FastAPI
  ├─ 用户授权的浏览器坐标 ──> 新演示会话（标记为不可信来源）
  └─ 不提交车辆状态，不持有供应商长期密钥
                                  │
                                  ├─ 可信 TaskPlan 编译器
                                  ├─ DeepSeek（边界内工具选择）
                                  │     └─ tool_calls
                                  ▼
                         服务端领域执行器（硬边界）
                                  ├─ Pydantic 参数校验
                                  ├─ 读取前置条件
                                  ├─ 天气/车速/确认规则
                                  ├─ 导航授权与目的地校验
                                  └─ 更新服务端模拟会话
```

会话 ID 是演示状态定位符，不是用户身份凭证。项目实现了驾驶员、前排乘客、后排儿童、访客四类演示角色及 ABAC，但角色由浏览器请求创建，不能等同于可信账号、设备身份或车辆所有权。

## 已知风险与假设

| 风险/假设 | 代码证据 | 当前处理 |
| --- | --- | --- |
| 会话仅存在于单进程内存 | `backend/cabinguard/session.py` | 限制 300 个会话并设置 TTL；不宣称分布式可靠 |
| DeepSeek 输出可能不符合工具 Schema | `backend/cabinguard/tools.py` | 服务端再次用 Pydantic 校验，失败不改变状态 |
| 模型可能无依据宣称完成 | `backend/cabinguard/policy.py` | 返回前检查副作用是否有成功工具结果 |
| 整条请求重试可能重复副作用 | `session.py`、Agent Lab 和评测客户端 | 同一逻辑请求复用幂等键并回放结果；陈旧版本或并发任务不执行 |
| 早期 Realtime 代码未共用执行器 | `src/app/agentConfigs/cabinPilot.ts` | 不再暴露为产品入口，也不计入当前 Agent 数量 |
| 来源 IP 限流依赖部署平台转发头 | API route | 仅为演示成本保护，不作为身份认证 |
| 浏览器坐标不是车载可信位置 | `AgentLab.tsx`、`session.py` | 仅在用户点击授权后接收，记录来源与精度，不用于真实车控，也不写入模型工具上下文 |
| 公共补能 POI 不是实时充电平台 | `charging.py`、`tools.py` | 授权后优先 Overpass；不承诺枪位/价格/营业，失败时明确标注 Demo Catalog 降级 |
| 匿名偏好不是账号级记忆 | `preference_store.py`、`memory.py` | 默认只在会话；长期保存需单独授权、带 TTL，可撤销并删除 |
| 结构化感知事件不等于摄像头/VLM | `proactive.py`、`signal_player.py` | 只作为建议触发输入，永不自动车控，不宣称真实视觉接入 |

没有邮件、定时任务或后台作业，因此没有 `emails.md` 或 `cron.md`。项目目前没有公开部署和索引目标，因此不单列 `seo.md`。

## Related Documents

- [关键运行流程](flows.md)
- [权限与能力矩阵](permissions.md)
- [变量与密钥](variables.md)
- [测试覆盖地图](tests.md)
- [Agent 与自动化边界](automation.md)
- [求职作品集叙事](../docs/PORTFOLIO_PLAYBOOK.md)
- [当前状态（唯一指标口径）](../docs/CURRENT_STATUS.md)
- [产品与技术决策记录](../docs/DECISION_LOG.md)
