# 运行预算提醒生成器

> 中文源文件；[英文版](../../../en/agent_system_prompts/nanopycodeagent/budget-reminder.md) 由本文件生成。原文块保留来源语言，以下中文内容是解读，不是原文的逐字译本。

## 来源与适用范围

- 查阅日期：2026-10-05
- 固定版本：`c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [原始来源](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- 定位：`Python function _time_budget_note`
- Source file: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- Source file SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- Archived text SHA256: `54181c1e60d1fd225a04117c9a02600290d1e48cd52632464f1a80f42f86ccb8`

动态提示词生成器源码。

每次请求前追加运行预算消息；剩余时间或回合不足时切换收尾提醒。

## 内容方向

- 时间、回合、最后一回合工具不会执行、保存交付物、必要检查与停止条件。

## 对 nanoPyCodeAgent 的启示

验证指导必须与剩余预算兼容；现有提醒已经要求检查与及时完成，不能在研究中写成从未要求验证。

## 原文

````text
def _time_budget_note(
    *, turn: int, elapsed: float, budget: float | None, remaining: float | None,
    max_turns: int | None = None,
) -> str:
    """Tell the model about both limits before either prevents finalization."""
    replies_left = None if max_turns is None else max_turns - turn + 1
    turn_note = f"Turn {turn}. " if max_turns is None else (
        f"Turn {turn} of {max_turns}; {replies_left} replies remaining including "
        "this one. The last reply must be a final summary: its tool calls "
        "will not execute. "
    )
    time_low = remaining is not None and remaining <= max(
        _FINALIZATION_RESERVE_FRACTION * budget, _FINALIZATION_RESERVE_SECONDS
    )
    note = "[runtime budget] " + turn_note
    if remaining is not None:
        note += (
            f"Only {_format_duration(remaining)} of {_format_duration(budget)} left. "
            if time_low else
            f"Elapsed {_format_duration(elapsed)} of {_format_duration(budget)}; "
            f"{_format_duration(remaining)} remaining. "
        )
    if time_low or (replies_left is not None and replies_left <= _FINALIZATION_RESERVE_TURNS):
        note += (
            "Finalize now. Stop investigating new approaches. Complete and save "
            "the required deliverables, perform only the necessary checks, then "
            "reply with a short summary and no further tool calls. If incomplete, "
            "save useful progress and state the remaining limitation honestly."
        )
    else:
        note += (
            "Keep required deliverables up to date. Once the requirements are "
            "satisfied and checked, finish immediately; unused budget is not "
            "a reason to continue investigating."
        )
    return note
````
