# 变量与密钥

| 名称 | 使用位置 | 范围 | 来源/轮换 | 风险 |
| --- | --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 两个 DeepSeek API route | 仅服务端 | 本地 `.env.local` 或部署平台 Secret；泄露时立即在供应商控制台轮换 | API 成本、配额滥用 |
| `DEEPSEEK_MODEL` | DeepSeek API route | 仅服务端 | 可选配置；变更需重新运行评测 | 行为和成本漂移 |
| `OPENAI_API_KEY` | `/api/session` | 仅服务端 | 本地/部署平台 Secret；泄露立即轮换 | Realtime API 成本与权限 |
| `ENABLE_REALTIME_OUTPUT_GUARDRAIL` | `/api/responses` | 仅服务端 | 默认关闭；仅在验证 Realtime 输出审核时设为 `true` | 会增加模型调用成本与延迟 |
| `HTTPS_PROXY` | 服务端供应商请求 | 仅服务端 | 本机或部署环境 | 代理可观察流量元数据，配置错误导致 502 |
| `HTTP_PROXY` | 服务端供应商请求 | 仅服务端 | 同上 | 同上 |

长期密钥没有使用 `NEXT_PUBLIC_` 前缀，也没有被返回给浏览器。OpenAI Realtime 只向浏览器返回短期 client secret。

## 上线前检查

- `.env.local` 保持被 Git 忽略，只提交 `.env.sample` 占位符。
- 对历史提交运行 secret scan；发现泄露时先轮换、后清理历史。
- 为 DeepSeek/OpenAI 设置预算告警和最小权限。
- 公开部署前为消耗型 API 增加认证、持久化配额和可信来源限流。
- 环境变量或模型版本变化后重新执行行为评测并保存报告。
