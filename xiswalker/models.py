"""Event model and JSONL serialization for XisWalker."""

import json
from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Optional


@dataclass
class InputEvent:
    """A single recorded input event."""

    type: str  # "key_press", "key_release", "mouse_click", "mouse_press", "mouse_release", "mouse_move", "visual_click", "template_find", "relative_click"
    timestamp: float  # seconds since recording start
    key: Optional[str] = None  # key name (for keyboard events)
    x: Optional[int] = None  # mouse x coordinate (absolute or relative offset)
    y: Optional[int] = None  # mouse y coordinate (absolute or relative offset)
    button: Optional[str] = None  # mouse button name
    # Visual fields
    template: Optional[str] = None  # template image filename
    roi: Optional[list[int]] = None  # [x, y, w, h] region of interest
    threshold: Optional[float] = None  # match confidence threshold
    retry: Optional[int] = None  # number of retry attempts
    timeout: Optional[float] = None  # timeout in seconds for wait_visual
    # Relative click fields (for clicking within a found template)
    offset_x: Optional[int] = None  # X offset from template's top-left
    offset_y: Optional[int] = None  # Y offset from template's top-left
    # Template find fields
    abort_on_fail: Optional[bool] = None  # Whether to abort mission if template not found
    store_location: Optional[str] = None  # Variable name to store found location (for future use)
    # Relative recording fields (for recording actions relative to a template)
    relative_to_template: Optional[str] = None  # Template filename this event is relative to
    is_relative: Optional[bool] = None  # True if x,y are offsets from template's top-left


def serialize_event(event: InputEvent) -> str:
    """Serialize an InputEvent to a JSON line string.

    Args:
        event: The input event to serialize.

    Returns:
        A JSON string (single line, no trailing newline).
    """
    data = {k: v for k, v in asdict(event).items() if v is not None}
    return json.dumps(data)


def deserialize_event(line: str) -> InputEvent:
    """Deserialize a JSON line string into an InputEvent.

    Args:
        line: A JSON string representing an event.

    Returns:
        The parsed InputEvent.

    Raises:
        json.JSONDecodeError: If the line is not valid JSON.
        TypeError: If required fields are missing.
    """
    data = json.loads(line)
    return InputEvent(**data)


@dataclass
class CompositeStep:
    """A single step in a composite mission."""
    
    mission: Optional[str] = None
    atomic: bool = False
    retries: int = 0
    on_fail: str = "abort"  # abort | skip | continue
    humanization_override: Optional[float] = None
    wait: Optional[float] = None
    # Visual conditional fields
    visual_condition: Optional[str] = None  # Template filename to find
    on_found: Optional[str] = None  # Atomic mission to run if template found
    on_not_found: Optional[str] = None  # Atomic mission to run if template not found
    visual_threshold: Optional[float] = None  # Match confidence (default: 0.8)
    visual_timeout: Optional[float] = None  # Seconds to wait for template (default: 5.0)
    visual_click_x: Optional[int] = None  # X offset to click within found template/text
    visual_click_y: Optional[int] = None  # Y offset to click within found template/text
    visual_click_type: Optional[str] = None  # "left" (default) | "double" | "right"
    # OCR conditional fields (reuses on_found, on_not_found, on_fail, visual_click_x/y)
    ocr_text: Optional[str] = None              # Text string to locate on screen
    ocr_backend: Optional[str] = None           # "pytesseract" | "ollama"
    ocr_model: Optional[str] = None             # Ollama model name (e.g. "llava")
    ocr_threshold: Optional[float] = None       # Fuzzy match ratio (default: 0.8)
    ocr_roi: Optional[list] = None              # [x, y, w, h] region to search
    ocr_timeout: Optional[float] = None         # Max search time in seconds (default: 5.0)
    ocr_case_sensitive: Optional[bool] = None   # Case-sensitive matching (default: False)
    # OCR timer step — reads a timer from screen and waits for it to expire
    ocr_timer: Optional[bool] = None            # True to enable timer-wait mode
    ocr_timer_pre_scan_delay: Optional[float] = None  # Seconds to wait before first OCR scan
    timer_on_expire: Optional[str] = None       # Atomic mission to run when timer expires
    timer_loop: Optional[bool] = None           # Re-scan and reschedule after each run
    timer_loop_recheck_delay: Optional[float] = None  # Seconds to wait before re-scanning


@dataclass
class CompositeMission:
    """A composite mission comprised of multiple steps."""
    
    name: str
    description: str = ""
    grace_period: int = 5
    steps: Optional[list[CompositeStep]] = None

    def __post_init__(self) -> None:
        if self.steps is None:
            self.steps = []


def parse_composite_yaml(filepath: str) -> CompositeMission:
    """Parse a composite mission YAML file.

    Args:
        filepath: Path to the YAML file.

    Returns:
        The parsed CompositeMission object.

    Raises:
        ValueError: If the file is empty or invalid.
    """
    import yaml
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not data:
        raise ValueError(f"Empty or invalid composite mission YAML: {filepath}")
        
    steps = []
    for step_data in data.get("steps", []):
        steps.append(CompositeStep(**step_data))
        
    return CompositeMission(
        name=data.get("name", "Unknown"),
        description=data.get("description", ""),
        grace_period=data.get("grace_period", 5),
        steps=steps
    )

class MissionPriority(IntEnum):
    """Execution priority for queued missions."""
    INTERRUPT = 0   # Preempts whatever is running at the next safe boundary
    NORMAL = 1      # Standard mission execution


@dataclass
class ScheduleTask:
    """A single scheduled task definition."""
    name: str
    composite: str
    time: str
    days: list[str]
    safe_mode: bool = False
    repeat: int = 1
    priority: MissionPriority = MissionPriority.NORMAL
    repeat_every_minutes: Optional[int] = None
    jitter_seconds: int = 0  # Random delay 0..jitter_seconds added before each execution


def parse_schedules_yaml(filepath: str) -> list[ScheduleTask]:
    """Parse the schedules.yaml configuration.
    
    Args:
        filepath: Path to the YAML file.
        
    Returns:
        A list of ScheduleTask objects.
    """
    import yaml
    import os
    
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not data:
        return []

    schedule_items = data.get("schedules") or []
    if not schedule_items:
        return []

    tasks = []
    for item in schedule_items:
        raw_priority = item.get("priority", "NORMAL").upper()
        try:
            priority = MissionPriority[raw_priority]
        except KeyError:
            priority = MissionPriority.NORMAL
        tasks.append(ScheduleTask(
            name=item.get("name", "Unknown"),
            composite=item.get("composite", ""),
            time=item.get("time", "00:00"),
            days=item.get("days", []),
            safe_mode=item.get("safe_mode", False),
            repeat=item.get("repeat", 1),
            priority=priority,
            repeat_every_minutes=item.get("repeat_every_minutes", None),
            jitter_seconds=item.get("jitter_seconds", 0),
        ))
    return tasks
