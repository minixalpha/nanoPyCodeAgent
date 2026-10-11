"""Collect a completed, audited comparison without running models or verifiers.

Run from the repository root. Local job artifacts and frozen source worktrees
must still exist. Costs are estimates; missing accounting remains incomplete.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from run_comparison import digest, validate_plan


def accounting(metrics):
    extra = metrics.get("extra", {})
    total = metrics.get("total_cost_usd")
    return {
        "known_cost_usd": total if total is not None else extra.get("known_cost_usd"),
        "cost_complete": total is not None and not extra.get("cost_is_partial", False),
        "usage_complete": extra.get("usage_complete", True) and all(
            metrics.get(key) is not None for key in (
                "total_prompt_tokens", "total_completion_tokens", "total_cached_tokens",
            )
        ),
    }


def classify(result, audit):
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    exception = (result.get("exception_info") or {}).get("exception_type")
    native = "execution_error" if exception else "scored" if reward is not None else "unscored"
    status = native
    if audit.get("score_classification") == "verifier_dependency_error":
        status = "verifier_error"
        reward = None
    return {
        "native_status": native, "native_reward": rewards.get("reward"),
        "raw_verifier_rewards": rewards, "exception_type": exception,
        "status": status, "reward": reward,
        "eligible_as_independent_capability_evidence": status == "scored"
        and audit.get("score_valid_for_capability_comparison") is True
        and audit.get("eligible_as_independent_capability_evidence") is True,
    }


def summarize(rows):
    costs = [r["known_cost_usd"] for r in rows if r["known_cost_usd"] is not None]
    return {
        "trials": len(rows), "statuses": dict(Counter(r["status"] for r in rows)),
        "passes": sum(r["status"] == "scored" and r["reward"] == 1 for r in rows),
        "scored_failures": sum(r["status"] == "scored" and r["reward"] == 0 for r in rows),
        "known_cost_usd": round(sum(costs), 9) if costs else None,
        "cost_complete": bool(rows) and all(r["cost_complete"] for r in rows),
        "usage_complete": bool(rows) and all(r["usage_complete"] for r in rows),
        "incomplete_accounting_trials": sum(not r["cost_complete"] for r in rows),
        "agent_execution_seconds": sum(r["agent_execution_seconds"] for r in rows),
        "model_attempts": sum(r["model_attempts"] for r in rows),
        "incomplete_model_attempts": sum(r["incomplete_model_attempts"] for r in rows),
        "tool_timeouts": sum(r["tool_timeouts"] for r in rows),
    }


def common_cases(rows, arms):
    eligible = {
        arm: {(r["task"], r["repeat"]) for r in rows if r["arm"] == arm
              and r["eligible_as_independent_capability_evidence"]}
        for arm in arms
    }
    return set.intersection(*eligible.values())


def seconds(interval):
    return (datetime.fromisoformat(interval["finished_at"]) -
            datetime.fromisoformat(interval["started_at"])).total_seconds()


def load_checked(path, expected_hash):
    if digest(path) != expected_hash:
        raise ValueError(f"Evidence hash mismatch: {path}")
    return json.loads(path.read_text())


def collect(root, plan_path, audit_path):
    plan = json.loads(plan_path.read_text())
    validate_plan(root, plan_path, plan)
    registration = json.loads((root / plan["log_dir"] / "registration.json").read_text())
    if registration != {"plan_sha256": digest(plan_path), "plan": plan}:
        raise ValueError("Registered plan changed")
    audit = json.loads(audit_path.read_text())
    audits = {a["job"]: a for a in audit["trials"]}
    expected_jobs = {j["job_name"] for j in plan["queue"]}
    if (audit["status"] != "completed" or set(audits) != expected_jobs
            or len(audit["trials"]) != len(expected_jobs)):
        raise ValueError("Every planned trial needs exactly one completed audit")
    tasks = {t["name"]: t for t in plan["tasks"]}
    rows = []
    for job in plan["queue"]:
        arm = plan["arms"][job["arm"]]
        source = root / arm["source_root"]
        state = json.loads((root / plan["log_dir"] / (job["job_name"] + ".json")).read_text())
        if state["status"] != "finished":
            raise ValueError(f"Unfinished job: {job['job_name']}")
        results = list((source / "jobs" / job["job_name"]).glob("*/result.json"))
        if len(results) != 1:
            raise ValueError(f"Expected one trial: {job['job_name']}")
        result_path = results[0]
        result = json.loads(result_path.read_text())
        if not result.get("finished_at"):
            raise ValueError(f"Unfinished trial: {result_path}")
        evidence = audits[job["job_name"]]
        trajectory_path = result_path.parent / "agent/trajectory.json"
        if root / evidence["trajectory_path"] != trajectory_path:
            raise ValueError("Audit points to a different trial")
        trajectory = load_checked(trajectory_path, evidence["trajectory_sha256"])
        stdout = result_path.parent / "verifier/test-stdout.txt"
        if (root / evidence["verifier_stdout_path"] != stdout
                or digest(stdout) != evidence["verifier_stdout_sha256"]):
            raise ValueError(f"Verifier evidence changed: {stdout}")
        bootstrap = json.loads((result_path.parent / "agent/bootstrap.json").read_text())
        manifest_path = source / "jobs" / (job["job_name"] + "-input/manifest.json")
        manifest = json.loads(manifest_path.read_text())
        if manifest["commit"] != arm["source_ref"]:
            raise ValueError("Trial source revision differs from the plan")
        wheel = Path(result["config"]["agent"]["kwargs"]["wheel_path"])
        if not (digest(wheel) == manifest["wheel_sha256"] == bootstrap["wheel_sha256"]):
            raise ValueError("Installed wheel differs from the recorded build")
        for name, expected in manifest["source_sha256"].items():
            prefix = "benchmarks/harbor/src" if name.startswith("harbor_adapter/") else "src"
            if digest(source / prefix / name) != expected:
                raise ValueError(f"Trial runtime source changed: {name}")
        task = tasks[job["task"]]
        if result["task_id"]["ref"] != task["ref"]:
            raise ValueError("Trial task revision differs from the plan")
        retry_path = result_path.parent / "verifier/retry-summary.json"
        retry = json.loads(retry_path.read_text())
        attempts = retry["attempts"]
        if not (retry["timeout_sec"] == task["verifier_timeout_seconds"]
                and retry["max_attempts"] == 3 and 1 <= len(attempts) <= 3
                and all(a["status"] == "timeout" for a in attempts[:-1])):
            raise ValueError("Verifier retries violate the registered policy")
        steps = trajectory["steps"]
        model_steps = [s for s in steps if s.get("llm_call_count")]
        observations = [o for s in steps for o in s.get("observation", {}).get("results", [])]
        metrics = trajectory["final_metrics"]
        rows.append({
            **job, "cohort": task["cohort"], **classify(result, evidence),
            **accounting(metrics), "metrics": metrics,
            "launcher_exit_code": state["exit_code"],
            "result_path": str(result_path.relative_to(root)),
            "result_sha256": digest(result_path), "task_checksum": result["task_checksum"],
            "trajectory_path": str(trajectory_path.relative_to(root)),
            "trajectory_sha256": digest(trajectory_path),
            "verifier_stdout_sha256": digest(stdout),
            "source_ref": manifest["commit"], "wheel_sha256": manifest["wheel_sha256"],
            "terminal": trajectory.get("extra", {}).get("terminal"),
            "started_at": result["started_at"], "finished_at": result["finished_at"],
            "agent_setup_seconds": seconds(result["agent_setup"]),
            "agent_execution_seconds": seconds(result["agent_execution"]),
            "verifier_seconds": seconds(result["verifier"]),
            "verifier_attempts": retry, "verifier_preflight": bootstrap["verifier_preflight"],
            "model_attempts": sum(s["llm_call_count"] for s in model_steps),
            "incomplete_model_attempts": sum(bool(s.get("extra", {}).get("incomplete")) for s in steps),
            "truncated_responses": sum(s.get("extra", {}).get("stop_reason") == "max_tokens" for s in steps),
            "tool_timeouts": sum("[command timed out after" in str(o.get("content", "")) for o in observations),
            "audit": evidence,
        })
    arms = list(plan["arms"])
    common = common_cases(rows, arms)
    paired = [r for r in rows if (r["task"], r["repeat"]) in common]
    held_out = [r for r in paired if r["cohort"] == "held_out_from_prior_tuning"]
    return {
        "schema_version": 2, "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_plan": str(plan_path.relative_to(root)),
        "experiment_plan_sha256": digest(plan_path),
        "audit_path": str(audit_path.relative_to(root)), "audit_sha256": digest(audit_path),
        "cost_note": "Token-based estimates, not invoices. Incomplete totals are known lower bounds, never zero-imputed.",
        "summary": {arm: summarize([r for r in rows if r["arm"] == arm]) for arm in arms},
        "common_eligible_cases": [dict(task=t, repeat=r) for t, r in sorted(common)],
        "common_eligible_summary": {arm: summarize([r for r in paired if r["arm"] == arm]) for arm in arms},
        "held_out_common_summary": {arm: summarize([r for r in held_out if r["arm"] == arm]) for arm in arms},
        "trials": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(Path.cwd(), args.plan.resolve(), args.audit.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
