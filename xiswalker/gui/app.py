import tkinter as tk
from tkinter import ttk
import sys
import queue

from xiswalker.gui.dashboard import DashboardTab
from xiswalker.gui.composer import ComposerTab
from xiswalker.gui.recorder import RecorderTab
from xiswalker.gui.stats import StatsTab
from xiswalker.gui.config_tab import ConfigTab
from xiswalker.gui.template_manager import TemplateManagerTab
from xiswalker.gui.scheduler_tab import SchedulerTab

class XisWalkerApp(tk.Tk):
    """Main Application Window for XisWalker."""
    
    def __init__(self):
        super().__init__()
        
        self.title("XisWalker - Input Automation Framework")
        self.geometry("900x700")
        
        # A queue for thread-safe communication
        self.msg_queue = queue.Queue()
        
        # Track all log panels for broadcasting messages
        self.log_panels = []
        
        # Apply strict Dark Mode by default
        self._apply_dark_theme()
        
        # Setup UI
        self._create_widgets()
        
        # Start a periodic check for cross-thread messages
        self.after(100, self._process_msg_queue)
        
        # Start periodic overlay update for thread-safe overlay handling
        self.after(100, self._process_overlay_pending)

    def _apply_dark_theme(self):
        """Apply a dark mode theme strictly using standard tkinter."""
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        entry_bg = "#3c3f41"
        sel_bg = "#2f65ca"
        
        self.configure(bg=bg_color)
        
        # Configure standard tk widgets (Text, Listbox, etc) that ignore ttk.Style
        self.tk_setPalette(background=bg_color, foreground=fg_color,
                           activeBackground='#3c3f41', activeForeground=fg_color,
                           insertBackground=fg_color, selectColor=sel_bg)
                           
        self.option_add('*Text*Background', entry_bg)
        self.option_add('*Text*Foreground', fg_color)
        self.option_add('*Listbox*Background', entry_bg)
        self.option_add('*Listbox*Foreground', fg_color)
        self.option_add('*TCombobox*Listbox.background', entry_bg)
        self.option_add('*TCombobox*Listbox.foreground', fg_color)
        
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        style.configure('.', background=bg_color, foreground=fg_color, fieldbackground=entry_bg, insertcolor=fg_color, selectbackground=sel_bg)
        style.configure('TNotebook', background=bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', background='#3c3f41', foreground=fg_color, padding=[10, 2])
        style.map('TNotebook.Tab', background=[('selected', bg_color)])
        style.configure('TLabelframe', background=bg_color, foreground=fg_color)
        style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color)
        style.configure('TButton', background='#4a4d50', foreground=fg_color, borderwidth=1)
        style.map('TButton', background=[('active', '#5c5f61')])
        style.configure('Treeview', background=entry_bg, foreground=fg_color, fieldbackground=entry_bg)
        style.map('Treeview', background=[('selected', sel_bg)])
        style.configure('TCombobox', fieldbackground=entry_bg, background=bg_color, foreground=fg_color, arrowcolor=fg_color)
        style.configure('TEntry', fieldbackground=entry_bg, foreground=fg_color)

    def _create_widgets(self):
        """Create the main notebook and tabs."""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.tab_dashboard = DashboardTab(self.notebook, self)
        self.tab_composer = ComposerTab(self.notebook, self)
        self.tab_recorder = RecorderTab(self.notebook, self)
        self.tab_template_manager = TemplateManagerTab(self.notebook, self)
        self.tab_stats = StatsTab(self.notebook, self)
        self.tab_config = ConfigTab(self.notebook, self)
        self.tab_scheduler = SchedulerTab(self.notebook, self)
        
        self.notebook.add(self.tab_dashboard, text="Dashboard")
        self.notebook.add(self.tab_composer, text="Composer")
        self.notebook.add(self.tab_recorder, text="Recorder")
        self.notebook.add(self.tab_template_manager, text="Templates")
        self.notebook.add(self.tab_stats, text="Files & Stats")
        self.notebook.add(self.tab_config, text="Config")
        self.notebook.add(self.tab_scheduler, text="Scheduler")
        
    def log_message(self, msg: str):
        """Push a message to the UI from any thread."""
        self.msg_queue.put(msg)
        
    def register_log_panel(self, log_panel):
        """Register a log panel to receive broadcast messages."""
        if log_panel not in self.log_panels:
            self.log_panels.append(log_panel)
            
    def _broadcast_message(self, msg: str):
        """Send message to all registered log panels."""
        # Always send to stats tab (main log)
        self.tab_stats.log_message(msg)
        # Also send to all other registered log panels
        for panel in self.log_panels:
            try:
                panel.log_message(msg)
            except Exception:
                pass  # Panel might have been destroyed
        
    def _process_msg_queue(self):
        """Periodically check the queue and route messages to UI elements."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self._broadcast_message(msg)
                self.msg_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_msg_queue)
            
    def _process_overlay_pending(self):
        """Process pending overlay show/hide requests from background threads."""
        from xiswalker.overlay import get_overlay
        try:
            overlay = get_overlay()
            overlay.process_pending()
        except Exception:
            pass
        finally:
            self.after(100, self._process_overlay_pending)

    def load_composite_in_composer(self, name: str):
        """Switch to the Composer tab and pre-load *name* for editing."""
        self.notebook.select(self.tab_composer)
        self.tab_composer.load_composite(name)

def run_gui():
    """Launch the XisWalker Desktop GUI."""
    app = XisWalkerApp()
    app.mainloop()

if __name__ == "__main__":
    run_gui()
