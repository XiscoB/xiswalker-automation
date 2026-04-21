"""Shared GUI components for XisWalker."""

import tkinter as tk
from tkinter import ttk


class LogPanel(ttk.LabelFrame):
    """A reusable log panel widget that can be embedded in any tab."""
    
    def __init__(self, parent, app, height=8):
        """Initialize the log panel.
        
        Args:
            parent: Parent widget
            app: The main XisWalkerApp instance for message routing
            height: Height of the log text area in lines
        """
        super().__init__(parent, text="Activity Log")
        self.app = app
        self._create_widgets(height)
        
    def _create_widgets(self, height):
        """Create the log panel widgets."""
        # Text area for logs
        self.txt_log = tk.Text(
            self, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            height=height,
            bg="#3c3f41",
            fg="white",
            font=("Consolas", 9)
        )
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.txt_log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.configure(yscrollcommand=scrollbar.set)
        
    def log_message(self, msg: str):
        """Add a message to the log."""
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)
        
    def clear(self):
        """Clear all log messages."""
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.config(state=tk.DISABLED)


class ToggleableLogPanel(ttk.Frame):
    """A log panel that can be toggled on/off with a button."""
    
    def __init__(self, parent, app, height=6):
        """Initialize the toggleable log panel.
        
        Args:
            parent: Parent widget
            app: The main XisWalkerApp instance
            height: Height of the log text area when visible
        """
        super().__init__(parent)
        self.app = app
        self.height = height
        self.is_visible = False
        
        # Toggle button frame
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(fill=tk.X)
        
        self.toggle_btn = ttk.Button(
            self.btn_frame, 
            text="▼ Show Log", 
            command=self._toggle
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.clear_btn = ttk.Button(
            self.btn_frame,
            text="Clear",
            command=self._clear_log
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Log panel (initially hidden)
        self.log_panel = LogPanel(self, app, height=height)
        # Don't pack yet - will be packed when toggled on
        
    def _toggle(self):
        """Toggle the log panel visibility."""
        if self.is_visible:
            self.log_panel.pack_forget()
            self.toggle_btn.config(text="▼ Show Log")
            self.is_visible = False
        else:
            self.log_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            self.toggle_btn.config(text="▲ Hide Log")
            self.is_visible = True
            
    def _clear_log(self):
        """Clear the log."""
        self.log_panel.clear()
        
    def log_message(self, msg: str):
        """Add a message to the log."""
        self.log_panel.log_message(msg)
