"""Player module â€” replays recorded JSONL missions."""

import time
from pathlib import Path
from typing import Callable, List, Optional, Set

from pynput.keyboard import Controller as KbController, Key, KeyCode
from pynput.mouse import Controller as MouseController, Button

from xiswalker.models import InputEvent, deserialize_event


MISSIONS_DIR = Path("missions")
ATOMIC_DIR = MISSIONS_DIR / "atomic"
COMPOSITE_DIR = MISSIONS_DIR / "composite"


# Map special key names back to pynput Key objects
_SPECIAL_KEYS = {k.name: k for k in Key}

# Map mouse button names back to pynput Button objects
_MOUSE_BUTTONS = {b.name: b for b in Button}


def _str_to_key(key_str: str) -> Key | KeyCode:
    """Convert a string key name back to a pynput key.

    Args:
        key_str: String representation of the key.

    Returns:
        The corresponding pynput Key or KeyCode.
    """
    if key_str in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key_str]
    if key_str.startswith("<") and key_str.endswith(">"):
        # Virtual key code - used for cross-keyboard compatibility
        vk = int(key_str[1:-1])
        return KeyCode.from_vk(vk)
    
    # Single character - use from_char
    if len(key_str) == 1:
        return KeyCode.from_char(key_str)
    
    # Fallback for unknown keys
    return KeyCode.from_char(key_str)


def load_atomic(name: str) -> List[InputEvent]:
    """Load an atomic mission from a JSONL file.

    Args:
        name: Mission name (without extension).

    Returns:
        List of InputEvent objects.

    Raises:
        FileNotFoundError: If the mission file does not exist.
    """
    filepath = ATOMIC_DIR / f"{name}.jsonl"
    if not filepath.exists():
        raise FileNotFoundError(f"Atomic mission not found: {filepath}")

    events: List[InputEvent] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(deserialize_event(line))
    return events


