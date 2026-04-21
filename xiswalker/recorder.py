"""Recorder module — captures keyboard and mouse input to JSONL."""

import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from pynput import keyboard, mouse

from xiswalker.models import InputEvent, serialize_event
from xiswalker.config import load_config


MISSIONS_DIR = Path("missions")
ATOMIC_DIR = MISSIONS_DIR / "atomic"
TEMPLATES_DIR = MISSIONS_DIR / "templates"


def _parse_stop_key(key_str: str) -> keyboard.Key:
    """Parse a stop key string into a pynput Key.
    
    Args:
        key_str: Key name like "esc", "f1", "f12", etc.
        
    Returns:
        The corresponding pynput Key
    """
    key_str = key_str.lower().strip()
    
    # Map common key names
    key_map = {
        'esc': keyboard.Key.esc,
        'escape': keyboard.Key.esc,
        'f1': keyboard.Key.f1, 'f2': keyboard.Key.f2,
        'f3': keyboard.Key.f3, 'f4': keyboard.Key.f4,
        'f5': keyboard.Key.f5, 'f6': keyboard.Key.f6,
        'f7': keyboard.Key.f7, 'f8': keyboard.Key.f8,
        'f9': keyboard.Key.f9, 'f10': keyboard.Key.f10,
        'f11': keyboard.Key.f11, 'f12': keyboard.Key.f12,
        'end': keyboard.Key.end,
        'home': keyboard.Key.home,
        'insert': keyboard.Key.insert,
        'delete': keyboard.Key.delete,
        'pageup': keyboard.Key.page_up,
        'pagedown': keyboard.Key.page_down,
        'space': keyboard.Key.space,
        'tab': keyboard.Key.tab,
        'enter': keyboard.Key.enter,
        'return': keyboard.Key.enter,
        'backspace': keyboard.Key.backspace,
    }
    
    if key_str in key_map:
        return key_map[key_str]
    
    # Try to get from keyboard.Key enum
    try:
        return getattr(keyboard.Key, key_str)
    except AttributeError:
        pass
    
    # Default to ESC if unknown
    return keyboard.Key.esc


def countdown(seconds: int = 5) -> None:
    """Print a countdown before recording/playback starts.

    Args:
        seconds: Number of seconds to count down.
    """
    for i in range(seconds, 0, -1):
        print(f"  {i}...", flush=True)
        time.sleep(1)
    print("  GO!", flush=True)


def capture_template(name: str) -> None:
    """Interactively capture a screen region and save as template."""
    from xiswalker.visual import VisualMatcher
    import cv2
    
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📸 Capturing template: {name}")
    print("   Please left-click and drag to select the region.")
    
    start_pos = None
    end_pos = None
    
    def on_click(x, y, button, pressed):
        nonlocal start_pos, end_pos
        if button == mouse.Button.left:
            if pressed:
                start_pos = (x, y)
                print(f"   Start: {start_pos}...", end="\r")
            else:
                end_pos = (x, y)
                print(f"   Start: {start_pos} -> End: {end_pos}")
                return False  # stop listener
                
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
        
    if start_pos and end_pos:
        x1, int_y1 = start_pos
        x2, int_y2 = end_pos
        x = int(min(x1, x2))
        y = int(min(int_y1, int_y2))
        w = int(abs(x2 - x1))
        h = int(abs(int_y2 - int_y1))
        
        if w < 5 or h < 5:
            print("❌ Region too small.")
            return
            
        roi = [x, y, w, h]
        matcher = VisualMatcher(TEMPLATES_DIR)
        img = matcher.capture_roi(roi)
        
        template_path = TEMPLATES_DIR / f"{name}.png"
        cv2.imwrite(str(template_path), img)
        print(f"✅ Saved template to {template_path} (ROI: {roi})")


