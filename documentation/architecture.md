# CabinGuard 可审查架构

## 产品概览

CabinGuard 是智能座舱可信任务 Agent MVP。它用模拟车辆和充电数据验证“理解目标—读取上下文—安全校验—执行工具—核验结果”的闭环，不接入真实车辆、地图或充电平台。

关键假设：

- 模型是可出错的规划者，不能直接修改车辆状态。
- 服务端工具执行器是动作边界，负责参数、前置条件和风险规则。
- 本地稳定演示用于可复现展示；DeepSeek Agent Lab 用于观察开放式 Tool Calling。
- 所有状态和策略都属于演示级实现，不能直接用于量产车控。

## 技术栈与入口

| 层级 | 实现 | 入口 |
| --- | --- | --- |
| 产品 UI | Next.js、React、TypeScript、Tailwind | `/` |
| Tool Calling 实验台 | DeepSeek Chat Completions | `/agent-lab` |
| 模型回归评测 | 浏览器驱动真实 Agent API | `/evaluation` |
| 可选语音 | OpenAI Realtime Agents | `/realtime` |
| Python Agent API | FastAPI、DeepSeek 多轮编排、OpenAPI | `backend/cabinguard/api.py` |
| 服务端会话 | Python 内存 Store、TTL、限流 | `backend/cabinguard/session.py` |
| 可信工具边界 | Pydantic 参数校验、领域执行器 | `backend/cabinguard/tools.py` |
| 兼容回退 | Next.js Route Handlers、Zod | `src/app/api/`、`src/app/lib/` |

## 状态与信任边界

```text
浏览器（不可信输入）
  ├─ text/history/sessionId ──> Python FastAPI
  └─ 不提交车辆状态，不持有供应商长期密钥
                                  │
                                  ├─ DeepSeek（不可信规划）
                                  │     └─ tool_calls
                                  ▼
                         服务端领域执行器（硬边界）
                                  ├─ Pydantic 参数校验
                                  ├─ 读取前置条件
                                  ├─ 天气/车速/确认规则
                                  ├─ 导航授权与目的地校验
                                  └─ 更新服务端模拟会话
```

会话 ID 是演示状态定位符，不是用户身份凭证。项目目前没有账号、组织、租户或角色系统。

## 已知风险与假设

| 风险/假设 | 代码证据 | 当前处理 |
| --- | --- | --- |
| 会话仅存在于单进程内存 | `backend/cabinguard/session.py` | 限制 300 个会话并设置 TTL；不宣称分布式可靠 |
| DeepSeek 输出可能不符合工具 Schema | `backend/cabinguard/tools.py` | 服务端再次用 Pydantic 校验，失败不改变状态 |
| 模型可能无依据宣称完成 | `backend/cabinguard/policy.py` | 返回前检查副作用是否有成功工具结果 |
| 整条请求重试可能重复副作用 | Agent Lab 和评测客户端 | 当前动作多为绝对赋值；真实接入前必须增加幂等键 |
| Realtime 与 DeepSeek 尚未共用执行器 | `src/app/agentConfigs/cabinPilot.ts` | 明确标记为后续统一项，不把 Realtime 当生产安全链路 |
| 来源 IP 限流依赖部署平台转发头 | API route | 仅为演示成本保护，不作为身份认证 |

没有邮件、定时任务或后台作业，因此没有 `emails.md` 或 `cron.md`。项目目前没有公开部署和索引目标，因此不单列 `seo.md`。

## Related Documents

- [关键运行流程](flows.md)
- [权限与能力矩阵](permissions.md)
- [变量与密钥](variables.md)
- [测试覆盖地图](tests.md)
- [Agent 与自动化边界](automation.md)
- [求职作品集叙事](../docs/PORTFOLIO_PLAYBOOK.md)
- [产品与技术决策记录](../docs/DECISION_LOG.md)
