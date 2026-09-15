# 变量与密钥

| 名称 | 使用位置 | 范围 | 来源/轮换 | 风险 |
| --- | --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | Python Agent/解析 API 与 Next.js 兼容 route | 仅服务端 | 本地 `.env.local` 或部署平台 Secret；泄露时立即在供应商控制台轮换 | API 成本、配额滥用 |
| `DEEPSEEK_MODEL` | Python Agent/解析 API 与 Next.js 兼容 route | 仅服务端 | 可选配置；变更需重新运行评测 | 行为和成本漂移 |
| `NEXT_PUBLIC_CABINGUARD_API_URL` | Next.js 产品界面 | 浏览器可见 | 本地指向 `http://127.0.0.1:8000`，部署时指向 Python API 域名 | 配置错误会回落或请求失败 |
| `CABINGUARD_CORS_ORIGINS` | Python FastAPI | 仅服务端 | 逗号分隔的前端 Origin 白名单 | 过宽会扩大跨站调用面 |
| `CABINGUARD_GEOCODER_URL` | Python 地点检索适配器 | 仅服务端 | 可选；默认 Nominatim 公共实例 | 公共服务无 SLA，供应商变更会影响候选结果 |
| `CABINGUARD_ROUTER_URL` | Python 道路算路适配器 | 仅服务端 | 可选；默认 OSRM 公共实例 | 外部服务可观察算路坐标，生产需商业协议 |
| `CABINGUARD_NAV_COUNTRY_CODES` | Python 地点检索适配器 | 仅服务端 | 默认 `cn`，空值表示不按国家限制 | 范围过大可能增加同名歧义 |
| `CABINGUARD_MAP_USER_AGENT` | Nominatim/OSRM 请求 | 仅服务端 | 标识应用和联系地址，需遵循供应商政策 | 无效标识可能导致公共服务拒绝 |
| `CABINGUARD_PREFERENCE_DB` | 用户明确授权的本地偏好 | 仅服务端 | 可选；默认 `.runtime/cabinguard-preferences.sqlite3` | 文件需限制访问、备份和删除；当前不是账号级存储 |
| `CABINGUARD_MEDIA_URL` | Python 音乐目录适配器 | 仅服务端 | 可选；默认 Apple iTunes Search API | 公共目录无 SLA，供应商变更会影响试听结果 |
| `CABINGUARD_MEDIA_FALLBACK_URL` | Python 音乐目录降级适配器 | 仅服务端 | 可选；默认 Deezer API | 同上 |
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
