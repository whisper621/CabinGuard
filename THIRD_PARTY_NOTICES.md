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

## 产品内容边界

CabinGuard 的智能座舱场景、产品策略、DeepSeek 多轮工具编排、服务端安全执行器、会话确认机制、可视化评测、确定性测试和配套产品文档属于本仓库的核心产品实现。第三方组件不代表对本项目的背书。