def _play_atomic_events(
    events: List[InputEvent],
    safety: 'SafetyContext',
    kb: KbController,
    ms: MouseController,
    humanize: float,
    window_patterns: List[str],
) -> bool:
    """Play a sequence of events.

    Returns:
        True if completed successfully, False if aborted.
    """
    from xiswalker.safety import apply_humanization, apply_mouse_jitter
    
    last_timestamp = 0.0

    for event in events:
        if safety.is_aborted():
            return False
            
        # Window focus check before each event
        if not safety.verify_window_focus(window_patterns):
            print(f"\n{Fore.RED}âŒ Window focus lost! Aborting mission.{Style.RESET_ALL}")
            safety._on_emergency_stop()
            return False

        # Sleep for the delta between events
        delta = event.timestamp - last_timestamp
        if delta > 0:
            delta = apply_humanization(delta, humanize)
            # Chunk sleep to allow rapid aborts
            while delta > 0 and not safety.is_aborted():
                sleep_time = min(0.05, delta)
                
                # Verify focus during long sleeps too
                if not safety.verify_window_focus(window_patterns):
                    print(f"\n{Fore.RED}âŒ Window focus lost during wait! Aborting.{Style.RESET_ALL}")
                    safety._on_emergency_stop() # trigger abort
                    return False
                

                time.sleep(sleep_time)
                delta -= sleep_time

        if safety.is_aborted():
            return False

        last_timestamp = event.timestamp

        if event.type == "key_press" and event.key is not None:
            safety.safe_press_key(_str_to_key(event.key))

        elif event.type == "key_release" and event.key is not None:
            safety.safe_release_key(_str_to_key(event.key))

        elif event.type == "visual_click" and event.template:
            from xiswalker.visual import VisualMatcher
            from pathlib import Path
            TEMPLATES_DIR = Path("missions") / "templates"
            matcher = VisualMatcher(TEMPLATES_DIR)
            
            attempts = event.retry if event.retry is not None else 3
            threshold = event.threshold if event.threshold is not None else 0.8
            found = False
            
            for attempt in range(attempts):
                if safety.is_aborted():
                    return False
                    
                if not safety.verify_window_focus(window_patterns):
                    print(f"\nâŒ Window focus lost before visual_click! Aborting.")
                    safety._on_emergency_stop()
                    return False
                    
                found, coords = matcher.find_and_click(event.template, event.roi, threshold)
                if found:
                    cx, cy = coords
                    if humanize > 0:
                        cx = apply_mouse_jitter(cx, 2)
                        cy = apply_mouse_jitter(cy, 2)
                    ms.position = (cx, cy)
                    safety.safe_press_mouse(Button.left)
                    if humanize > 0:
                        time.sleep(apply_humanization(0.05, humanize))
                    safety.safe_release_mouse(Button.left)
                    print(f"\nðŸ‘ï¸  Visual_click success on {event.template} at {cx},{cy}", end="")
                    break
                else:
                    if attempt < attempts - 1:
                        time.sleep(1.0) # Wait before retry
            
            if not found:
                print(f"\nâŒ Visual_click failed: could not find {event.template} after {attempts} retries")
                safety._on_emergency_stop()
                return False
                
        elif event.type == "template_find" and event.template:
            """Find a template anywhere on screen with retry logic."""
            from xiswalker.visual import VisualMatcher
            from pathlib import Path
            TEMPLATES_DIR = Path("missions") / "templates"
            matcher = VisualMatcher(TEMPLATES_DIR)
            
            attempts = event.retry if event.retry is not None else 3
            threshold = event.threshold if event.threshold is not None else 0.8
            abort_on_fail = event.abort_on_fail if event.abort_on_fail is not None else True
            
            print(f"\nðŸ” Looking for template: {event.template} (max {attempts} attempts)", end="")
            
            # Use full screen search (roi=None) or specified ROI
            roi = event.roi if event.roi else None
            
            result = matcher.find_template_with_retry(
                event.template,
                max_attempts=attempts,
                delay_between=1.0,
                roi=roi,
                threshold=threshold
            )
            
            if result.found:
                print(f" âœ“ Found at ({result.x}, {result.y}) with confidence {result.confidence:.2f}")
                # Store the found location for potential relative clicks
                # (In a more complex system, we'd store this in a variable context)
            else:
                print(f" âœ— Not found after {attempts} attempts")
                if abort_on_fail:
                    print(f"âŒ Template_find failed: aborting mission")
                    safety._on_emergency_stop()
                    return False
                else:
                    print(f"âš ï¸ Template_find failed: continuing (abort_on_fail=False)")
                    
        elif event.type == "relative_click" and event.template:
            """Find a template, then click at an offset relative to its top-left corner."""
            from xiswalker.visual import VisualMatcher
            from pathlib import Path
            TEMPLATES_DIR = Path("missions") / "templates"
            matcher = VisualMatcher(TEMPLATES_DIR)
            
            attempts = event.retry if event.retry is not None else 3
            threshold = event.threshold if event.threshold is not None else 0.8
            offset_x = event.offset_x if event.offset_x is not None else 0
            offset_y = event.offset_y if event.offset_y is not None else 0
            
            print(f"\nðŸŽ¯ Relative click on {event.template} at offset ({offset_x}, {offset_y})", end="")
            
            result = matcher.find_template_with_retry(
                event.template,
                max_attempts=attempts,
                delay_between=1.0,
                roi=event.roi,
                threshold=threshold
            )
            
            if result.found:
                # Calculate click position relative to template's top-left
                click_x, click_y = result.get_relative(offset_x, offset_y)
                
                if humanize > 0:
                    click_x = apply_mouse_jitter(click_x, 2)
                    click_y = apply_mouse_jitter(click_y, 2)
                    
                ms.position = (click_x, click_y)
                safety.safe_press_mouse(Button.left)
                if humanize > 0:
                    time.sleep(apply_humanization(0.05, humanize))
                safety.safe_release_mouse(Button.left)
                print(f" âœ“ Clicked at ({click_x}, {click_y})")
            else:
                print(f" âœ— Template not found, cannot perform relative click")
                safety._on_emergency_stop()
                return False

        elif event.type in ("mouse_click", "mouse_press", "mouse_release", "mouse_move"):
            x = event.x
            y = event.y
            
            # Handle relative coordinates (recorded relative to a template)
            if event.is_relative and event.relative_to_template and x is not None and y is not None:
                from xiswalker.visual import VisualMatcher
                from pathlib import Path
                TEMPLATES_DIR = Path("missions") / "templates"
                matcher = VisualMatcher(TEMPLATES_DIR)
                
                # Find the template to get current origin
                result = matcher.find_template_with_retry(
                    event.relative_to_template,
                    max_attempts=3,
                    delay_between=0.5,
                    roi=None,
                    threshold=0.8
                )
                
                if result.found:
                    # Convert relative offsets to absolute coordinates
                    abs_x = result.x + x
                    abs_y = result.y + y
                    
                    if humanize > 0:
                        abs_x = apply_mouse_jitter(abs_x, 2)
                        abs_y = apply_mouse_jitter(abs_y, 2)
                    
                    ms.position = (abs_x, abs_y)
                    print(f"\nðŸ“ Relative action: {event.relative_to_template} at offset ({x}, {y}) -> ({abs_x}, {abs_y})", end="")
                else:
                    print(f"\nâŒ Could not find template '{event.relative_to_template}' for relative action")
                    safety._on_emergency_stop()
                    return False
            elif x is not None and y is not None:
                # Absolute coordinates (default behavior)
                if humanize > 0:
                    x = apply_mouse_jitter(x, 2)
                    y = apply_mouse_jitter(y, 2)
                ms.position = (x, y)
            
            button = _MOUSE_BUTTONS.get(event.button or "left", Button.left)
            
            if event.type == "mouse_click":
                safety.safe_press_mouse(button)
                if humanize > 0:
                    time.sleep(apply_humanization(0.05, humanize))
                safety.safe_release_mouse(button)
            elif event.type == "mouse_press":
                safety.safe_press_mouse(button)
            elif event.type == "mouse_release":
                safety.safe_release_mouse(button)

    return True


