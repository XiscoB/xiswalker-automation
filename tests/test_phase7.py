"""Tests for Phase 7 pure logic functions."""

import dataclasses
import json
import textwrap
from pathlib import Path
from xiswalker import stats
from xiswalker import importer


def test_stats_recording(tmp_path, monkeypatch):
    """Test that statistics are recorded and aggregated correctly."""
    monkeypatch.setattr(stats, "STATS_FILE", tmp_path / "stats.json")
    
    # Record first execution
    stats.record_execution("atomic", "test_m", True, 1.5)
    data = stats._load_stats()
    key = "atomic:test_m"
    
    assert key in data
    assert data[key]["attempts"] == 1
    assert data[key]["successes"] == 1
    assert data[key]["total_duration"] == 1.5
    
    # Record second execution (fail)
    stats.record_execution("atomic", "test_m", False, 2.0)
    data = stats._load_stats()
    
    assert data[key]["attempts"] == 2
    assert data[key]["successes"] == 1  # unchanged
    assert data[key]["total_duration"] == 3.5


def test_importer_import_json(tmp_path, monkeypatch):
    """Test importing a valid exported JSON string."""
    monkeypatch.setattr(importer, "MISSIONS_DIR", tmp_path)
    monkeypatch.setattr(importer, "ATOMIC_DIR", tmp_path / "atomic")
    monkeypatch.setattr(importer, "COMPOSITE_DIR", tmp_path / "composite")
    monkeypatch.setattr(importer, "TEMPLATES_DIR", tmp_path / "templates")
    
    # Create fake exported JSON
    export_json = {
        "export_version": 1,
        "type": "atomic",
        "name": "fake_mission",
        "atomics": {
            "fake_mission": '{"ts": 0.0, "type": "key_press", "key": "w"}'
        },
        "composites": {},
        "templates": {
            "fake_temp.png": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        }
    }
    
    importer.import_mission(json.dumps(export_json))
    
    # Verify files were created
    atomic_path = importer.ATOMIC_DIR / "fake_mission.jsonl"
    assert atomic_path.exists()
    assert "key_press" in atomic_path.read_text(encoding="utf-8")
    
    template_path = importer.TEMPLATES_DIR / "fake_temp.png"
    assert template_path.exists()
    assert template_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Phase 7 — Priority Execution Queue pure logic tests
# ---------------------------------------------------------------------------

def test_mission_priority_ordering():
    """INTERRUPT (0) must sort before NORMAL (1) so the heap pops it first."""
    from xiswalker.models import MissionPriority

    assert MissionPriority.INTERRUPT < MissionPriority.NORMAL
    assert int(MissionPriority.INTERRUPT) == 0
    assert int(MissionPriority.NORMAL) == 1


def test_queue_pop_order():
    """An INTERRUPT job enqueued after a NORMAL job must still be popped first."""
    import heapq
    from xiswalker.executor import _QueuedJob
    from xiswalker.models import MissionPriority

    heap: list = []
    normal_job = _QueuedJob(priority=MissionPriority.NORMAL, enqueue_seq=0, mission_name="farm")
    interrupt_job = _QueuedJob(priority=MissionPriority.INTERRUPT, enqueue_seq=1, mission_name="alive_check")

    heapq.heappush(heap, normal_job)
    heapq.heappush(heap, interrupt_job)

    first = heapq.heappop(heap)
    assert first.mission_name == "alive_check", "INTERRUPT must be popped before NORMAL"
    assert first.priority == MissionPriority.INTERRUPT


def test_resume_state_roundtrip():
    """ResumeState fields must survive a dataclasses.asdict() round-trip."""
    from xiswalker.executor import ResumeState

    original = ResumeState(mission_name="evening_farm", step_index=3, remaining_seconds=1243.5)
    as_dict = dataclasses.asdict(original)

    assert as_dict["mission_name"] == "evening_farm"
    assert as_dict["step_index"] == 3
    assert as_dict["remaining_seconds"] == 1243.5

    restored = ResumeState(**as_dict)
    assert restored == original


def test_repeat_every_minutes_parsed():
    """YAML with repeat_every_minutes must produce ScheduleTask with that field set."""
    import yaml
    import io
    from xiswalker.models import parse_schedules_yaml, MissionPriority

    yaml_text = textwrap.dedent("""\
        schedules:
          - name: alive_check
            composite: check_is_alive
            time: "00:00"
            days: []
            repeat_every_minutes: 5
            priority: INTERRUPT
    """)

    # Write to a temp file and parse
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        tmp_path = f.name

    try:
        tasks = parse_schedules_yaml(tmp_path)
    finally:
        os.unlink(tmp_path)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.repeat_every_minutes == 5
    assert task.priority == MissionPriority.INTERRUPT

