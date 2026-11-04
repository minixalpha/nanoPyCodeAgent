"""Audited accounting cannot silently promote flags or discard violations."""

import json

import pytest

from harbor_adapter.audit import audit_job


@pytest.fixture
def job(tmp_path):
    root = tmp_path / "job"
    root.mkdir()
    (root / "result.json").write_text(json.dumps({"finished_at": "2026-11-03T00:00:00Z"}))
    for name, reward, error in [("pass", 1, None), ("fail", 0, None), ("infra", 0, "VerifierTimeoutError")]:
        trial = root / name
        (trial / "agent").mkdir(parents=True)
        (trial / "result.json").write_text(json.dumps({
            "task_name": name, "verifier_result": {"rewards": {"reward": reward}},
            "exception_info": {"exception_type": error} if error else None,
        }))
        (trial / "agent/pi.txt").write_text("curl https://host/terminal-bench/task/solution/solve.sh\n")
    return root


def test_scanner_does_not_convict_and_does_not_publish_partial_rate(job, tmp_path):
    report = audit_job(job, tmp_path / "audit")
    assert report["findings"]
    assert report["summary"] == {
        "eligible_trials": 2, "pending_review": 2, "integrity_violations": 0,
        "unscored_or_errors": 1, "effective_pass_rate": None,
    }
    assert all(row["effective_score"] is None for row in report["trials"])


def reviews(report):
    return {"freeze_sha256": report["freeze_sha256"], "trials": {
        name: {"verdict": verdict, "reviewer": "maintainer", "reason": "Reviewed surrounding tool arguments and results.",
               "evidence": [name + "/agent/pi.txt"]}
        for name, verdict in [("pass", "violation"), ("fail", "clear")]
    }}


def test_confirmed_violation_keeps_original_reward_and_denominator(job, tmp_path):
    output = tmp_path / "audit"
    initial = audit_job(job, output)
    review = tmp_path / "review.json"
    review.write_text(json.dumps(reviews(initial)))
    report = audit_job(job, output, review)
    assert report["summary"]["eligible_trials"] == 2
    assert report["summary"]["integrity_violations"] == 1
    assert report["summary"]["effective_pass_rate"] == 0
    row = next(row for row in report["trials"] if row["trial"] == "pass")
    assert row["native_rewards"] == {"reward": 1}
    assert row["effective_score"] == 0
    assert json.loads((job / "pass/result.json").read_text())["verifier_result"]["rewards"]["reward"] == 1
    assert json.loads((output / "audit.json").read_text()) == initial
    assert list(output.glob("audit-*.json"))


@pytest.mark.parametrize("change", ["modify", "add", "delete", "symlink"])
def test_changed_evidence_invalidates_the_existing_freeze(job, tmp_path, change):
    output = tmp_path / "audit"
    audit_job(job, output)
    path = job / "pass/agent/pi.txt"
    if change == "modify":
        path.write_text("changed")
    elif change == "add":
        (job / "added").write_text("new")
    elif change == "delete":
        path.unlink()
    else:
        (job / "link").symlink_to(path)
    with pytest.raises(ValueError):
        audit_job(job, output)


def test_review_of_wrong_freeze_or_infrastructure_failure_is_rejected(job, tmp_path):
    output = tmp_path / "audit"
    initial = audit_job(job, output)
    review = tmp_path / "review.json"
    value = reviews(initial)
    value["freeze_sha256"] = "wrong"
    review.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="exact freeze"):
        audit_job(job, output, review)
    value = reviews(initial)
    value["trials"] = {"infra": value["trials"]["fail"] | {"evidence": ["infra/agent/pi.txt"]}}
    review.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="infrastructure"):
        audit_job(job, output, review)


def test_missing_enforcement_in_restricted_run_is_an_error_not_a_pass(job, tmp_path):
    (job / "pass/config.json").write_text(json.dumps({"agent": {"kwargs": {"integrity_policy": {"protocol": "restricted-v1"}}}}))
    report = audit_job(job, tmp_path / "audit")
    row = next(row for row in report["trials"] if row["trial"] == "pass")
    assert row["classification"] == "integrity_error"
    assert row["effective_score"] is None


def test_no_scan_matches_still_requires_review(job, tmp_path):
    for path in job.glob("*/agent/pi.txt"):
        path.write_text("ordinary output")
    report = audit_job(job, tmp_path / "audit")
    assert not report["findings"]
    assert report["summary"]["pending_review"] == 2


def test_confirmed_timeout_is_eligible_but_unconfirmed_timeout_is_not(job, tmp_path):
    path = job / "pass/result.json"
    result = json.loads(path.read_text())
    result["exception_info"] = {"exception_type": "AgentTimeoutError"}
    path.write_text(json.dumps(result))
    first = audit_job(job, tmp_path / "before")
    assert next(row for row in first["trials"] if row["trial"] == "pass")["eligible"] is False
    (job / "pass/agent/process-supervision.json").write_text(json.dumps({"status": "cancelled", "processes_stopped": True}))
    second = audit_job(job, tmp_path / "after")
    row = next(row for row in second["trials"] if row["trial"] == "pass")
    assert row["eligible"] is True and row["effective_score"] is None


def test_unfinished_job_is_not_frozen(job, tmp_path):
    (job / "result.json").write_text('{"finished_at": null}')
    with pytest.raises(ValueError, match="completed jobs"):
        audit_job(job, tmp_path / "audit")
    assert not (tmp_path / "audit/freeze.json").exists()


def test_missing_trial_results_cannot_shrink_the_denominator(job, tmp_path):
    (job / "result.json").write_text(json.dumps({
        "finished_at": "2026-11-03T00:00:00Z", "stats": {"n_completed_trials": 4},
    }))
    with pytest.raises(ValueError, match="inventory is incomplete"):
        audit_job(job, tmp_path / "audit")
