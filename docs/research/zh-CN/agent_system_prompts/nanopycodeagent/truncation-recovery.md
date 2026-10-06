# 截断恢复注入提示词

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/nanopycodeagent/truncation-recovery.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [原始来源](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- 定位：`Python string expression _TRUNCATION_RECOVERY_NOTE`
- 来源文件: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- 来源文件 SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- 中文译文 SHA256: `f066b5db9f2b41e4ee4da8841b8b9e904c9aee43b7de3554f6fb4996aaf9e937`
- 英文原文 SHA256: `294ebbb8fa4b684d743867433c89e4f2242de950bc06201be798fe873d38acbd`

当前主线基准的完整字符串值；组合字符串已展开。

见 agent.py 中 _TRUNCATION_RECOVERY_NOTE 的引用。

## 内容方向

- 从已确认工具结果和文件继续；不增加预算，每轮运行只恢复一次。

## 对 nanoPyCodeAgent 的启示

作为本轮比较基准；本调研尚未修改运行提示词，也未运行新的模型实验。

## 中文译文

````text
上一次回复在完成任务前达到了输出上限，其中的工具调用均未执行。请在剩余预算内，从最后确认的工具结果和当前文件继续。这是本次运行唯一一次自动截断恢复。
````
