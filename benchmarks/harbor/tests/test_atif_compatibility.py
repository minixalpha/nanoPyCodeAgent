"""Compatibility checks against Harbor's pinned ATIF-v1.7 validator."""

from pathlib import Path

from harbor.utils.trajectory_validator import TrajectoryValidator
from nanopycodeagent.atif import project_atif
from nanopycodeagent.event_journal import EventJournal


def test_projector_output_passes_harbor_atif_validator():
    journal_path = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    trajectory = project_atif(EventJournal.replay(journal_path))
    validator = TrajectoryValidator()

    assert validator.validate(trajectory), validator.get_errors()