def play_atomic(
    name: str,
    humanize: float = 0.0,
    safe_mode: bool = False,
    window_patterns: List[str] = None,
) -> None:
    """Replay an atomic mission from a JSONL file."""
    from xiswalker.recorder import countdown
    from xiswalker.safety import SafetyContext, get_foreground_window_title
    from xiswalker.config import load_config
    from colorama import Fore, Style

    cfg = load_config()
    
    if window_patterns is None:
        if cfg.safety.check_window_focus:
            window_patterns = cfg.safety.window_patterns
        else:
            window_patterns = []

    events = load_atomic(name)

    if not events:
        print(f"âš ï¸  Atomic mission '{name}' has no events.")
        return

    print(f"\n{Fore.GREEN}â–¶ï¸  Playing atomic mission: {name}{Style.RESET_ALL}")
    print(f"   Events: {len(events)}")
    print(f"   Duration: {events[-1].timestamp:.1f}s")
    print(f"   Stop key: {cfg.input.playback_stop_key.upper()}")
    
    if safe_mode:
        current_window = get_foreground_window_title() or "Unknown"
        print(f"\n{Fore.YELLOW}ðŸ›¡ï¸  Safe Mode Enabled{Style.RESET_ALL}")
        print(f"   Target Window: {current_window}")
        confirm = input("   Proceed? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("   Aborted by user.")
            return

    # Show overlay with countdown first
    from xiswalker.overlay import show_overlay, hide_overlay
    
    if cfg.input.show_overlay:
        try:
            show_overlay("playing", cfg.input.playback_stop_key, countdown=5)
        except Exception:
            pass  # Overlay is optional, don't fail if it doesn't work
    
    print()
    countdown(5)

    kb = KbController()
    ms = MouseController()
    
    from xiswalker.stats import record_execution
    import time
    start_time = time.time()
    success_flag = False

    try:
        with SafetyContext(kb, ms, stop_key=cfg.input.playback_stop_key) as safety:
            success = _play_atomic_events(
                events, safety, kb, ms, humanize, window_patterns
            )
            if success and not safety.is_aborted():
                print(f"\n{Fore.GREEN}âœ… Playback complete.{Style.RESET_ALL}")
                success_flag = True
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}âš ï¸  Playback interrupted by Ctrl+C.{Style.RESET_ALL}")
    finally:
        # Hide overlay
        if cfg.input.show_overlay:
            try:
                hide_overlay()
            except Exception:
                pass
        
        duration = time.time() - start_time
        record_execution("atomic", name, success_flag, duration)


