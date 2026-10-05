# 截断恢复注入提示词

> 中文源文件；[英文版](../../../en/agent_system_prompts/nanopycodeagent/truncation-recovery.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [原始来源](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- 定位：`Python string expression _TRUNCATION_RECOVERY_NOTE`
- Source file: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- Source file SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- Archived text SHA256: `294ebbb8fa4b684d743867433c89e4f2242de950bc06201be798fe873d38acbd`

当前主线基准的完整字符串值；组合字符串已展开。

见 agent.py 中 _TRUNCATION_RECOVERY_NOTE 的引用。

## 内容方向

- 从已确认工具结果和文件继续；不增加预算，每轮运行只恢复一次。

## 对 nanoPyCodeAgent 的启示

作为本轮比较基准；本调研尚未修改运行提示词，也未运行新的模型实验。

## 原文

````text
The previous response reached its output limit without finishing the task. No tool calls from that response were executed. Continue from the last confirmed tool results and current files within the remaining budget. This is the only automatic truncation recovery for this run.
````
