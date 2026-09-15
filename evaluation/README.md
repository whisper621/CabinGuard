# Reliability Lab 任务资产

`cases.json` 是 Python 评测器与 TypeScript 页面共用的唯一任务源，当前版本为 `3.1.0`，包含 Base、Hallucination、Disambiguation 各 5 个任务。

每个任务声明场景、连续输入、期望/禁止工具、澄清或能力边界要求和最终状态断言。请不要在这里加入真实用户隐私、模型密钥或未授权的第三方数据。

```powershell
python -m cabinguard benchmark --list
python -m cabinguard benchmark --case D05 --trials 1
```

生成的模型报告默认放在 `evaluation/results/`，该目录被 Git 忽略。任务设计和指标定义见 `docs/EVALUATION.md`。
