# CabinGuard 当前状态（唯一指标口径）

> 更新时间：2026-09-15；当前版本：v0.8.0。仓库中的数量、版本和完成度描述如与本文冲突，以同目录的 `CURRENT_STATUS.json` 及运行时接口为准。历史升级报告只描述当时快照。

## 当前可验证事实

| 维度 | 当前值 | 事实来源 |
| --- | ---: | --- |
| 用户可见助手 | 1 | 主页面统一入口 |
| Agent 边界 | 3 | 1 个主编排边界 + 导航、媒体 2 个领域边界 |
| 确定性服务 | 5 | 舒适、车身安全、记忆、感知、策略/执行服务 |
| 业务领域 | 6 | Python 运行时能力注册表 |
| 注册工具 | 23 | `GET /api/cabin/capabilities` |
| VSS 对齐信号 | 41 | `GET /api/cabin/capabilities` |
| 声明式约束 | 9 | `GET /api/cabin/capabilities` |
| 确定性场景合同 | 200 | 25 个核心合同 × 8 种口语表面形式；不调用 LLM |
| 基础组合合同 | 24 | 确定性评分，不调用 LLM |
| 真实模型语义任务 | 50 | 20 Base + 15 Hallucination + 15 Disambiguation；默认不进 CI |
| 真实模型首轮基线 | 113 / 150 | 2026-09-15；试次通过率 75.3%，Pass@3 86%，Pass^3 62%；包含 7 次供应商连接失败 |
| 修复后定向闭环 | 12 / 12 | 最后 4 个系统性问题任务各运行 3 次；不是修复后全量 50×3 结果 |
| 自动测试 | 385 | 342 Python + 43 TypeScript；以本次 `npm run check` 输出为准 |

## 架构表述

准确说法是：**可信 TaskPlan 编译器 + 有边界的大模型工具选择 + 确定性策略与执行层**。TaskPlan 由服务端确定性编译器生成；大模型不拥有最终车控权限，也不能修改工具白名单、ABAC 或车辆约束。

## 真实与沙箱边界

- 真实联网：浏览器定位（用户授权）、OpenStreetMap 地点/补能 POI、OSRM 道路路线、公共音乐试听和可选 DeepSeek 调用。
- 沙箱执行：空调、车窗、座椅、车门、雨刷、后备箱等车辆动作只写入数字车辆状态，未连接 CAN、ECU 或量产车。
- 补能数据：授权后优先使用 OpenStreetMap Overpass POI；空闲枪位、价格和营业状态不作实时承诺；失败时明确回退到 Demo Catalog。
- 感知数据：当前只支持结构化 `PerceptionEventAdapter` 演示事件，不代表已接入摄像头或 VLM。
- 偏好记忆：默认仅 30 分钟会话；明确授权后保存到匿名本地 SQLite 配置档，默认 TTL 90 天，可查看、遗忘或撤销并删除。

## 模型版本口径

当前聊天接口请求模型名为 `deepseek-v4-flash`。每次 Agent 响应分开记录 `requestedModel`、供应商实际返回的 `resolvedModel` 与内部 `executionSource`；纯槽位守卫或服务端确认没有调用模型，`resolvedModel` 为 `null`。2026-09-15 真实评测中供应商返回 `deepseek-flash`。

## 复核命令

```bash
python -m cabinguard capabilities
python -m cabinguard benchmark --list
npm run check
```

真实模型完整回归不是默认 CI：

```bash
python -m cabinguard benchmark --task-type all --trials 3 --allow-large-run
```

执行前必须配置有效 API Key，并接受 150 个真实模型试次的时间与成本。
