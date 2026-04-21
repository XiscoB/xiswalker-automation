"""Tests for Phase 8 — MCP server execution ID tracking (pure logic only)."""

import time
import uuid

import pytest

from xiswalker.executor import ExecutorQueue, _QueuedJob, ResumeState
from xiswalker.models import MissionPriority


# ---------------------------------------------------------------------------
# ExecutorQueue.enqueue — returns a valid UUID4 string
# ---------------------------------------------------------------------------


def test_enqueue_returns_uuid4_string():
    """enqueue() must return a non-empty UUID4 string."""
    q = ExecutorQueue()
    try:
        # Use a mission name that won't be found on disk; we only test the ID,
        # not the actual execution (which requires OS input APIs).
        eid = q.enqueue("nonexistent_test_mission", MissionPriority.NORMAL)
        assert isinstance(eid, str)
        assert len(eid) == 36  # UUID4 canonical length: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        parsed = uuid.UUID(eid, version=4)
        assert str(parsed) == eid
    finally:
        q.stop()


def test_enqueue_multiple_unique_ids():
    """Each enqueue() call must produce a distinct execution ID."""
    q = ExecutorQueue()
    try:
        ids = [q.enqueue("nonexistent_test_mission", MissionPriority.NORMAL) for _ in range(10)]
    finally:
        q.stop()
    assert len(set(ids)) == 10, "All execution IDs must be unique"


def test_enqueue_sets_pending_status():
    """A freshly enqueued job must be in 'pending' or 'running' state immediately."""
    q = ExecutorQueue()
    try:
        # Stop the worker so the job stays pending long enough to inspect.
        q._stop_event.set()  # Prevent worker from picking it up
        q._work_event.set()
        time.sleep(0.05)
        eid = q.enqueue("nonexistent_test_mission", MissionPriority.NORMAL)
        status = q.get_status(eid)
        # The worker is stopped so the job stays queued as "pending".
        assert status == "pending"
    finally:
        # Drain to avoid the worker thread blocking on job execution.
        with q._heap_lock:
            q._heap.clear()


# ---------------------------------------------------------------------------
# ExecutorQueue.get_status — unknown IDs return "not_found"
# ---------------------------------------------------------------------------


def test_get_status_unknown_id_returns_not_found():
    """get_status() with an unrecognised ID must return 'not_found'."""
    q = ExecutorQueue()
    try:
        result = q.get_status("00000000-dead-beef-cafe-000000000000")
        assert result == "not_found"
    finally:
        q.stop()


def test_get_status_known_id():
    """get_status() with a known ID returns a valid status string."""
    valid_statuses = {"pending", "running", "success", "failed", "stopped", "cancelled"}
    q = ExecutorQueue()
    try:
        q._stop_event.set()
        q._work_event.set()
        time.sleep(0.05)
        eid = q.enqueue("nonexistent_test_mission", MissionPriority.NORMAL)
        status = q.get_status(eid)
        assert status in valid_statuses
    finally:
        with q._heap_lock:
            q._heap.clear()


# ---------------------------------------------------------------------------
# MissionPriority ordering (pure enum test — no OS calls)
# ---------------------------------------------------------------------------


def test_interrupt_priority_less_than_normal():
    """INTERRUPT must have a lower numeric value than NORMAL (higher urgency)."""
    assert MissionPriority.INTERRUPT < MissionPriority.NORMAL


def test_queued_job_ordering():
    """_QueuedJob heap ordering: INTERRUPT jobs sort before NORMAL jobs."""
    import heapq

    normal_job = _QueuedJob(
        priority=MissionPriority.NORMAL,
        enqueue_seq=0,
        mission_name="normal_mission",
    )
    interrupt_job = _QueuedJob(
        priority=MissionPriority.INTERRUPT,
        enqueue_seq=1,
        mission_name="interrupt_mission",
    )

    heap: list[_QueuedJob] = []
    heapq.heappush(heap, normal_job)
    heapq.heappush(heap, interrupt_job)

    first = heapq.heappop(heap)
    assert first.priority == MissionPriority.INTERRUPT
    assert first.mission_name == "interrupt_mission"


# ---------------------------------------------------------------------------
# ResumeState — round-trip check (pure dataclass, no OS calls)
# ---------------------------------------------------------------------------


def test_resume_state_fields():
    """ResumeState must preserve all three fields exactly."""
    rs = ResumeState(mission_name="farm_mission", step_index=3, remaining_seconds=42.5)
    assert rs.mission_name == "farm_mission"
    assert rs.step_index == 3
    assert rs.remaining_seconds == 42.5


# ---------------------------------------------------------------------------
# abort_all — drains queue and marks cancelled
# ---------------------------------------------------------------------------


def test_abort_all_cancels_pending_jobs():
    """abort_all() must mark all queued-but-not-started jobs as 'cancelled'."""
    q = ExecutorQueue()
    try:
        # Freeze the worker so jobs stay queued.
        q._stop_event.set()
        q._work_event.set()
        time.sleep(0.05)

        eid1 = q.enqueue("mission_a", MissionPriority.NORMAL)
        eid2 = q.enqueue("mission_b", MissionPriority.NORMAL)

        q.abort_all()

        # Both IDs enqueued while worker was stopped should be cancelled.
        assert q.get_status(eid1) == "cancelled"
        assert q.get_status(eid2) == "cancelled"

        # Heap must be empty after drain.
        with q._heap_lock:
            assert len(q._heap) == 0
    finally:
        with q._heap_lock:
            q._heap.clear()
