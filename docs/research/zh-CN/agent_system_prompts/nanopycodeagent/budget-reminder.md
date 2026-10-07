# 运行预算提醒生成器

> 中文解读为源文件；[英文版](../../../en/agent_system_prompts/nanopycodeagent/budget-reminder.md) 同步解读并保留上游英文原文。下方为全文中文译文；工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [原始来源](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- 定位：`Python function _time_budget_note`
- 来源文件: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- 来源文件 SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- 中文译文 SHA256: `bef26d2bdcc5c7338c3f0f81300296ab40c894eae0694b8329c8c133cd3aa0e1`
- 英文原文 SHA256: `54181c1e60d1fd225a04117c9a02600290d1e48cd52632464f1a80f42f86ccb8`

动态提示词生成器源码。

每次请求前追加运行预算消息；剩余时间或回合不足时切换收尾提醒。

## 内容方向

- 时间、回合、最后一回合工具不会执行、保存交付物、必要检查与停止条件。

## 对 nanoPyCodeAgent 的启示

验证指导必须与剩余预算兼容；现有提醒已经要求检查与及时完成，不能在研究中写成从未要求验证。

## 中文译文

本节翻译生成器源码中的自然语言注释和提示词字符串，保留代码结构；它是供阅读的源码译本，不是实际请求的运行捕获。

````text
def _time_budget_note(
    *, turn: int, elapsed: float, budget: float | None, remaining: float | None,
    max_turns: int | None = None,
) -> str:
    """在任一上限阻止正常收尾前，将两种限制告知模型。"""
    replies_left = None if max_turns is None else max_turns - turn + 1
    turn_note = f"第 {turn} 回合。 " if max_turns is None else (
        f"第 {turn} 回合，共 {max_turns} 回合；还剩 {replies_left} 次回复，包括"
        "本次。最后一次回复必须是最终总结，其中的工具调用"
        "不会执行。 "
    )
    time_low = remaining is not None and remaining <= max(
        _FINALIZATION_RESERVE_FRACTION * budget, _FINALIZATION_RESERVE_SECONDS
    )
    note = "[runtime budget] " + turn_note
    if remaining is not None:
        note += (
            f"仅剩 {_format_duration(remaining)}，总预算 {_format_duration(budget)}。 "
            if time_low else
            f"已用 {_format_duration(elapsed)}，总预算 {_format_duration(budget)}；"
            f"还剩 {_format_duration(remaining)}。 "
        )
    if time_low or (replies_left is not None and replies_left <= _FINALIZATION_RESERVE_TURNS):
        note += (
            "现在收尾。停止探索新方法，完成并保存"
            "必需交付物，只进行必要检查，然后"
            "给出简短总结，不再调用工具。如果尚未完成，"
            "保存有用进展，并如实说明剩余限制。"
        )
    else:
        note += (
            "保持必需交付物最新。一旦要求"
            "已满足并检查，立即完成；预算尚有剩余并不是"
            "继续调查的理由。"
        )
    return note
````
