"""Status overlay for XisWalker — floating window showing recording/playback state."""

import tkinter as tk
from typing import Optional
import threading


class StatusOverlay:
    """A floating overlay window showing current operation status.
    
    Displays a small, always-on-top window indicating whether recording
    or playback is active, along with the stop key to press.
    """
    
    def __init__(self):
        self._window: Optional[tk.Toplevel] = None
        self._status_label: Optional[tk.Label] = None
        self._stop_key_label: Optional[tk.Label] = None
        self._step_label: Optional[tk.Label] = None
        self._is_visible = False
        self._pending_show = None  # For thread-safe showing
        self._pending_hide = False  # For thread-safe hiding
    
    def show(self, mode: str, stop_key: str, parent: Optional[tk.Tk] = None, countdown: int = 0):
        """Show the overlay with the given status.
        
        Args:
            mode: Either "recording" or "playing"
            stop_key: The key combination to stop the operation
            parent: Optional parent window (for GUI mode)
            countdown: Countdown seconds to display before starting
        """
        # If called from a non-main thread, queue for main thread
        if threading.current_thread() is not threading.main_thread():
            self._pending_show = (mode, stop_key, parent, countdown)
            return
            
        self._do_show(mode, stop_key, parent, countdown)
    
    def _do_show(self, mode: str, stop_key: str, parent: Optional[tk.Tk] = None, countdown: int = 0):
        """Internal method to actually create and show the window."""
        if self._window is not None:
            self.hide()
        
        # Create a new top-level window
        if parent is not None:
            self._window = tk.Toplevel(parent)
        else:
            self._window = tk.Toplevel()
        
        self._window.overrideredirect(True)  # No window decorations
        self._window.attributes('-topmost', True)  # Always on top
        self._window.attributes('-alpha', 0.9)  # Slight transparency
        
        # Position in top-right corner
        screen_width = self._window.winfo_screenwidth()
        self._window.geometry(f"+{screen_width - 220}+20")
        
        # Force window to be on top and visible
        self._window.lift()
        self._window.focus_force()
        
        self._countdown = countdown
        self._mode = mode
        self._stop_key = stop_key
        
        # Colors based on mode
        if mode == "recording":
            bg_color = "#dc3545"  # Red for recording
            text = "🔴 RECORDING"
        elif mode == "playing":
            bg_color = "#28a745"  # Green for playing
            text = "▶️ PLAYING"
        else:
            bg_color = "#6c757d"  # Gray for unknown
            text = "⏸️ IDLE"
        
        # Main frame
        frame = tk.Frame(self._window, bg=bg_color, padx=15, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Status label
        self._status_label = tk.Label(
            frame,
            text=text,
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg="white"
        )
        self._status_label.pack()
        
        # Countdown label (if countdown active)
        self._countdown_label = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 20, "bold"),
            bg=bg_color,
            fg="yellow"
        )
        self._countdown_label.pack()

        # Step info label
        self._step_label = tk.Label(
            frame,
            text="",
            font=("Segoe UI", 9),
            bg=bg_color,
            fg="#d0d0d0",
            wraplength=200,
            justify=tk.LEFT,
        )
        self._step_label.pack(pady=(2, 0))

        # Stop key hint
        stop_key_display = stop_key.replace("+", " + ").upper()
        self._stop_key_label = tk.Label(
            frame,
            text=f"Press {stop_key_display} to stop",
            font=("Segoe UI", 9),
            bg=bg_color,
            fg="white"
        )
        self._stop_key_label.pack()
        
        self._is_visible = True
        
        # Start countdown if specified
        if countdown > 0:
            self._update_countdown()
        
        # Update to ensure window appears
        self._window.update_idletasks()
        self._window.update()
    
    def _update_countdown(self):
        """Update the countdown display."""
        if not self._is_visible or self._window is None:
            return
        
        if self._countdown > 0:
            self._countdown_label.config(text=f"Starting in {self._countdown}...")
            self._countdown -= 1
            self._window.after(1000, self._update_countdown)
        else:
            self._countdown_label.config(text="GO!")
            # Hide "GO!" after 1 second
            self._window.after(1000, lambda: self._countdown_label.config(text=""))
    
    def update_step(self, current: int, total: int, label: str = "") -> None:
        """Update the current step display on the overlay (thread-safe)."""
        if not self._is_visible or self._window is None or self._step_label is None:
            return
        text = f"Step {current}/{total}"
        if label:
            # Truncate long labels so overlay doesn't grow too wide
            short = label if len(label) <= 28 else label[:25] + "..."
            text += f"\n{short}"
        try:
            # after() is thread-safe: schedules callback on the main event loop
            def _update(t=text):
                if self._step_label:
                    self._step_label.config(text=t)
            self._window.after(0, _update)
        except Exception:
            pass  # Window may have been destroyed

    def process_pending(self):
        """Process any pending show/hide requests from other threads.
        Call this periodically from the main thread."""
        if self._pending_show is not None:
            # Handle both old 3-tuple and new 4-tuple formats
            if len(self._pending_show) == 3:
                mode, stop_key, parent = self._pending_show
                countdown = 0
            else:
                mode, stop_key, parent, countdown = self._pending_show
            self._pending_show = None
            self._do_show(mode, stop_key, parent, countdown)
        
        if self._pending_hide:
            self._pending_hide = False
            self._do_hide()
    
    def hide(self):
        """Hide the overlay window."""
        # If called from a non-main thread, queue for main thread
        if threading.current_thread() is not threading.main_thread():
            self._pending_hide = True
            return
        
        self._do_hide()
    
    def _do_hide(self):
        """Internal method to actually hide the window."""
        if self._window is not None:
            self._window.destroy()
            self._window = None
        self._is_visible = False
    
    def is_visible(self) -> bool:
        """Check if the overlay is currently visible."""
        return self._is_visible


# Global overlay instance for CLI usage
_overlay_instance: Optional[StatusOverlay] = None


def get_overlay() -> StatusOverlay:
    """Get the global overlay instance."""
    global _overlay_instance
    if _overlay_instance is None:
        _overlay_instance = StatusOverlay()
    return _overlay_instance


def show_overlay(mode: str, stop_key: str, parent: Optional[tk.Tk] = None, countdown: int = 0):
    """Show the global overlay with the given status.
    
    Args:
        mode: Either "recording" or "playing"
        stop_key: The key combination to stop the operation
        parent: Optional parent window (for GUI mode)
        countdown: Countdown seconds to display before starting
    """
    overlay = get_overlay()
    overlay.show(mode, stop_key, parent, countdown)


def hide_overlay():
    """Hide the global overlay."""
    overlay = get_overlay()
    overlay.hide()


def update_step_overlay(current: int, total: int, label: str = "") -> None:
    """Update the step counter on the global overlay (thread-safe)."""
    overlay = get_overlay()
    overlay.update_step(current, total, label)
