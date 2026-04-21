import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import re as _re
from pathlib import Path

from xiswalker.utilities import ATOMIC_DIR, COMPOSITE_DIR
from xiswalker.player import play_atomic, play_composite
from xiswalker.gui.components import ToggleableLogPanel

class DashboardTab(ttk.Frame):
    """Mission Dashboard displaying current tasks and execution toggles."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        # Variables for global toggles
        self.var_safe_mode = tk.BooleanVar(value=False)
        self.var_humanize = tk.DoubleVar(value=0.0)
        
        self._create_widgets()
        self.refresh_missions()

    def _create_widgets(self):
        # Toggles frame
        toggles_frame = ttk.LabelFrame(self, text="Global Settings")
        toggles_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(toggles_frame, text="Safe Mode", variable=self.var_safe_mode).pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(toggles_frame, text="Humanize").pack(side=tk.LEFT, padx=(20, 5), pady=5)
        humanize_scale = ttk.Scale(toggles_frame, from_=0.0, to=0.5, variable=self.var_humanize, orient=tk.HORIZONTAL)
        humanize_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        btn_refresh = ttk.Button(toggles_frame, text="Refresh", command=self.refresh_missions)
        btn_refresh.pack(side=tk.RIGHT, padx=5, pady=5)

        # Missions frame
        missions_frame = ttk.Frame(self)
        missions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Split into Atomics and Composites
        self.tree_atomics = self._create_mission_list(missions_frame, "Atomic Missions", tk.LEFT)
        self.tree_composites = self._create_mission_list(missions_frame, "Composite Missions", tk.RIGHT)
        
        # Log panel (toggleable)
        self.log_panel = ToggleableLogPanel(self, self.app, height=6)
        self.log_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.app.register_log_panel(self.log_panel)

    def _create_mission_list(self, parent_frame, title, side):
        frame = ttk.LabelFrame(parent_frame, text=title)
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tree = ttk.Treeview(frame, columns=("Name",), show="headings", selectmode="browse")
        tree.heading("Name", text="Mission Name")
        tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        btn_play = ttk.Button(btn_frame, text="Play", command=lambda t=tree, title=title: self.play_selected(t, title))
        btn_play.pack(side=tk.LEFT, padx=(0, 2))
        
        btn_delete = ttk.Button(btn_frame, text="Delete", command=lambda t=tree, title=title: self.delete_selected(t, title))
        btn_delete.pack(side=tk.LEFT, padx=2)

        if "Composite" in title:
            btn_edit = ttk.Button(btn_frame, text="Edit", command=lambda t=tree: self.edit_selected_composite(t))
            btn_edit.pack(side=tk.LEFT, padx=2)
        
        btn_cancel = ttk.Button(btn_frame, text="Cancel", command=self.cancel_mission)
        btn_cancel.pack(side=tk.RIGHT, padx=(2, 0))
        
        return tree

    def refresh_missions(self):
        """Reload missions from the filesystem."""
        for item in self.tree_atomics.get_children():
            self.tree_atomics.delete(item)
        for item in self.tree_composites.get_children():
            self.tree_composites.delete(item)
            
        if ATOMIC_DIR.exists():
            for p in sorted(ATOMIC_DIR.glob("*.jsonl")):
                self.tree_atomics.insert("", "end", values=(p.stem,))
                
        if COMPOSITE_DIR.exists():
            for p in sorted(COMPOSITE_DIR.glob("*.yaml")):
                self.tree_composites.insert("", "end", values=(p.stem,))

    def edit_selected_composite(self, tree):
        """Load the selected composite mission into the Composer tab for editing."""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a composite mission to edit.")
            return
        mission_name = tree.item(selected[0])["values"][0]
        self.app.load_composite_in_composer(mission_name)

    def play_selected(self, tree, title):
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a mission to play.")
            return
            
        mission_name = tree.item(selected[0])["values"][0]
        mission_type = "atomic" if "Atomic" in title else "composite"
        
        humanize_val = round(self.var_humanize.get(), 3)
        safe_mode_val = self.var_safe_mode.get()
        
        # Run in a background thread to prevent GUI freezing
        thread = threading.Thread(
            target=self._run_mission_thread,
            args=(mission_type, mission_name, humanize_val, safe_mode_val),
            daemon=True
        )
        thread.start()
        self.app.log_message(f"Started playback of {mission_type} mission: {mission_name}")

    def _run_mission_thread(self, m_type, m_name, hum, safe):
        _ansi = _re.compile(r'\x1b\[[0-9;]*m')

        class _GuiWriter:
            def __init__(self_, stream):
                self_.buf = ""
                self_.orig = stream

            def write(self_, text):
                self_.orig.write(text)  # keep terminal output too
                cleaned = _ansi.sub("", text)
                self_.buf += cleaned
                while "\n" in self_.buf:
                    line, self_.buf = self_.buf.split("\n", 1)
                    if line.strip():
                        self.app.after(0, lambda l=line: self.app.log_message(l))

            def flush(self_):
                self_.orig.flush()
                # Flush any buffered partial line so it's not silently lost
                if self_.buf.strip():
                    line = self_.buf.strip()
                    self_.buf = ""
                    self.app.after(0, lambda l=line: self.app.log_message(l))

        writer = _GuiWriter(sys.stdout)
        old_stdout = sys.stdout
        sys.stdout = writer
        try:
            if m_type == "atomic":
                play_atomic(m_name, humanize=hum, safe_mode=safe)
            else:
                play_composite(m_name, humanize=hum, safe_mode=safe)
            self.app.log_message(f"Mission {m_name} finished successfully.")
        except Exception as e:
            self.app.log_message(f"Error executing mission {m_name}: {e}")
        finally:
            sys.stdout = old_stdout

    def delete_selected(self, tree, title):
        """Delete the selected mission."""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a mission to delete.")
            return
        
        mission_name = tree.item(selected[0])["values"][0]
        mission_type = "atomic" if "Atomic" in title else "composite"
        
        if messagebox.askyesno("Confirm Delete", f"Delete {mission_type} mission '{mission_name}'?"):
            try:
                if mission_type == "atomic":
                    path = ATOMIC_DIR / f"{mission_name}.jsonl"
                else:
                    path = COMPOSITE_DIR / f"{mission_name}.yaml"
                
                if path.exists():
                    path.unlink()
                    self.app.log_message(f"Deleted {mission_type} mission: {mission_name}")
                    self.refresh_missions()
                else:
                    messagebox.showerror("Error", f"Mission file not found: {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete mission: {e}")

    def cancel_mission(self):
        """Trigger the emergency stop hotkey securely to abort running tasks."""
        try:
            from pynput.keyboard import Controller, Key
            kb = Controller()
            # Send Ctrl+Shift+End to signal emergency stop globally
            with kb.pressed(Key.ctrl, Key.shift):
                kb.press(Key.end)
                kb.release(Key.end)
            if hasattr(self, 'app'):
                self.app.log_message("Sent emergency stop hotkey (Ctrl+Shift+End).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send cancel hotkey: {e}")
