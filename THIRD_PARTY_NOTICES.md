# 第三方组件与许可说明

CabinGuard 使用开源软件构建。各组件的商标、版权和许可归其权利人所有。

## OpenAI Realtime Agents

仓库中的可选 Realtime 语音实验链路包含来自 OpenAI `openai-realtime-agents` 示例的 MIT 许可代码及其修改版本，包括部分会话 UI、音频处理、事件记录和 Realtime 连接逻辑。

原始版权声明：

```text
Copyright (c) 2025 OpenAI
```

相关许可条款保留在根目录 [LICENSE](LICENSE) 中。

## npm 依赖

运行时与开发依赖分别在 `package.json` 和 `package-lock.json` 中锁定，包括 Next.js、React、TypeScript、Zod、Vitest、OpenAI Agents SDK、OpenAI Node SDK 与 Undici 等。每个依赖继续适用其自身许可证；发布或再分发前应按锁文件版本复核许可证清单。

## Python 依赖

Python Agent 后端的直接依赖声明在 `pyproject.toml`，包括 FastAPI、Pydantic、HTTPX、Uvicorn、python-dotenv 与 Pytest。安装时生成的间接依赖继续适用其各自许可证；部署或再分发时应按实际锁定版本复核许可证与安全公告。

## 地图与道路数据

Agent Lab 使用 Leaflet（BSD-2-Clause）渲染地图，并在用户触发导航时访问 OpenStreetMap 生态的公共服务：Nominatim 用于地点检索，OSRM 用于道路算路，OpenStreetMap 标准瓦片用于地图展示。页面保留可见的 `© OpenStreetMap contributors` 归属信息。地图数据适用 [OpenStreetMap 版权与许可说明](https://www.openstreetmap.org/copyright)，公共服务还受各自使用政策、容量与可用性限制；本项目不批量抓取或打包离线地图。

## 产品内容边界

CabinGuard 的智能座舱场景、产品策略、DeepSeek 多轮工具编排、服务端安全执行器、会话确认机制、可视化评测、确定性测试和配套产品文档属于本仓库的核心产品实现。第三方组件不代表对本项目的背书。
