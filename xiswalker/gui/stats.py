import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
from pathlib import Path

from xiswalker.importer import export_mission, import_mission
from xiswalker.gui.components import ToggleableLogPanel

class StatsTab(ttk.Frame):
    """File Management & Stats Hub."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.stats_file = Path("missions/stats.json")
        self._create_widgets()

    def _create_widgets(self):
        # File Management Frame
        file_frame = ttk.LabelFrame(self, text="File Management (Import/Export)")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_import = ttk.Button(file_frame, text="Import Mission (File)", command=self.do_import_file)
        btn_import.pack(side=tk.LEFT, padx=10, pady=10)
        
        btn_import_clip = ttk.Button(file_frame, text="Import Mission (Clipboard)", command=self.do_import_clip)
        btn_import_clip.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Export inputs
        export_inner = ttk.Frame(file_frame)
        export_inner.pack(side=tk.RIGHT, padx=10, pady=10)
        
        self.cmb_type = ttk.Combobox(export_inner, values=["atomic", "composite"], width=10, state="readonly")
        self.cmb_type.current(0)
        self.cmb_type.pack(side=tk.LEFT, padx=5)
        
        self.ent_export_name = ttk.Entry(export_inner, width=15)
        self.ent_export_name.pack(side=tk.LEFT, padx=5)
        
        btn_export = ttk.Button(export_inner, text="Export to Clipboard", command=self.do_export)
        btn_export.pack(side=tk.LEFT, padx=5)

        # Stats display frame
        stats_frame = ttk.LabelFrame(self, text="Recent Runs")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.txt_stats = tk.Text(stats_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, bg="#3c3f41", fg="white")
        self.txt_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.txt_stats.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_stats.configure(yscrollcommand=scrollbar.set)
        
        # Log panel (toggleable) - this is the main log that receives all messages
        self.log_panel = ToggleableLogPanel(self, self.app, height=8)
        self.log_panel.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM, padx=10, pady=5)
        # Note: We don't register this one since it's the main log destination

    def log_message(self, msg: str):
        """Main log destination - also update stats display."""
        self.log_panel.log_message(msg)
        # Also add to stats display
        self.txt_stats.config(state=tk.NORMAL)
        self.txt_stats.insert(tk.END, msg + "\n")
        self.txt_stats.see(tk.END)
        self.txt_stats.config(state=tk.DISABLED)

    def do_import_file(self):
        file_path = filedialog.askopenfilename(title="Select Mission Export File", filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                import_mission(file_path)
                self.app.log_message(f"Successfully imported mission from {file_path}")
                if hasattr(self.app, 'tab_dashboard'):
                    self.app.tab_dashboard.refresh_missions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import from file: {e}")
                
    def do_import_clip(self):
        try:
            # We assume the user has the json wrapped in clipboard, import_mission works from file ideally 
            # In xiswalker importer, import_mission accepts `file` argument which can read raw json if exists.
            text = self.clipboard_get()
            # Dump to temp file, then import
            temp = Path("missions") / "temp_import.json"
            temp.write_text(text, encoding="utf-8")
            import_mission(str(temp))
            temp.unlink()
            self.app.log_message("Successfully imported mission from clipboard.")
            if hasattr(self.app, 'tab_dashboard'):
                self.app.tab_dashboard.refresh_missions()
        except tk.TclError:
            messagebox.showwarning("Warning", "Clipboard is empty.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import from clipboard: {e}")

    def do_export(self):
        m_type = self.cmb_type.get()
        m_name = self.ent_export_name.get().strip()
        if not m_name:
            messagebox.showwarning("Warning", "Please enter a mission name to export.")
            return
            
        try:
            export_mission(m_type, m_name, to_clipboard=True)
            self.app.log_message(f"Exported {m_type} mission '{m_name}' to clipboard.")
            messagebox.showinfo("Success", f"{m_name} copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
