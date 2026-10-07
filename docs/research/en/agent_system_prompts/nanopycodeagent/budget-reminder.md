# Runtime-budget reminder generator

> Analysis generated from the [Chinese source](../../../zh-CN/agent_system_prompts/nanopycodeagent/budget-reminder.md). This version preserves the upstream English original; the Chinese version contains its full translation. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged.

## Source and applicability

- Inspected: 2026-10-05
- Pinned revision: `c8c5bf7d8a06c3e67403f3389cabc2632abf5b39`
- [Original source](https://github.com/minixalpha/nanoPyCodeAgent/blob/c8c5bf7d8a06c3e67403f3389cabc2632abf5b39/src/nanopycodeagent/agent.py)
- Selector: `Python function _time_budget_note`
- Source file: [src/nanopycodeagent/agent.py](../../../../../src/nanopycodeagent/agent.py)
- Source file SHA256: `8e28a5c3fcd140441484c46d1e62ec811d325aaff484141a4b9837baead6fc52`
- Chinese translation SHA256: `bef26d2bdcc5c7338c3f0f81300296ab40c894eae0694b8329c8c133cd3aa0e1`
- English original SHA256: `54181c1e60d1fd225a04117c9a02600290d1e48cd52632464f1a80f42f86ccb8`

Dynamic-prompt builder source.

Appends budget guidance before requests; low time or reply counts trigger finalization guidance.

## Content directions

- Time, reply count, no tools on the final reply, deliverable preservation, necessary checks, and stopping rules.

## Implications for nanoPyCodeAgent

Verification guidance must fit remaining budgets; existing reminders already require checks and timely completion, so the study must not claim verification was previously absent.

## Original text

The Chinese version translates natural-language comments and prompt strings in this builder while preserving code structure. It is a reading translation of source code, not a captured runtime request.

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