def play_composite(
    name: str,
    humanize: float = 0.0,
    safe_mode: bool = False,
    window_patterns: List[str] = None,
    check_interrupt: Optional[Callable[[], bool]] = None,
    resume_state: Optional[object] = None,
) -> None:
    """Replay a composite mission from a YAML file."""
    from xiswalker.recorder import countdown
    from xiswalker.safety import SafetyContext, get_foreground_window_title, apply_humanization
    from xiswalker.models import parse_composite_yaml
    from xiswalker.config import load_config
    from colorama import Fore, Style
    import tqdm
    import math
    from xiswalker.stats import record_execution
    import time

    cfg = load_config()
    
    if window_patterns is None:
        if cfg.safety.check_window_focus:
            window_patterns = cfg.safety.window_patterns
        else:
            window_patterns = []

    filepath = COMPOSITE_DIR / f"{name}.yaml"
    if not filepath.exists():
        print(f"{Fore.RED}âŒ Composite mission not found: {filepath}{Style.RESET_ALL}")
        return

    mission = parse_composite_yaml(filepath)
    print(f"\n{Fore.GREEN}â–¶ï¸  Playing composite mission: {mission.name}{Style.RESET_ALL}")
    print(f"   Steps: {len(mission.steps)}")
    print(f"   Stop key: {cfg.input.playback_stop_key.upper()}")

    if safe_mode:
        current_window = get_foreground_window_title() or "Unknown"
        print(f"\n{Fore.YELLOW}ðŸ›¡ï¸  Safe Mode Enabled{Style.RESET_ALL}")
        print(f"   Target Window: {current_window}")
        confirm = input("   Proceed? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("   Aborted by user.")
            return

    # Show overlay with countdown first
    from xiswalker.overlay import show_overlay, hide_overlay
    
    grace = mission.grace_period if mission.grace_period > 0 else 5
    if cfg.input.show_overlay:
        try:
            show_overlay("playing", cfg.input.playback_stop_key, countdown=grace)
        except Exception:
            pass
    
    print()
    if mission.grace_period > 0 and resume_state is None:
        countdown(mission.grace_period)

    kb = KbController()
    ms = MouseController()

    # Import overlay here to avoid circular imports
    from xiswalker.overlay import show_overlay, hide_overlay
    
    # Show overlay if enabled
    if cfg.input.show_overlay:
        try:
            show_overlay("playing", cfg.input.playback_stop_key)
        except Exception:
            pass  # Overlay is optional, don't fail if it doesn't work

    start_time = time.time()
    success_flag = False

    try:
        with SafetyContext(kb, ms, stop_key=cfg.input.playback_stop_key) as safety:
            for idx, step in enumerate(mission.steps):
                i = idx + 1  # 1-based display index
                # Skip already-completed steps when resuming from a preemption point
                if resume_state is not None and idx < resume_state.step_index:
                    continue
                if safety.is_aborted():
                    break

                # Build a short label for the overlay
                if step.wait is not None:
                    _step_label = f"Wait {step.wait}s"
                elif step.mission:
                    _step_label = f"Atomic: {step.mission}"
                elif step.visual_condition:
                    _step_label = f"Visual: {step.visual_condition}"
                elif step.ocr_text:
                    _step_label = f"OCR: {step.ocr_text}"
                elif step.ocr_timer:
                    _step_label = "Timer OCR"
                else:
                    _step_label = ""
                try:
                    from xiswalker.overlay import update_step_overlay
                    update_step_overlay(i, len(mission.steps), _step_label)
                except Exception:
                    pass
                    
                print(f"\nâ³ Step {i}/{len(mission.steps)}", end="")
                
                # Check for wait step
                if step.wait is not None:
                    wait_time = step.wait
                    # Override with remaining time if resuming at this specific step
                    if resume_state is not None and idx == resume_state.step_index:
                        wait_time = resume_state.remaining_seconds
                    print(f" - Waiting {wait_time:.1f}s")
                    
                    if humanize > 0:
                        wait_time = apply_humanization(wait_time, humanize)
                        
                    total_steps = math.ceil(wait_time / 0.05)
                    with tqdm.tqdm(total=total_steps, desc=f"Wait {wait_time:.1f}s", leave=False, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
                        while wait_time > 0 and not safety.is_aborted():
                            sleep_time = min(0.05, wait_time)
                            if not safety.verify_window_focus(window_patterns):
                                print(f"\n{Fore.RED}âŒ Window focus lost during composite wait! Aborting.{Style.RESET_ALL}")
                                safety._on_emergency_stop()
                                break
                                    
                            time.sleep(sleep_time)
                            wait_time -= sleep_time
                            pbar.update(1)
                            # Preemption check: yield to INTERRUPT mission at next safe tick
                            if check_interrupt is not None and check_interrupt():
                                from xiswalker.executor import PreemptSignal
                                raise PreemptSignal(idx, wait_time)
                    continue

                if step.mission:
                    print(f" - Atomic: {step.mission}")
                    try:
                        events = load_atomic(step.mission)
                    except FileNotFoundError:
                        events = None
                        
                    if not events:
                        print(f"âš ï¸  Missing or empty atomic mission '{step.mission}'")
                        if step.on_fail == "abort":
                            safety._on_emergency_stop()
                            break
                        elif step.on_fail == "skip":
                            continue
                            
                    step_hum = step.humanization_override if step.humanization_override is not None else humanize
                    
                    attempts = step.retries + 1
                    success = False
                    
                    for attempt in range(attempts):
                        if safety.is_aborted():
                            break
                        if attempt > 0:
                            print(f"   â†» Retry {attempt}/{step.retries}")
                            
                        success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                        
                        if success:
                            break
                            
                    if not success and not safety.is_aborted():
                        print(f"{Fore.RED}âŒ Step failed.{Style.RESET_ALL}")
                        if step.on_fail == "abort":
                            safety._on_emergency_stop()
                            break
                            
                # Handle visual condition steps
                elif step.visual_condition:
                    print(f" - Visual: {step.visual_condition}")
                    
                    from xiswalker.visual import VisualMatcher
                    TEMPLATES_DIR = Path("missions") / "templates"
                    matcher = VisualMatcher(TEMPLATES_DIR)
                    
                    threshold = step.visual_threshold if step.visual_threshold is not None else 0.8
                    timeout = step.visual_timeout if step.visual_timeout is not None else 5.0
                    
                    print(f"   Looking for template (threshold={threshold}, timeout={timeout}s)...", end="")
                    
                    # Try to find template
                    import time
                    start_search = time.time()
                    result = None
                    
                    while time.time() - start_search < timeout:
                        if safety.is_aborted():
                            break
                        
                        result = matcher.find_template(
                            step.visual_condition,
                            roi=None,
                            threshold=threshold
                        )
                        
                        if result.found:
                            break
                            
                        time.sleep(0.5)  # Check every 500ms
                    
                    if result and result.found:
                        print(f" âœ“ Found at ({result.x}, {result.y})")
                        
                        # If on_found atomic specified, run it with offset
                        if step.on_found:
                            try:
                                events = load_atomic(step.on_found)
                                if events:
                                    # Calculate offset if visual_click_x/y specified
                                    offset_x = step.visual_click_x if step.visual_click_x is not None else 0
                                    offset_y = step.visual_click_y if step.visual_click_y is not None else 0
                                    
                                    # Apply offset to all mouse events
                                    abs_x = result.x + offset_x
                                    abs_y = result.y + offset_y
                                    
                                    print(f"   Executing '{step.on_found}' at ({abs_x}, {abs_y})")
                                    
                                    # Temporarily move mouse to position (first event will use this)
                                    if events and events[0].x is not None:
                                        ms.position = (abs_x, abs_y)
                                    
                                    step_hum = step.humanization_override if step.humanization_override is not None else humanize
                                    success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                                    
                                    if not success and step.on_fail == "abort":
                                        safety._on_emergency_stop()
                                        break
                            except FileNotFoundError:
                                print(f" âš ï¸ Atomic mission '{step.on_found}' not found")
                        else:
                            # Click at the specified point (left / double / right)
                            offset_x = step.visual_click_x if step.visual_click_x is not None else 0
                            offset_y = step.visual_click_y if step.visual_click_y is not None else 0

                            click_x = result.x + offset_x
                            click_y = result.y + offset_y

                            click_type = step.visual_click_type or "left"
                            ms.position = (click_x, click_y)

                            if click_type == "right":
                                print(f"   Right-clicking at ({click_x}, {click_y})")
                                safety.safe_press_mouse(Button.right)
                                time.sleep(0.05)
                                safety.safe_release_mouse(Button.right)
                            elif click_type == "double":
                                print(f"   Double-clicking at ({click_x}, {click_y})")
                                safety.safe_press_mouse(Button.left)
                                time.sleep(0.05)
                                safety.safe_release_mouse(Button.left)
                                time.sleep(0.08)
                                safety.safe_press_mouse(Button.left)
                                time.sleep(0.05)
                                safety.safe_release_mouse(Button.left)
                            else:
                                print(f"   Clicking at ({click_x}, {click_y})")
                                safety.safe_press_mouse(Button.left)
                                time.sleep(0.05)
                                safety.safe_release_mouse(Button.left)
                    else:
                        print(f" âœ— Not found")
                        
                        # If on_not_found atomic specified, run it
                        if step.on_not_found:
                            try:
                                events = load_atomic(step.on_not_found)
                                if events:
                                    print(f"   Executing '{step.on_not_found}' (not found path)")
                                    step_hum = step.humanization_override if step.humanization_override is not None else humanize
                                    success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                                    
                                    if not success and step.on_fail == "abort":
                                        safety._on_emergency_stop()
                                        break
                            except FileNotFoundError:
                                print(f" âš ï¸ Atomic mission '{step.on_not_found}' not found")
                        elif step.on_fail == "abort":
                            print(f"{Fore.RED}âŒ Visual condition failed and on_fail=abort{Style.RESET_ALL}")
                            safety._on_emergency_stop()
                            break
                        elif step.on_fail == "skip":
                            print(f"   Skipping step (on_fail=skip)")
                            continue

                # Handle OCR text condition steps
                elif step.ocr_text:
                    print(f" - OCR: '{step.ocr_text}'")

                    import time as _time
                    from xiswalker.ocr import OcrMatcher

                    ollama_url = cfg.ocr.ollama_url
                    backend = step.ocr_backend or cfg.ocr.backend
                    model = step.ocr_model or cfg.ocr.ollama_model
                    threshold = step.ocr_threshold if step.ocr_threshold is not None else 0.8
                    timeout = step.ocr_timeout if step.ocr_timeout is not None else 5.0
                    case_sensitive = step.ocr_case_sensitive if step.ocr_case_sensitive is not None else False

                    print(
                        f"   Searching via {backend} (threshold={threshold}, timeout={timeout}s)...",
                        end="",
                    )

                    matcher = OcrMatcher(ollama_url=ollama_url)
                    ocr_result = matcher.find_text(
                        target=step.ocr_text,
                        roi=step.ocr_roi,
                        threshold=threshold,
                        timeout=timeout,
                        backend=backend,
                        model=model,
                        case_sensitive=case_sensitive,
                    )

                    if ocr_result.found:
                        print(f" âœ“ Found at ({ocr_result.x}, {ocr_result.y})")

                        if step.on_found:
                            try:
                                events = load_atomic(step.on_found)
                                if events:
                                    offset_x = step.visual_click_x if step.visual_click_x is not None else 0
                                    offset_y = step.visual_click_y if step.visual_click_y is not None else 0
                                    abs_x = ocr_result.x + offset_x
                                    abs_y = ocr_result.y + offset_y
                                    print(f"   Executing '{step.on_found}' at ({abs_x}, {abs_y})")
                                    if events[0].x is not None:
                                        ms.position = (abs_x, abs_y)
                                    step_hum = step.humanization_override if step.humanization_override is not None else humanize
                                    success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                                    if not success and step.on_fail == "abort":
                                        safety._on_emergency_stop()
                                        break
                            except FileNotFoundError:
                                print(f" âš ï¸ Atomic mission '{step.on_found}' not found")
                        else:
                            # Default: click center of found text + optional offset
                            offset_x = step.visual_click_x if step.visual_click_x is not None else (ocr_result.w // 2)
                            offset_y = step.visual_click_y if step.visual_click_y is not None else (ocr_result.h // 2)
                            click_x = ocr_result.x + offset_x
                            click_y = ocr_result.y + offset_y
                            print(f"   Clicking at ({click_x}, {click_y})")
                            ms.position = (click_x, click_y)
                            safety.safe_press_mouse(Button.left)
                            _time.sleep(0.05)
                            safety.safe_release_mouse(Button.left)
                    else:
                        print(f" âœ— Text not found")

                        if step.on_not_found:
                            try:
                                events = load_atomic(step.on_not_found)
                                if events:
                                    print(f"   Executing '{step.on_not_found}' (not found path)")
                                    step_hum = step.humanization_override if step.humanization_override is not None else humanize
                                    success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                                    if not success and step.on_fail == "abort":
                                        safety._on_emergency_stop()
                                        break
                            except FileNotFoundError:
                                print(f" âš ï¸ Atomic mission '{step.on_not_found}' not found")
                        elif step.on_fail == "abort":
                            print(f"{Fore.RED}âŒ OCR condition failed and on_fail=abort{Style.RESET_ALL}")
                            safety._on_emergency_stop()
                            break
                        else:
                            print(f"   Skipping step (on_fail=skip)")

                # Handle OCR timer steps â€” read a timer from screen and wait
                elif step.ocr_timer:
                    import time as _time
                    from xiswalker.ocr import OcrMatcher
                    from xiswalker.timer_parser import extract_timer_seconds, format_seconds

                    backend = step.ocr_backend or cfg.ocr.backend
                    model = step.ocr_model or cfg.ocr.ollama_model
                    matcher = OcrMatcher(ollama_url=cfg.ocr.ollama_url)
                    recheck_delay = step.timer_loop_recheck_delay if step.timer_loop_recheck_delay is not None else 10.0
                    pre_scan_delay = step.ocr_timer_pre_scan_delay if step.ocr_timer_pre_scan_delay else 0.0
                    loop_active = True
                    first_run = True
                    # If resuming at this step, skip OCR scan and use saved remaining time
                    _resume_seconds: Optional[float] = None
                    if resume_state is not None and idx == resume_state.step_index:
                        _resume_seconds = resume_state.remaining_seconds

                    while loop_active and not safety.is_aborted():
                        if _resume_seconds is not None:
                            # Resume path: skip scan, jump straight to countdown
                            wait_seconds = _resume_seconds
                            _resume_seconds = None
                        else:
                            # Normal path: optional pre-scan delay, then OCR scan
                            if first_run and pre_scan_delay > 0:
                                print(f"   [Timer OCR] Waiting {pre_scan_delay:.0f}s before first scan...")
                                elapsed = 0.0
                                while elapsed < pre_scan_delay and not safety.is_aborted():
                                    _time.sleep(1.0)
                                    elapsed += 1.0
                            elif not first_run:
                                print(f"   [Timer OCR] Waiting {recheck_delay:.0f}s before re-scanning...")
                                elapsed = 0.0
                                while elapsed < recheck_delay and not safety.is_aborted():
                                    _time.sleep(1.0)
                                    elapsed += 1.0
                            first_run = False

                            print(f"   [Timer OCR] Scanning region {step.ocr_roi} via {backend}...")
                            blob = matcher.read_all_text(roi=step.ocr_roi, backend=backend, model=model)
                            raw_preview = blob[:80].strip().replace("\n", " ")
                            print(f"   [Timer OCR] Raw text: '{raw_preview}'")

                            wait_seconds = extract_timer_seconds(blob)

                            if wait_seconds is None:
                                print(f"   [Timer OCR] No timer pattern found in OCR output.")
                                if step.on_fail == "abort":
                                    safety._on_emergency_stop()
                                loop_active = False
                                break

                        print(f"   [Timer OCR] Detected: {format_seconds(wait_seconds)} ({wait_seconds}s) â€” starting countdown...")

                        # Interruptible wait with periodic log every 60s
                        elapsed = 0
                        next_log = min(60, wait_seconds)
                        while elapsed < wait_seconds:
                            if safety.is_aborted():
                                loop_active = False
                                break
                            _time.sleep(1.0)
                            elapsed += 1
                            # Preemption check: yield to INTERRUPT mission at next safe tick
                            if check_interrupt is not None and check_interrupt():
                                from xiswalker.executor import PreemptSignal
                                raise PreemptSignal(idx, float(wait_seconds - elapsed))
                            if elapsed >= next_log and elapsed < wait_seconds:
                                remaining = wait_seconds - elapsed
                                print(f"   [Timer OCR] Countdown: {format_seconds(remaining)} remaining...")
                                next_log += 60

                        if safety.is_aborted():
                            break

                        print(f"   [Timer OCR] Timer expired â€” executing on-expire action...")
                        # Run on_expire mission if specified
                        if step.timer_on_expire:
                            on_expire = step.timer_on_expire
                            step_hum = step.humanization_override if step.humanization_override is not None else humanize
                            if on_expire.startswith("composite:"):
                                comp_name = on_expire[len("composite:"):]
                                print(f"   [Timer OCR] Running composite '{comp_name}'")
                                play_composite(comp_name, humanize=step_hum,
                                               window_patterns=window_patterns)
                            else:
                                # "atomic:name" or legacy bare name
                                atom_name = on_expire[len("atomic:"):] if on_expire.startswith("atomic:") else on_expire
                                try:
                                    events = load_atomic(atom_name)
                                    if events:
                                        print(f"   [Timer OCR] Executing atomic '{atom_name}'")
                                        success = _play_atomic_events(events, safety, kb, ms, step_hum, window_patterns)
                                        if not success and step.on_fail == "abort":
                                            safety._on_emergency_stop()
                                            loop_active = False
                                except FileNotFoundError:
                                    print(f"   [Timer OCR] âš  Atomic '{atom_name}' not found")
                                    loop_active = False
                        else:
                            print(f"   [Timer OCR] No on-expire action configured.")

                        if not step.timer_loop:
                            loop_active = False
                        else:
                            print(f"   [Timer OCR] Loop enabled â€” will re-scan after delay.")

            if not safety.is_aborted():
                print(f"\n{Fore.GREEN}âœ… Composite playback complete.{Style.RESET_ALL}")
                success_flag = True

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}âš ï¸  Playback interrupted by Ctrl+C.{Style.RESET_ALL}")
    finally:
        # Hide overlay
        if cfg.input.show_overlay:
            try:
                hide_overlay()
            except Exception:
                pass
            
        duration = time.time() - start_time
        record_execution("composite", name, success_flag, duration)
