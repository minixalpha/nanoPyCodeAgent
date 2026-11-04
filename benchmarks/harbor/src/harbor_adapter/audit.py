"""Freeze evidence, flag candidates, and apply explicit integrity reviews.

Scanning never proves a clean run or automatically convicts an agent. Original
Harbor rewards and errors remain untouched; reviews bind to one exact freeze.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .integrity import write_record


_PATTERNS = {
    "benchmark_reference": re.compile(r"terminal[-_]bench|RSIBench|solution[/\\]+solve\.sh", re.I),
    "verifier_access": re.compile(r"/logs/verifier|/tests/test_outputs\.py|reward\.(?:json|txt)", re.I),
}


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Cannot freeze symbolic-link evidence: {path.relative_to(root)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Cannot freeze special-file evidence: {path.relative_to(root)}")
        result[path.relative_to(root).as_posix()] = digest(path)
    return result


def freeze(job_dir, output_dir):
    result = json.loads((job_dir / "result.json").read_text())
    if not result.get("finished_at"):
        raise ValueError("Only completed jobs can be frozen for review")
    stats = result.get("stats") or {}
    if (stats.get("n_running_trials", 0) or stats.get("n_pending_trials", 0)
            or stats.get("n_completed_trials", len(list(job_dir.glob("*/result.json")))) != len(list(job_dir.glob("*/result.json")))):
        raise ValueError("Job trial inventory is incomplete; cannot publish selective accounting")
    files = inventory(job_dir)
    path = output_dir / "freeze.json"
    if path.exists():
        frozen = json.loads(path.read_text())
        if frozen["job_dir"] != str(job_dir) or frozen["files"] != files:
            raise ValueError("Job evidence changed after freezing; review is invalid")
    else:
        write_record(path, {
            "schema_version": 1, "job_dir": str(job_dir),
            "frozen_at": datetime.now(timezone.utc).isoformat(), "files": files,
        })
    return files, digest(path)


def scan(job_dir, files):
    """Return locations only; never publish credential-bearing excerpts."""
    findings = []
    for name in files:
        if not ("/agent/" in name or (name.startswith(".integrity/") and Path(name).name in {"live-output.jsonl", "egress-log.json"})):
            continue
        if Path(name).suffix not in {".txt", ".json", ".jsonl"}:
            continue
        with (job_dir / name).open(encoding="utf-8", errors="replace") as source:
            for number, line in enumerate(source, 1):
                for rule, pattern in _PATTERNS.items():
                    if pattern.search(line):
                        findings.append({"file": name, "line": number, "rule": rule})
    return findings


def read_reviews(path, freeze_sha256, files, trial_names):
    if path is None:
        return {}
    value = json.loads(path.read_text())
    if set(value) != {"freeze_sha256", "trials"} or value["freeze_sha256"] != freeze_sha256:
        raise ValueError("Review must identify this exact freeze_sha256")
    if not isinstance(value["trials"], dict) or set(value["trials"]) - trial_names:
        raise ValueError("Review contains unknown trial identifiers")
    for trial, review in value["trials"].items():
        if not isinstance(review, dict) or set(review) != {"verdict", "reviewer", "reason", "evidence"}:
            raise ValueError("Each review needs verdict, reviewer, reason, and evidence")
        if review["verdict"] not in {"clear", "violation"}:
            raise ValueError("A reviewed verdict must be clear or violation")
        if not all(isinstance(review[k], str) and review[k].strip() for k in ("reviewer", "reason")):
            raise ValueError("Reviews require an identified reviewer and a reason")
        evidence = review["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Reviews require frozen evidence references")
        if any(not isinstance(name, str) or name not in files or not name.startswith((trial + "/", ".integrity/" + trial + "/")) for name in evidence):
            raise ValueError("Review evidence must reference this trial's frozen files")
    return value["trials"]


def trial_accounting(job_dir, path, review):
    result = json.loads(path.read_text())
    exception = result.get("exception_info") or {}
    error = exception.get("exception_type")
    rewards = (result.get("verifier_result") or {}).get("rewards")
    raw_score = rewards.get("reward") if isinstance(rewards, dict) else None
    evidence_dir = job_dir / ".integrity" / path.parent.name
    proof_path = evidence_dir / "enforcement.json"
    proof = json.loads(proof_path.read_text()) if proof_path.exists() else None
    config_path = path.parent / "config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    required = bool(config.get("agent", {}).get("kwargs", {}).get("integrity_policy"))
    control_path = path.parent / "agent/process-supervision.json"
    control = json.loads(control_path.read_text()) if control_path.exists() else {}
    confirmed_timeout = (
        error == "AgentTimeoutError" and control.get("status") == "cancelled"
        and control.get("processes_stopped") is True
    )
    eligible = type(raw_score) in (float, int) and raw_score in (0, 1) and (not error or confirmed_timeout)
    enforcement_ok = bool(proof and proof.get("preflight") == "passed"
                          and proof.get("agent_phase") in {"completed", "interrupted"})
    if enforcement_ok:
        live = evidence_dir / "live-output.jsonl"
        expected_policy = config.get("agent", {}).get("kwargs", {}).get("integrity_policy")
        enforcement_ok = (
            live.is_file() and proof.get("live_output_sha256") == digest(live)
            and all((evidence_dir / name).is_file() for name in (
                "network-preflight.json", "network-before-agent.json", "network-after-agent.json", "egress-log.json",
            ))
            and (not expected_policy or proof.get("policy") == expected_policy)
        )
    if required and not enforcement_ok:
        eligible = False
        classification = "integrity_error"
    elif error and not confirmed_timeout:
        classification = ("setup_error" if "Setup" in error else
                          "verifier_error" if "Verif" in error else "execution_error")
    else:
        classification = "pending_review" if eligible else "unscored"
    if review and not eligible:
        raise ValueError("Cannot assign scored integrity verdicts to infrastructure errors or unscored trials")
    effective_score = None
    if review:
        classification = "integrity_violation" if review["verdict"] == "violation" else "no_observed_violation"
        effective_score = 0 if review["verdict"] == "violation" else raw_score
    return {
        "trial": path.parent.name, "task": result.get("task_name"),
        "native_rewards": rewards, "native_exception_type": error,
        "confirmed_timeout": confirmed_timeout,
        "enforcement": "restricted-v1" if enforcement_ok else "not_established",
        "verifier_isolation": proof.get("verifier_isolation") if proof else None,
        "classification": classification, "eligible": eligible,
        "effective_score": effective_score, "review": review,
    }


def audit_job(job_dir: Path, output_dir: Path, review_path: Path | None = None):
    job_dir, output_dir = job_dir.resolve(), output_dir.resolve()
    if output_dir == job_dir or job_dir in output_dir.parents:
        raise ValueError("Audit outputs must be outside the frozen job")
    files, freeze_sha256 = freeze(job_dir, output_dir)
    paths = sorted(job_dir.glob("*/result.json"))
    if not paths:
        raise ValueError("No trial results to audit")
    reviews = read_reviews(review_path, freeze_sha256, files, {p.parent.name for p in paths})
    rows = [trial_accounting(job_dir, p, reviews.get(p.parent.name)) for p in paths]
    findings = scan(job_dir, files)
    eligible = [row for row in rows if row["eligible"]]
    pending = sum(row["effective_score"] is None for row in eligible)
    summary = {
        "eligible_trials": len(eligible), "pending_review": pending,
        "integrity_violations": sum(row["classification"] == "integrity_violation" for row in rows),
        "unscored_or_errors": len(rows) - len(eligible),
        # Violations stay in the denominator. Never publish a selectively
        # reviewed pass rate while another eligible attempt is pending.
        "effective_pass_rate": (sum(row["effective_score"] for row in eligible) / len(eligible)
                                if eligible and not pending else None),
    }
    report = {
        "schema_version": 1, "freeze_sha256": freeze_sha256,
        "review_sha256": digest(review_path) if review_path else None,
        "scan_is_exhaustive": False,
        "note": "Candidate flags require review. No matches do not prove absence of reference exposure, tampering, or training contamination.",
        "summary": summary, "trials": rows, "findings": findings,
    }
    if inventory(job_dir) != files:
        raise ValueError("Evidence changed during audit")
    if review_path:
        # Preserve each reviewed revision instead of erasing earlier decisions.
        write_record(output_dir / ("review-" + report["review_sha256"] + ".json"), json.loads(review_path.read_text()))
        write_record(output_dir / ("audit-" + report["review_sha256"] + ".json"), report)
    else:
        write_record(output_dir / "audit.json", report)
    return report
