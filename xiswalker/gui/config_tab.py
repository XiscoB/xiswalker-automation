import tkinter as tk
from tkinter import ttk, messagebox
import yaml
from pathlib import Path

from xiswalker.gui.components import ToggleableLogPanel

class ConfigTab(ttk.Frame):
    """Configuration Tab for editing global configuration."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.config_path = Path("config/config.yaml")
        
        self.var_check_focus = tk.BooleanVar(value=False)
        self.var_show_overlay = tk.BooleanVar(value=True)
        self._create_widgets()
        self.load_config()

    def _create_widgets(self):
        # Create a canvas with scrollbar for scrolling
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Safety Configuration Frame
        safety_frame = ttk.LabelFrame(scrollable_frame, text="Global Safety Configuration")
        safety_frame.pack(fill=tk.X, expand=False, padx=10, pady=10)
        
        ttk.Checkbutton(
            safety_frame,
            text="Require Window Focus Before Input",
            variable=self.var_check_focus
        ).pack(anchor=tk.W, padx=10, pady=10)
        
        ttk.Label(safety_frame, text="Allowed Window Title Patterns (one per line):").pack(anchor=tk.W, padx=10, pady=(10, 0))
        
        self.txt_patterns = tk.Text(safety_frame, height=8, wrap=tk.NONE)
        self.txt_patterns.pack(fill=tk.X, padx=10, pady=5)
        
        # Input Controls Frame
        input_frame = ttk.LabelFrame(scrollable_frame, text="Input Controls")
        input_frame.pack(fill=tk.X, expand=False, padx=10, pady=10)
        
        # Recording Stop Key
        ttk.Label(input_frame, text="Recording Stop Key:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.entry_rec_stop = ttk.Entry(input_frame)
        self.entry_rec_stop.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            input_frame,
            text="Single key name (e.g., esc, f1, f12, end)",
            font=("Segoe UI", 8),
            foreground="gray"
        ).pack(anchor=tk.W, padx=10)
        
        # Playback Stop Key
        ttk.Label(input_frame, text="Playback Stop Key:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.entry_play_stop = ttk.Entry(input_frame)
        self.entry_play_stop.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            input_frame,
            text="Key combination (e.g., ctrl+shift+end, ctrl+f12)",
            font=("Segoe UI", 8),
            foreground="gray"
        ).pack(anchor=tk.W, padx=10)
        
        # Overlay Toggle
        ttk.Checkbutton(
            input_frame,
            text="Show Status Overlay During Recording/Playback",
            variable=self.var_show_overlay
        ).pack(anchor=tk.W, padx=10, pady=10)
        
        # Buttons Frame
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_reload = ttk.Button(btn_frame, text="Reload", command=self.load_config)
        btn_reload.pack(side=tk.LEFT)
        
        btn_save = ttk.Button(btn_frame, text="Save Configuration", command=self.save_config)
        btn_save.pack(side=tk.RIGHT)
        
        # Log panel (toggleable) - placed outside scrollable area at bottom
        self.log_panel = ToggleableLogPanel(self, self.app, height=5)
        self.log_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.app.register_log_panel(self.log_panel)

    def load_config(self):
        if not self.config_path.exists():
            messagebox.showwarning("Warning", f"Config file not found at {self.config_path}")
            return
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
            # Load safety settings
            safety = data.get("safety", {})
            self.var_check_focus.set(safety.get("check_window_focus", False))
            
            patterns = safety.get("window_patterns", [])
            self.txt_patterns.delete("1.0", tk.END)
            self.txt_patterns.insert(tk.END, "\n".join(patterns))
            
            # Load input settings
            input_cfg = data.get("input", {})
            self.entry_rec_stop.delete(0, tk.END)
            self.entry_rec_stop.insert(0, input_cfg.get("recording_stop_key", "esc"))
            
            self.entry_play_stop.delete(0, tk.END)
            self.entry_play_stop.insert(0, input_cfg.get("playback_stop_key", "ctrl+shift+end"))
            
            self.var_show_overlay.set(input_cfg.get("show_overlay", True))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def save_config(self):
        if not self.config_path.parent.exists():
            self.config_path.parent.mkdir(parents=True)
            
        patterns = [p.strip() for p in self.txt_patterns.get("1.0", tk.END).strip().split("\n") if p.strip()]
        
        data = {
            "safety": {
                "check_window_focus": self.var_check_focus.get(),
                "window_patterns": patterns
            },
            "input": {
                "recording_stop_key": self.entry_rec_stop.get().strip() or "esc",
                "playback_stop_key": self.entry_play_stop.get().strip() or "ctrl+shift+end",
                "show_overlay": self.var_show_overlay.get()
            }
        }
        
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False)
            messagebox.showinfo("Success", "Configuration saved successfully!")
            self.app.log_message("Global configuration updated.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
