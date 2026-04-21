"""Priority execution queue for XisWalker.

Single worker thread processes missions in priority order (INTERRUPT before NORMAL).
Preemption is cooperative: the worker signals play_composite via a callback, which
raises PreemptSignal at the next safe boundary (wait / ocr_timer step). The saved
resume state is re-enqueued so the NORMAL mission resumes after the INTERRUPT finishes.
"""

import heapq
import itertools
import threading
import time
import logging
import uuid
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, Optional

from xiswalker.models import MissionPriority

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal exception raised inside play_composite when preempted.
# Caught ONLY by ExecutorQueue._run_job — not a public API.
# ---------------------------------------------------------------------------

class PreemptSignal(Exception):
    """Raised inside play_composite to signal a safe preemption point.

    Attributes:
        step_index: The step that was interrupted (will be resumed).
        remaining_seconds: Seconds left in the current wait/timer at the point
                           of preemption.
    """

    def __init__(self, step_index: int, remaining_seconds: float) -> None:
        super().__init__(f"Preempted at step {step_index} with {remaining_seconds:.1f}s remaining")
        self.step_index = step_index
        self.remaining_seconds = remaining_seconds


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ResumeState:
    """Saved execution state for a preempted NORMAL mission."""
    mission_name: str
    step_index: int
    remaining_seconds: float


@dataclass
class _QueuedJob:
    """Internal heap entry. Comparable by (priority, enqueue_seq) for stable ordering."""
    priority: MissionPriority
    enqueue_seq: int           # Monotonically increasing; breaks ties within same priority
    mission_name: str
    execution_id: str = ""
    mission_type: str = "composite"
    humanize: float = 0.0
    resume: Optional[ResumeState] = None

    def __lt__(self, other: "_QueuedJob") -> bool:
        # Lower numeric value = higher urgency (INTERRUPT=0 < NORMAL=1)
        return (self.priority, self.enqueue_seq) < (other.priority, other.enqueue_seq)


# ---------------------------------------------------------------------------
# ExecutorQueue
# ---------------------------------------------------------------------------

