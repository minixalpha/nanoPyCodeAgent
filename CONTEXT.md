# Code Agent Runtime

This glossary defines the runtime artifacts produced and maintained by a code agent so that public output, diagnostics, evaluation data, and resumable state remain distinct.

## Language

**Agent Run**:
A bounded execution that starts with an instruction and ends when the agent stops autonomous work.
_Avoid_: Session, turn

**Run Output**:
The public result or event protocol that one agent run emits to its caller.
_Avoid_: Trace, transcript

**Run Result Object**:
A single public object that summarizes how one Agent Run ended, including its final result and optional usage metadata.
_Avoid_: Trajectory, session export

**Public Event Stream**:
A caller-facing Run Output that exposes a stable, selected sequence of Agent Run events as they occur.
_Avoid_: Internal event bus, execution trace

**Partial Content**:
An unfinished representation of a message, reasoning block, or tool input that is exposed before the logical content is complete.
_Avoid_: Final message, completed event

**Content Delta**:
The incremental fragment or change relative to content already emitted for the same logical item.
_Avoid_: Partial snapshot, final message

**Terminal Event**:
The final Public Event Stream record that explicitly states how an Agent Run ended.
_Avoid_: EOF, last message

**Execution Trace**:
A diagnostic record of runtime activity retained to explain failures, timing, and internal behavior.
_Avoid_: Run output, trajectory

**Trajectory**:
A task-scoped record of observations, actions, results, and outcome prepared for evaluation or offline analysis.
_Avoid_: Execution trace, session, transcript

**Session**:
Durable agent state that can span multiple runs and supports continuing or branching prior work.
_Avoid_: Agent run, trajectory, transcript
