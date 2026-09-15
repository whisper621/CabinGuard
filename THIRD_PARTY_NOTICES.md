# 第三方组件与许可说明

CabinGuard 使用开源软件构建。各组件的商标、版权和许可归其权利人所有。

## OpenAI Realtime Agents

仓库中的可选 Realtime 语音实验链路包含来自 OpenAI `openai-realtime-agents` 示例的 MIT 许可代码及其修改版本，包括部分会话 UI、音频处理、事件记录和 Realtime 连接逻辑。

原始版权声明：

```text
Copyright (c) 2025 OpenAI
```

相关许可条款保留在根目录 [LICENSE](LICENSE) 中。

## cockpit-agent-sim

`backend/cabinguard/signals.py` 的分段 glob 匹配语义与声明式约束数据结构改编自 [yancent-dao/cockpit-agent-sim](https://github.com/yancent-dao/cockpit-agent-sim) 的 MIT 许可实现；CabinGuard 在 Python 中重新实现运行逻辑，并增加了本项目的 VSS 对齐信号、车窗/天窗/后备箱/空调约束及机器可读裁决。

原始版权声明：

```text
Copyright (c) 2026 yancent
```

原项目完整 MIT 条款保留在 [licenses/cockpit-agent-sim-MIT.txt](licenses/cockpit-agent-sim-MIT.txt)。System Lab 与 AgentLab 的 React 页面为 CabinGuard 独立实现，参考的是其“执行与展示分离、工具注册表、信号目录、权限分层”的公开产品思想，没有复制原页面源码。

## p1-cabin-agent 研究边界

[Eliclx/p1-cabin-agent](https://github.com/Eliclx/p1-cabin-agent) 的 README 将项目标为“私有项目”，仓库未提供公开开源许可证。因此 CabinGuard **没有复制或改编其代码**。本项目仅研究其公开展示的多意图编排、槽位延续、黑板与行程记忆思路，并以 CabinGuard 既有 FastAPI/DeepSeek 架构独立实现会话偏好、行程回执和执行图。

## npm 依赖

运行时与开发依赖分别在 `package.json` 和 `package-lock.json` 中锁定，包括 Next.js、React、TypeScript、Zod、Vitest、OpenAI Agents SDK、OpenAI Node SDK 与 Undici 等。每个依赖继续适用其自身许可证；发布或再分发前应按锁文件版本复核许可证清单。

## Python 依赖

Python Agent 后端的直接依赖声明在 `pyproject.toml`，包括 FastAPI、Pydantic、HTTPX、Uvicorn、python-dotenv 与 Pytest。安装时生成的间接依赖继续适用其各自许可证；部署或再分发时应按实际锁定版本复核许可证与安全公告。

## 地图与道路数据

Agent Lab 使用 Leaflet（BSD-2-Clause）渲染地图，并在用户触发导航或补能检索时访问 OpenStreetMap 生态的公共服务：Nominatim 用于地点检索，OSRM 用于道路算路，Overpass 用于充电设施 POI 查询，OpenStreetMap 标准瓦片用于地图展示。页面保留可见的 `© OpenStreetMap contributors` 归属信息。地图数据适用 [OpenStreetMap 版权与许可说明](https://www.openstreetmap.org/copyright)，公共服务还受各自使用政策、容量与可用性限制；本项目不批量抓取或打包离线地图，不将 POI 解释为实时枪位、价格或营业状态。

## 产品内容边界

CabinGuard 的智能座舱场景、产品策略、DeepSeek 多轮工具编排、服务端安全执行器、会话确认机制、可视化评测、确定性测试和配套产品文档属于本仓库的核心产品实现。第三方组件不代表对本项目的背书。
