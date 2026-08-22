# Code Agent Runtime

This glossary defines the runtime artifacts produced and maintained by a code agent so that public output, diagnostics, evaluation data, and resumable state remain distinct.

## Language

**Agent Run**:
A bounded execution that starts with an instruction and ends when the agent stops autonomous work.
_Avoid_: Session, turn

**Run Output**:
The public result or event protocol that one agent run emits to its caller.
_Avoid_: Trace, transcript

**Execution Trace**:
A diagnostic record of runtime activity retained to explain failures, timing, and internal behavior.
_Avoid_: Run output, trajectory

**Trajectory**:
A task-scoped record of observations, actions, results, and outcome prepared for evaluation or offline analysis.
_Avoid_: Execution trace, session, transcript

**Session**:
Durable agent state that can span multiple runs and supports continuing or branching prior work.
_Avoid_: Agent run, trajectory, transcript
