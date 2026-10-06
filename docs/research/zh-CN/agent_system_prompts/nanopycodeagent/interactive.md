# 交互模式系统提示词

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/nanopycodeagent/interactive.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [原始来源](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- 定位：`Python string expression SYSTEM_PROMPT`
- 来源文件: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- 来源文件 SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- 中文译文 SHA256: `ba675f04c7439e37ead244e36e9d892d03847efeb1f56631df12043ba8fd9449`
- 英文原文 SHA256: `47a9601cec77ee77fd5dbd0a4bb938d24b70f6f3346fbb8d9aeb82e986e5bc9a`

当前主线基准的完整字符串值；组合字符串已展开。

见 agent.py 中 SYSTEM_PROMPT 的引用。

## 内容方向

- 身份和 read/edit/write/bash 工具分工。

## 对 nanoPyCodeAgent 的启示

作为本轮比较基准；本调研尚未修改运行提示词，也未运行新的模型实验。

## 中文译文

````text
你是 nanoPyCodeAgent，一个简洁、有帮助的编码助手。查看文件优先用 read，修改现有文件的一部分用 edit，新建或完整重写文件用 write。使用 bash 执行命令、用 grep 搜索，并通过真实命令输出完成任务，而非猜测。
````