def record_mission(name: str, visual: bool = False) -> None:
    """Record keyboard and mouse input to a JSONL atomic mission file.

    Captures key presses, key releases, and mouse clicks with relative
    timestamps. Press the configured stop key to stop recording.

    Args:
        name: Mission name (used as filename without extension).
        visual: Whether to enable F8 visual checkpoints.
    """
    # Load configuration
    cfg = load_config()
    stop_key_str = cfg.input.recording_stop_key
    stop_key = _parse_stop_key(stop_key_str)
    
    # Import overlay here to avoid circular imports
    from xiswalker.overlay import show_overlay, hide_overlay
    
    ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ATOMIC_DIR / f"{name}.jsonl"

    events: List[InputEvent] = []
    start_time: float = 0.0
    stop_event = False
    
    # Track held mouse buttons to only record mouse_move when dragging
    held_mouse_buttons = set()
    
    # Track if shift is currently held
    _shift_held = False
    
    def _key_to_str(key: keyboard.Key | keyboard.KeyCode, is_shifted: bool = False) -> str:
        """Convert a pynput key to a string representation.
        
        If is_shifted is True, stores VK code for proper cross-keyboard playback.
        """
        if isinstance(key, keyboard.KeyCode):
            if key.char is not None:
                # If this key was typed with shift held, store VK code
                # This ensures proper playback on different keyboard layouts
                if is_shifted and key.vk is not None:
                    return f"<{key.vk}>"
                return key.char
            # Special key with vk code but no char (e.g. numpad)
            return f"<{key.vk}>"
        return key.name
    
    def _update_modifier_state(key, is_press: bool):
        """Track shift key state."""
        nonlocal _shift_held
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            _shift_held = is_press

    def on_key_press(key: keyboard.Key | keyboard.KeyCode) -> None:
        nonlocal stop_event
        
        # Track shift state
        _update_modifier_state(key, True)
        
        # Configured stop key stops recording
        if key == stop_key:
            stop_event = True
            return
            
        if visual and key == keyboard.Key.f8:
            # Capture visual checkpoint
            from xiswalker.visual import VisualMatcher
            import cv2
            
            ms_controller = mouse.Controller()
            cx, cy = ms_controller.position
            # Capture 50x50 region around mouse
            roi = [int(cx - 25), int(cy - 25), 50, 50]
            
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            template_name = f"{name}_auto_{int(time.time())}.png"
            template_path = TEMPLATES_DIR / template_name
            
            matcher = VisualMatcher(TEMPLATES_DIR)
            img = matcher.capture_roi(roi)
            cv2.imwrite(str(template_path), img)
            
            event = InputEvent(
                type="visual_click",
                timestamp=time.time() - start_time,
                template=template_name,
                roi=roi,
                threshold=0.8,
                retry=3
            )
            events.append(event)
            print(f"📸 Captured visual checkpoint: {template_name} at {cx},{cy}")
            return

        event = InputEvent(
            type="key_press",
            timestamp=time.time() - start_time,
            key=_key_to_str(key, is_shifted=_shift_held),
        )
        events.append(event)

    def on_key_release(key: keyboard.Key | keyboard.KeyCode) -> None:
        # Track shift release before checking stop_event
        _update_modifier_state(key, False)
        
        if stop_event:
            return

        # Don't record stop key release
        if key == stop_key:
            return

        event = InputEvent(
            type="key_release",
            timestamp=time.time() - start_time,
            key=_key_to_str(key, is_shifted=_shift_held),
        )
        events.append(event)

    def on_click(
        x: int, y: int, button: mouse.Button, pressed: bool
    ) -> None:
        if stop_event:
            return
            
        if pressed:
            held_mouse_buttons.add(button)
            event_type = "mouse_press"
        else:
            held_mouse_buttons.discard(button)
            event_type = "mouse_release"

        event = InputEvent(
            type=event_type,
            timestamp=time.time() - start_time,
            x=x,
            y=y,
            button=button.name,
        )
        events.append(event)
        
    def on_move(x: int, y: int) -> None:
        if stop_event:
            return
            
        # Only record mouse movements if actively dragging (a button is held)
        if not held_mouse_buttons:
            return
            
        event = InputEvent(
            type="mouse_move",
            timestamp=time.time() - start_time,
            x=x,
            y=y,
        )
        events.append(event)

    print(f"\n🎙️  Recording mission: {name}")
    print(f"   Output: {filepath}")
    print(f"   Press {stop_key_str.upper()} to stop recording.\n")
    
    # Show overlay with countdown first
    if cfg.input.show_overlay:
        try:
            show_overlay("recording", stop_key_str, countdown=5)
        except Exception:
            pass  # Overlay is optional, don't fail if it doesn't work
    
    countdown(5)

    start_time = time.time()

    kb_listener = keyboard.Listener(
        on_press=on_key_press, on_release=on_key_release
    )
    mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)

    kb_listener.start()
    mouse_listener.start()

    try:
        while not stop_event:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n⚠️  Recording interrupted by Ctrl+C.")
    finally:
        kb_listener.stop()
        mouse_listener.stop()
        kb_listener.join()
        mouse_listener.join()
        
        # Hide overlay
        if cfg.input.show_overlay:
            try:
                hide_overlay()
            except Exception:
                pass

    # Write events to file
    with open(filepath, "w", encoding="utf-8") as f:
        for event in events:
            f.write(serialize_event(event) + "\n")

    print(f"\n✅ Recorded {len(events)} events to {filepath}")


