"""MCP server for XisWalker — exposes mission execution tools to AI agents via stdio.

Transport: stdio (compatible with VS Code Copilot and Claude Desktop).
Entry point: xiswalker-mcp (defined in pyproject.toml).

Tools exposed:
  list_missions          — enumerate available atomics and composites
  get_mission_info       — duration, event count, templates for a mission
  play_atomic            — fire-and-forget atomic execution, returns execution_id
  play_composite         — fire-and-forget composite execution, returns execution_id
  get_execution_status   — poll running / success / failed / stopped
  stop_execution         — trigger emergency stop, drain queue
  get_stats              — recent run statistics
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from xiswalker.executor import ExecutorQueue
from xiswalker.models import MissionPriority, deserialize_event, parse_composite_yaml

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

mcp = FastMCP("XisWalker")
_executor = ExecutorQueue()

MISSIONS_DIR = Path("missions")
ATOMIC_DIR = MISSIONS_DIR / "atomic"
COMPOSITE_DIR = MISSIONS_DIR / "composite"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_missions() -> dict[str, list[str]]:
    """List all available atomic and composite missions.

    Returns a dict with two keys:
      atomics    — list of atomic mission names (without extension)
      composites — list of composite mission names (without extension)
    """
    atomics: list[str] = []
    composites: list[str] = []

    if ATOMIC_DIR.exists():
        atomics = sorted(p.stem for p in ATOMIC_DIR.glob("*.jsonl"))
    if COMPOSITE_DIR.exists():
        composites = sorted(p.stem for p in COMPOSITE_DIR.glob("*.yaml"))

    return {"atomics": atomics, "composites": composites}


@mcp.tool()
def get_mission_info(mission_type: str, name: str) -> dict[str, Any]:
    """Get metadata about a mission.

    Args:
        mission_type: "atomic" or "composite".
        name: Mission name (without file extension).

    Returns:
        For atomics: duration_seconds, event_count, templates.
        For composites: description, grace_period, step_count, total_wait_seconds, dependencies.
        On error: an "error" key with a description.
    """
    if mission_type == "atomic":
        path = ATOMIC_DIR / f"{name}.jsonl"
        if not path.exists():
            return {"error": f"Atomic mission not found: {name}"}
        events = []
        templates: list[str] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ev = deserialize_event(line)
                    events.append(ev)
                    if ev.template and ev.template not in templates:
                        templates.append(ev.template)
        duration = events[-1].timestamp if events else 0.0
        return {
            "name": name,
            "type": "atomic",
            "duration_seconds": round(duration, 2),
            "event_count": len(events),
            "templates": templates,
        }

    elif mission_type == "composite":
        path = COMPOSITE_DIR / f"{name}.yaml"
        if not path.exists():
            return {"error": f"Composite mission not found: {name}"}
        mission = parse_composite_yaml(str(path))
        total_wait = sum(s.wait for s in mission.steps if s.wait is not None)
        deps = sorted({s.mission for s in mission.steps if s.mission})
        return {
            "name": name,
            "type": "composite",
            "description": mission.description,
            "grace_period": mission.grace_period,
            "step_count": len(mission.steps),
            "total_wait_seconds": total_wait,
            "dependencies": deps,
        }

    return {"error": f"Unknown mission_type '{mission_type}'. Use 'atomic' or 'composite'."}


@mcp.tool()
def play_atomic(name: str, humanize: float = 0.0) -> dict[str, str]:
    """Execute an atomic mission asynchronously.

    Args:
        name: Atomic mission name (without extension).
        humanize: Timing variance fraction, e.g. 0.05 for ±5% (default 0.0).

    Returns:
        execution_id: UUID string for polling via get_execution_status().
    """
    execution_id = _executor.enqueue(name, MissionPriority.NORMAL, "atomic", humanize)
    return {"execution_id": execution_id}


@mcp.tool()
def play_composite(name: str, humanize: float = 0.0) -> dict[str, str]:
    """Execute a composite mission asynchronously.

    Args:
        name: Composite mission name (without extension).
        humanize: Timing variance fraction, e.g. 0.05 for ±5% (default 0.0).

    Returns:
        execution_id: UUID string for polling via get_execution_status().
    """
    execution_id = _executor.enqueue(name, MissionPriority.NORMAL, "composite", humanize)
    return {"execution_id": execution_id}


@mcp.tool()
def get_execution_status(execution_id: str) -> dict[str, str]:
    """Poll the status of a mission execution.

    Args:
        execution_id: UUID returned by play_atomic() or play_composite().

    Returns:
        status: One of "pending", "running", "success", "failed",
                "stopped", "cancelled", or "not_found".
    """
    return {"status": _executor.get_status(execution_id)}


@mcp.tool()
def stop_execution() -> dict[str, bool]:
    """Trigger emergency stop.

    Drains the pending queue (those jobs are marked "cancelled") and sends a
    global stop signal so the currently running mission aborts at the next
    safe check point. All held keys are released by the SafetyContext.

    Returns:
        stopped: Always True.
    """
    _executor.abort_all()
    return {"stopped": True}


@mcp.tool()
def get_stats() -> dict[str, Any]:
    """Get recent execution statistics for all missions.

    Returns a dict keyed by "<type>:<name>" with fields:
      attempts, successes, total_duration, last_run.
    Returns an empty dict if no stats have been recorded yet.
    """
    from xiswalker.stats import _load_stats
    return _load_stats()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server on stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
