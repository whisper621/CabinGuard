# Reliability Lab 任务资产

`cases.json` 是 Python 评测器与 TypeScript 页面共用的唯一任务源，当前版本为 `4.0.0`，包含 20 个 Base、15 个 Hallucination 和 15 个 Disambiguation 任务。

每个任务声明场景、连续输入、期望/禁止工具、澄清或能力边界要求和最终状态断言。请不要在这里加入真实用户隐私、模型密钥或未授权的第三方数据。

```powershell
python -m cabinguard benchmark --list
python -m cabinguard benchmark --case D05 --trials 1
```

生成的模型报告默认放在 `evaluation/results/`，该目录被 Git 忽略。任务设计和指标定义见 `docs/EVALUATION.md`。

2026-09-15 已完成首轮 50×3 基线：113/150 试次通过、Pass@3 86%、Pass^3 62%；其中包含 7 次供应商连接失败。修复后最后 4 个问题任务定向复测 12/12。两者不能拼接成“修复后全量通过率”，当前提交仍需另做完整 50×3 复跑。可公开复核的脱敏汇总见 `v0.8-live-summary.json`。