def record_relative_mission(name: str, template_name: str, visual: bool = False) -> None:
    """Record keyboard and mouse input relative to a template's position.
    
    This allows recorded mouse coordinates to be playback-correct even if the
    template moves to a different screen location. All mouse coordinates are
    stored as offsets from the template's top-left corner.
    
    Args:
        name: Mission name (used as filename without extension).
        template_name: Name of the template file to record relative to.
        visual: Whether to enable F8 visual checkpoints.
    """
    from xiswalker.visual import VisualMatcher
    
    # Load configuration
    cfg = load_config()
    stop_key_str = cfg.input.recording_stop_key
    stop_key = _parse_stop_key(stop_key_str)
    
    # Import overlay here to avoid circular imports
    from xiswalker.overlay import show_overlay, hide_overlay
    
    ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ATOMIC_DIR / f"{name}.jsonl"
    
    # First, find the template to establish the origin point
    print(f"\n🔍 Locating template '{template_name}' to establish origin...")
    matcher = VisualMatcher(TEMPLATES_DIR)
    
    # Try to find template with retries
    result = matcher.find_template_with_retry(
        template_name,
        max_attempts=3,
        delay_between=1.0,
        roi=None,  # Full screen search
        threshold=0.8
    )
    
    if not result.found:
        print(f"❌ Could not find template '{template_name}' on screen.")
        print("   Falling back to absolute coordinate recording.")
        origin_x, origin_y = 0, 0
        is_relative_mode = False
    else:
        origin_x, origin_y = result.x, result.y
        is_relative_mode = True
        print(f"✅ Template found at ({origin_x}, {origin_y})")
        print(f"   All mouse coordinates will be recorded relative to this point.")
    
    events: List[InputEvent] = []
    start_time: float = 0.0
    stop_event = False
    
    # Track held mouse buttons to only record mouse_move when dragging
    held_mouse_buttons = set()

    # Track if shift is currently held
    _shift_held = False
    
    def _key_to_str(key: keyboard.Key | keyboard.KeyCode, is_shifted: bool = False) -> str:
        """Convert a pynput key to a string representation."""
        if isinstance(key, keyboard.KeyCode):
            if key.char is not None:
                # If this key was typed with shift held, store VK code
                if is_shifted and key.vk is not None:
                    return f"<{key.vk}>"
                return key.char
            return f"<{key.vk}>"
        return key.name
    
    def _update_modifier_state(key, is_press: bool):
        """Track shift key state."""
        nonlocal _shift_held
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            _shift_held = is_press

    def on_key_press(key: keyboard.Key | keyboard.KeyCode) -> None:
        nonlocal stop_event
        
        # Track shift state
        _update_modifier_state(key, True)
        
        if key == stop_key:
            stop_event = True
            return
            
        if visual and key == keyboard.Key.f8:
            # Capture visual checkpoint (absolute, not relative)
            from xiswalker.visual import VisualMatcher
            import cv2
            
            ms_controller = mouse.Controller()
            cx, cy = ms_controller.position
            roi = [int(cx - 25), int(cy - 25), 50, 50]
            
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            checkpoint_name = f"{name}_auto_{int(time.time())}.png"
            template_path = TEMPLATES_DIR / checkpoint_name
            
            matcher = VisualMatcher(TEMPLATES_DIR)
            img = matcher.capture_roi(roi)
            cv2.imwrite(str(template_path), img)
            
            event = InputEvent(
                type="visual_click",
                timestamp=time.time() - start_time,
                template=checkpoint_name,
                roi=roi,
                threshold=0.8,
                retry=3
            )
            events.append(event)
            print(f"📸 Captured visual checkpoint: {checkpoint_name} at {cx},{cy}")
            return

        event = InputEvent(
            type="key_press",
            timestamp=time.time() - start_time,
            key=_key_to_str(key, is_shifted=_shift_held),
        )
        events.append(event)

    def on_key_release(key: keyboard.Key | keyboard.KeyCode) -> None:
        # Track shift release before checking stop_event
        _update_modifier_state(key, False)
        
        if stop_event:
            return

        if key == stop_key:
            return

        event = InputEvent(
            type="key_release",
            timestamp=time.time() - start_time,
            key=_key_to_str(key, is_shifted=_shift_held),
        )
        events.append(event)

    def on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if stop_event:
            return
            
        if pressed:
            held_mouse_buttons.add(button)
            event_type = "mouse_press"
        else:
            held_mouse_buttons.discard(button)
            event_type = "mouse_release"

        # Store relative coordinates if in relative mode
        if is_relative_mode:
            rel_x = x - origin_x
            rel_y = y - origin_y
            event = InputEvent(
                type=event_type,
                timestamp=time.time() - start_time,
                x=rel_x,
                y=rel_y,
                button=button.name,
                relative_to_template=template_name,
                is_relative=True
            )
        else:
            event = InputEvent(
                type=event_type,
                timestamp=time.time() - start_time,
                x=x,
                y=y,
                button=button.name,
            )
        events.append(event)
        
    def on_move(x: int, y: int) -> None:
        if stop_event:
            return
            
        # Only record mouse movements if actively dragging
        if not held_mouse_buttons:
            return
            
        # Store relative coordinates if in relative mode
        if is_relative_mode:
            rel_x = x - origin_x
            rel_y = y - origin_y
            event = InputEvent(
                type="mouse_move",
                timestamp=time.time() - start_time,
                x=rel_x,
                y=rel_y,
                relative_to_template=template_name,
                is_relative=True
            )
        else:
            event = InputEvent(
                type="mouse_move",
                timestamp=time.time() - start_time,
                x=x,
                y=y,
            )
        events.append(event)

    print(f"\n🎙️  Recording RELATIVE mission: {name}")
    print(f"   Template: {template_name}")
    print(f"   Origin: ({origin_x}, {origin_y})")
    print(f"   Output: {filepath}")
    print(f"   Press {stop_key_str.upper()} to stop recording.\n")
    
    # Show overlay with countdown first
    if cfg.input.show_overlay:
        try:
            show_overlay("recording", stop_key_str, countdown=5)
        except Exception:
            pass
    
    countdown(5)

    start_time = time.time()

    kb_listener = keyboard.Listener(
        on_press=on_key_press, on_release=on_key_release
    )
    mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)

    kb_listener.start()
    mouse_listener.start()

    try:
        while not stop_event:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n⚠️  Recording interrupted by Ctrl+C.")
    finally:
        kb_listener.stop()
        mouse_listener.stop()
        kb_listener.join()
        mouse_listener.join()
        
        # Hide overlay
        if cfg.input.show_overlay:
            try:
                hide_overlay()
            except Exception:
                pass

    # Write events to file
    with open(filepath, "w", encoding="utf-8") as f:
        for event in events:
            f.write(serialize_event(event) + "\n")

    rel_count = sum(1 for e in events if e.is_relative)
    print(f"\n✅ Recorded {len(events)} events ({rel_count} relative) to {filepath}")
