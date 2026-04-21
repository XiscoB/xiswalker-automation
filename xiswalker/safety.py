"""Safety layer for XisWalker — window focus, emergency stops, and humanization."""

import logging
import random
import threading
from typing import List, Set, Optional, Callable

from pynput import keyboard, mouse

# We wrap win32 imports so they don't break on non-Windows platforms during tests,
# although the roadmap specifies Windows as primary target.
try:
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


logger = logging.getLogger(__name__)

# Module-level event that MCP's stop_execution() (and emergency stop) can trigger
# to abort any currently running SafetyContext across threads.
_GLOBAL_STOP_EVENT: threading.Event = threading.Event()


def trigger_global_stop() -> None:
    """Signal all running SafetyContexts to abort immediately."""
    _GLOBAL_STOP_EVENT.set()


def is_global_stop_active() -> bool:
    """Return True if the global stop event is currently set."""
    return _GLOBAL_STOP_EVENT.is_set()


def parse_key_combo(combo_str: str) -> Callable:
    """Parse a key combination string into a pynput GlobalHotKeys compatible format.
    
    Args:
        combo_str: Key combination like "ctrl+shift+end" or "esc"
        
    Returns:
        A callable that can be used with GlobalHotKeys
    """
    parts = combo_str.lower().split('+')
    
    # Map common key names to pynput format
    key_map = {
        'ctrl': '<ctrl>',
        'alt': '<alt>',
        'shift': '<shift>',
        'cmd': '<cmd>',
        'win': '<cmd>',
        'esc': '<esc>',
        'escape': '<esc>',
        'end': '<end>',
        'home': '<home>',
        'insert': '<insert>',
        'delete': '<delete>',
        'del': '<delete>',
        'pageup': '<page_up>',
        'pagedown': '<page_down>',
        'up': '<up>',
        'down': '<down>',
        'left': '<left>',
        'right': '<right>',
        'space': '<space>',
        'tab': '<tab>',
        'enter': '<enter>',
        'return': '<enter>',
        'backspace': '<backspace>',
        'f1': '<f1>', 'f2': '<f2>', 'f3': '<f3>', 'f4': '<f4>',
        'f5': '<f5>', 'f6': '<f6>', 'f7': '<f7>', 'f8': '<f8>',
        'f9': '<f9>', 'f10': '<f10>', 'f11': '<f11>', 'f12': '<f12>',
    }
    
    formatted_parts = []
    for part in parts:
        part = part.strip()
        if part in key_map:
            formatted_parts.append(key_map[part])
        elif len(part) == 1:
            # Single character key
            formatted_parts.append(part)
        else:
            # Try as-is (for other special keys)
            formatted_parts.append(f'<{part}>')
    
    return '+'.join(formatted_parts)


def match_window_title(title: str, patterns: List[str]) -> bool:
    """Check if a window title matches any of the given patterns (case-insensitive).
    
    Args:
        title: The actual window title.
        patterns: List of acceptable substrings.

    Returns:
        True if any pattern is found in the title.
    """
    title_lower = title.lower()
    return any(p.lower() in title_lower for p in patterns)


def get_foreground_window_title() -> str:
    """Get the title of the currently focused window.
    
    Returns:
        The window title, or an empty string if it cannot be determined.
    """
    if not WIN32_AVAILABLE:
        return ""
    
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            return win32gui.GetWindowText(hwnd)
    except Exception as e:
        logger.warning(f"Failed to get foreground window: {e}")
    return ""


def apply_humanization(delay: float, variance: float) -> float:
    """Apply humanization variance to a time delay using Gaussian distribution.
    
    Args:
        delay: Original delay in seconds.
        variance: Maximum variance percentage (e.g., 0.05 for 5%).
        
    Returns:
        New delay with variance applied. Never returns negative.
    """
    if variance <= 0.0:
        return max(0.0, delay)
        
    # Standard deviation is roughly a third of the max variance
    # to keep 99.7% of values within the variance range.
    sigma = delay * variance / 3.0
    jitter = random.gauss(0, sigma)
    
    # Cap the jitter to the hard variance limits
    max_jitter = delay * variance
    jitter = max(-max_jitter, min(jitter, max_jitter))
    
    return max(0.0, delay + jitter)


def apply_mouse_jitter(val: int, variance: int) -> int:
    """Apply pixel jitter to a mouse coordinate.
    
    Args:
        val: The original coordinate.
        variance: Maximum pixel variance (+/-).
        
    Returns:
        Jittered coordinate.
    """
    if variance <= 0:
        return val
    return val + random.randint(-variance, variance)


class SafetyContext:
    """Context manager and tracker for safe input execution.
    
    Tracks held keys to guarantee they are released on exit/crash.
    Provides emergency stop functionality via a global hotkey.
    """
    
    def __init__(
        self,
        kb_controller: keyboard.Controller,
        ms_controller: mouse.Controller,
        stop_key: str = "ctrl+shift+end"
    ):
        self.kb = kb_controller
        self.ms = ms_controller
        self.held_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        self.held_buttons: set[mouse.Button] = set()
        self._stop_key = stop_key
        
        self._aborted = False
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def __enter__(self):
        # Start the global hotkey listener for emergency stop
        hotkey_str = parse_key_combo(self._stop_key)
        self._listener = keyboard.GlobalHotKeys({
            hotkey_str: self._on_emergency_stop
        })
        self._listener.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._listener:
            self._listener.stop()
        self.release_all()
        # Clear the global stop so future missions are not immediately aborted.
        _GLOBAL_STOP_EVENT.clear()

    def _on_emergency_stop(self):
        """Callback for the emergency stop hotkey."""
        print("\n\n🚨 EMERGENCY STOP TRIGGERED 🚨")
        self._aborted = True
        self.release_all()
        # The main playback loop checks is_aborted() so we don't need to os._exit

    def is_aborted(self) -> bool:
        """Check if playback has been aborted (local or global stop)."""
        return self._aborted or _GLOBAL_STOP_EVENT.is_set()

    def verify_window_focus(self, patterns: List[str]) -> bool:
        """Verify the current foreground window matches acceptable titles.
        
        Args:
            patterns: List of acceptable window title substrings.
            
        Returns:
            True if focus is valid, False otherwise.
        """
        # If no patterns provided, don't enforce window rules
        if not patterns:
            return True
            
        title = get_foreground_window_title()
        return match_window_title(title, patterns)

    def safe_press_key(self, key: keyboard.Key | keyboard.KeyCode):
        if self._aborted:
            return
        self.kb.press(key)
        self.held_keys.add(key)

    def safe_release_key(self, key: keyboard.Key | keyboard.KeyCode):
        self.kb.release(key)
        self.held_keys.discard(key)

    def safe_press_mouse(self, button: mouse.Button):
        if self._aborted:
            return
        self.ms.press(button)
        self.held_buttons.add(button)

    def safe_release_mouse(self, button: mouse.Button):
        self.ms.release(button)
        self.held_buttons.discard(button)

    def release_all(self):
        """Release all currently held keys and mouse buttons."""
        for key in list(self.held_keys):
            try:
                self.kb.release(key)
                self.held_keys.discard(key)
            except Exception as e:
                logger.error(f"Failed to release key {key}: {e}")
                
        for btn in list(self.held_buttons):
            try:
                self.ms.release(btn)
                self.held_buttons.discard(btn)
            except Exception as e:
                logger.error(f"Failed to release button {btn}: {e}")