class ExecutorQueue:
    """Priority-based serial mission executor.

    Public API:
        enqueue(mission_name, priority)  — add a mission to the queue
        stop()                           — signal the worker thread to exit cleanly

    The worker thread pops jobs in priority order and calls play_composite.
    For preemptible steps (wait, ocr_timer) in NORMAL missions it passes a
    check_interrupt callback; when an INTERRUPT job arrives, the callback
    causes play_composite to raise PreemptSignal, which the worker catches,
    saves resume state, and runs the INTERRUPT mission first.
    """

    def __init__(self) -> None:
        self._heap: list[_QueuedJob] = []
        self._heap_lock = threading.Lock()
        self._work_event = threading.Event()  # Signalled when a job is enqueued
        self._stop_event = threading.Event()
        self._counter = itertools.count()
        self._execution_status: dict[str, str] = {}
        self._execution_meta: dict[str, dict] = {}  # eid → {mission, mission_type, priority}
        self._status_lock = threading.Lock()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="ExecutorWorker")
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        mission_name: str,
        priority: MissionPriority,
        mission_type: str = "composite",
        humanize: float = 0.0,
    ) -> str:
        """Add a mission to the queue and return its execution ID.

        Args:
            mission_name: Name of the mission to execute.
            priority: Execution priority (INTERRUPT or NORMAL).
            mission_type: "atomic" or "composite".
            humanize: Timing variance fraction (e.g. 0.05 for ±5%).

        Returns:
            A unique execution ID (UUID4) for polling via get_status().
        """
        eid = str(uuid.uuid4())
        job = _QueuedJob(
            priority=priority,
            enqueue_seq=next(self._counter),
            mission_name=mission_name,
            execution_id=eid,
            mission_type=mission_type,
            humanize=humanize,
        )
        with self._status_lock:
            self._execution_status[eid] = "pending"
            self._execution_meta[eid] = {
                "mission": mission_name,
                "mission_type": mission_type,
                "priority": priority.name,
                "enqueued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        with self._heap_lock:
            heapq.heappush(self._heap, job)
        self._work_event.set()
        logger.info("Enqueued '%s' (priority=%s, id=%s)", mission_name, priority.name, eid)
        return eid

    def stop(self) -> None:
        """Signal the worker thread to exit after finishing the current job."""
        self._stop_event.set()
        self._work_event.set()  # Wake up the worker so it sees the stop signal
        self._thread.join(timeout=5)

    def list_executions(self) -> dict[str, dict]:
        """Return a snapshot of all known executions with their metadata and status.

        Returns:
            Dict keyed by execution_id with keys:
            mission, mission_type, priority, status.
        """
        with self._status_lock:
            return {
                eid: {**self._execution_meta.get(eid, {}), "status": status}
                for eid, status in self._execution_status.items()
            }

    def get_status(self, execution_id: str) -> str:
        """Return the current status of an execution.

        Args:
            execution_id: UUID returned by enqueue().

        Returns:
            One of: "pending", "running", "success", "failed", "stopped",
            "cancelled", or "not_found" if the ID is unknown.
        """
        with self._status_lock:
            return self._execution_status.get(execution_id, "not_found")

    def abort_all(self) -> None:
        """Drain the queue and trigger global stop to abort the running job.

        All pending (queued but not yet started) jobs are marked "cancelled".
        The currently running job is aborted via the global stop event;
        its status is updated to "stopped" by _run_job().
        """
        from xiswalker.safety import trigger_global_stop
        cancelled_ids: list[str] = []
        with self._heap_lock:
            cancelled_ids = [j.execution_id for j in self._heap if j.execution_id]
            self._heap.clear()
            heapq.heapify(self._heap)
        with self._status_lock:
            for eid in cancelled_ids:
                self._execution_status[eid] = "cancelled"
        trigger_global_stop()
        logger.info("abort_all: cancelled %d queued jobs and triggered global stop", len(cancelled_ids))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_interrupt(self) -> bool:
        """Return True if an INTERRUPT job is waiting in the queue (lock-free peek)."""
        with self._heap_lock:
            return bool(self._heap) and self._heap[0].priority == MissionPriority.INTERRUPT

    def _pop_job(self) -> Optional[_QueuedJob]:
        with self._heap_lock:
            if self._heap:
                return heapq.heappop(self._heap)
            return None

    def _push_job(self, job: _QueuedJob) -> None:
        with self._heap_lock:
            heapq.heappush(self._heap, job)
        self._work_event.set()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            self._work_event.wait()
            self._work_event.clear()

            if self._stop_event.is_set():
                break

            while True:
                job = self._pop_job()
                if job is None:
                    break
                self._run_job(job)

    def _run_job(self, job: _QueuedJob) -> None:
        """Execute a single queued job. Handles preemption for NORMAL jobs."""
        from xiswalker.player import play_atomic, play_composite
        from xiswalker.safety import is_global_stop_active

        eid = job.execution_id

        def _set_status(status: str) -> None:
            if eid:
                with self._status_lock:
                    self._execution_status[eid] = status

        _set_status("running")
        is_interrupt = job.priority == MissionPriority.INTERRUPT

        # INTERRUPT missions run to completion — no preemption callback needed.
        if is_interrupt:
            logger.info("Running INTERRUPT mission '%s'", job.mission_name)
            try:
                if job.mission_type == "atomic":
                    play_atomic(job.mission_name, humanize=job.humanize)
                else:
                    play_composite(job.mission_name, humanize=job.humanize)
                _set_status("stopped" if is_global_stop_active() else "success")
            except Exception as exc:
                logger.error("INTERRUPT mission '%s' failed: %s", job.mission_name, exc)
                _set_status("failed")
            return

        # NORMAL missions: inject a check_interrupt callback.
        # If an INTERRUPT job arrives while a preemptible step is sleeping,
        # the callback returns True and play_composite raises PreemptSignal.
        check_interrupt: Callable[[], bool] = self._has_interrupt

        logger.info("Running NORMAL mission '%s' (step=%s, remaining=%.1fs)",
                    job.mission_name,
                    job.resume.step_index if job.resume else 0,
                    job.resume.remaining_seconds if job.resume else 0.0)
        try:
            if job.mission_type == "atomic":
                play_atomic(job.mission_name, humanize=job.humanize)
            else:
                play_composite(
                    job.mission_name,
                    humanize=job.humanize,
                    check_interrupt=check_interrupt,
                    resume_state=job.resume,
                )
            _set_status("stopped" if is_global_stop_active() else "success")
        except PreemptSignal as preempt:
            logger.info(
                "Mission '%s' preempted at step %d (%.1fs remaining) — saving resume state",
                job.mission_name, preempt.step_index, preempt.remaining_seconds,
            )
            _set_status("pending")
            resume = ResumeState(
                mission_name=job.mission_name,
                step_index=preempt.step_index,
                remaining_seconds=preempt.remaining_seconds,
            )
            # Re-enqueue the paused NORMAL job; preserve execution_id so callers
            # can continue polling the same ID. Gets a new seq to maintain ordering.
            resumed_job = _QueuedJob(
                priority=MissionPriority.NORMAL,
                enqueue_seq=next(self._counter),
                mission_name=job.mission_name,
                execution_id=job.execution_id,
                mission_type=job.mission_type,
                humanize=job.humanize,
                resume=resume,
            )
            self._push_job(resumed_job)
        except Exception as exc:
            logger.error("NORMAL mission '%s' failed: %s", job.mission_name, exc)
            _set_status("failed")
