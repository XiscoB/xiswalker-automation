import tkinter as tk
from tkinter import ttk, messagebox
import threading

from xiswalker.recorder import record_mission, record_relative_mission, capture_template as _capture_template_logic
from xiswalker.gui.components import ToggleableLogPanel

class RecorderTab(ttk.Frame):
    """Recorder & Calibration Hub for capturing macro and visual template sequences."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.var_visual = tk.BooleanVar(value=False)
        self._create_widgets()
        self._refresh_template_list()

    def _refresh_template_list(self):
        """Refresh the template dropdown list."""
        from pathlib import Path
        templates_dir = Path("missions/templates")
        
        templates = []
        if templates_dir.exists():
            templates = [f.name for f in templates_dir.iterdir() 
                        if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
        
        self.cmb_relative_template['values'] = templates
        if templates:
            self.cmb_relative_template.set(templates[0])
        
    def _create_widgets(self):
        # Instructions
        info_frame = ttk.LabelFrame(self, text="How It Works")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_text = (
            "1. Capture a template of your 'Chat Window' or UI element\n"
            "2. The system will find it anywhere on screen, even if moved\n"
            "3. Create relative click missions to click options within the found window\n"
            "4. Use Template Manager tab to manage and test your templates"
        )
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(padx=10, pady=5)
        
        # Recorder Frame
        rec_frame = ttk.LabelFrame(self, text="Record Atomic Mission")
        rec_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(rec_frame, text="Mission Name:").pack(side=tk.LEFT, padx=5, pady=5)
        self.ent_rec_name = ttk.Entry(rec_frame)
        self.ent_rec_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Checkbutton(rec_frame, text="Visual Checkpoints (F8)", variable=self.var_visual).pack(side=tk.LEFT, padx=5, pady=5)
        
        btn_record = ttk.Button(rec_frame, text="Start Recording", command=self.start_record)
        btn_record.pack(side=tk.RIGHT, padx=5, pady=5)
        
        ttk.Label(rec_frame, text="Press ESC to stop recording", foreground="gray").pack(side=tk.BOTTOM, pady=2)

        # Calibration Hub Frame
        cal_frame = ttk.LabelFrame(self, text="Capture Template (Click-Drag to Select Region)")
        cal_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(cal_frame, text="Template Name:").pack(side=tk.LEFT, padx=5, pady=5)
        self.ent_cal_name = ttk.Entry(cal_frame)
        self.ent_cal_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        btn_capture = ttk.Button(cal_frame, text="Capture Template", command=self.capture_template)
        btn_capture.pack(side=tk.RIGHT, padx=5, pady=5)
        
        ttk.Label(cal_frame, text="After clicking, you have 2 seconds to position. Then click-drag to select the region.", 
                  foreground="gray").pack(side=tk.BOTTOM, pady=2)
        
        # Relative Recording Frame
        rel_frame = ttk.LabelFrame(self, text="Relative Recording (Template-Based)")
        rel_frame.pack(fill=tk.X, padx=10, pady=10)
        
        rel_info = (
            "Record mouse actions relative to a template's position. "
            "Even if the template moves, playback will find it and apply the same offsets."
        )
        ttk.Label(rel_frame, text=rel_info, wraplength=600, foreground="gray").pack(padx=5, pady=5)
        
        # Row 1: Mission Name and Template
        rel_row1 = ttk.Frame(rel_frame)
        rel_row1.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(rel_row1, text="Mission Name:").pack(side=tk.LEFT)
        self.ent_relative_name = ttk.Entry(rel_row1, width=25)
        self.ent_relative_name.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(rel_row1, text="Template:").pack(side=tk.LEFT, padx=(15, 0))
        self.cmb_relative_template = ttk.Combobox(rel_row1, width=25, state="readonly")
        self.cmb_relative_template.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(rel_row1, text="Refresh List", 
                   command=self._refresh_template_list).pack(side=tk.LEFT, padx=5)
        
        # Row 2: Action Buttons
        rel_row2 = ttk.Frame(rel_frame)
        rel_row2.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(rel_row2, text="Start Relative Recording", 
                   command=self.start_relative_record).pack(side=tk.LEFT, padx=5)
        
        # Auto-generate name hint
        ttk.Label(rel_frame, text="Tip: Mission name will be auto-generated if left empty", 
                  foreground="gray", font=("Segoe UI", 8)).pack(pady=2)
        
        # Quick Actions Frame
        quick_frame = ttk.LabelFrame(self, text="Quick Actions")
        quick_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(quick_frame, text="Open Template Manager", 
                   command=self._open_template_manager).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(quick_frame, text="Refresh Template List", 
                   command=self._refresh_templates).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Log panel (toggleable)
        self.log_panel = ToggleableLogPanel(self, self.app, height=6)
        self.log_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.app.register_log_panel(self.log_panel)

    def start_relative_record(self):
        """Start recording relative to a template."""
        name = self.ent_relative_name.get().strip()
        
        # Auto-generate name if empty
        template = self.cmb_relative_template.get()
        if not name and template:
            import re
            base = re.sub(r'\.[^.]+$', '', template)  # Remove extension
            name = f"rel_{base}"
            self.ent_relative_name.insert(0, name)
        
        if not name:
            messagebox.showwarning("Warning", "Please enter a mission name to record.")
            return
            
        template = self.cmb_relative_template.get()
        if not template:
            messagebox.showwarning("Warning", "Please select a template to record relative to.")
            return
            
        visual = self.var_visual.get()
        self.app.log_message(f"Starting RELATIVE recording of '{name}' relative to '{template}' in 5 seconds...")
        
        # Run recorder in a separate thread
        thread = threading.Thread(
            target=self._run_relative_record_thread,
            args=(name, template, visual),
            daemon=True
        )
        thread.start()
        
    def _run_relative_record_thread(self, name, template, visual):
        try:
            record_relative_mission(name, template_name=template, visual=visual)
            self.app.log_message(f"Successfully recorded relative mission: {name}")
            if hasattr(self.app, 'tab_dashboard'):
                self.app.after(0, self.app.tab_dashboard.refresh_missions)
        except Exception as e:
            self.app.log_message(f"Error recording relative mission {name}: {e}")

    def start_record(self):
        name = self.ent_rec_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a mission name to record.")
            return
            
        visual = self.var_visual.get()
        self.app.log_message(f"Starting recording of atomic mission '{name}' in 5 seconds...")
        
        # Run recorder in a separate thread so GUI doesn't freeze
        thread = threading.Thread(
            target=self._run_record_thread,
            args=(name, visual),
            daemon=True
        )
        thread.start()
        
    def _run_record_thread(self, name, visual):
        try:
            record_mission(name, visual=visual)
            self.app.log_message(f"Successfully recorded mission: {name}")
            if hasattr(self.app, 'tab_dashboard'):
                self.app.after(0, self.app.tab_dashboard.refresh_missions)
        except Exception as e:
            self.app.log_message(f"Error recording mission {name}: {e}")

    def capture_template(self):
        name = self.ent_cal_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a template name.")
            return

        # Hide entire main window so the game/desktop is fully visible
        self.app.withdraw()

        # Small always-on-top hint bar
        hint = tk.Toplevel()
        hint.overrideredirect(True)
        hint.attributes("-topmost", True)
        hint.attributes("-alpha", 0.85)
        sw = hint.winfo_screenwidth()
        hint.geometry(f"+{sw // 2 - 200}+8")
        tk.Label(
            hint,
            text=f"  Click and drag to capture template: '{name}'  ",
            font=("Segoe UI", 11, "bold"),
            bg="#1e88e5", fg="white", padx=12, pady=8,
        ).pack()
        hint.update()

        threading.Thread(
            target=self._run_capture_thread,
            args=(name, hint),
            daemon=True,
        ).start()

    def _run_capture_thread(self, name: str, hint) -> None:
        try:
            _capture_template_logic(name)
            self.app.after(0, lambda: self._capture_done(hint, name, None))
        except Exception as exc:
            self.app.after(0, lambda: self._capture_done(hint, name, exc))

    def _capture_done(self, hint, name: str, exc) -> None:
        try:
            hint.destroy()
        except Exception:
            pass
        self.app.deiconify()
        if exc is None:
            self.app.log_message(f"✓ Template '{name}' captured successfully.")
            if hasattr(self.app, 'tab_template_manager'):
                self.app.after(0, self.app.tab_template_manager.refresh_templates)
        else:
            self.app.log_message(f"Error capturing template '{name}': {exc}")
            
    def _open_template_manager(self):
        """Switch to template manager tab."""
        if hasattr(self.app, 'tab_template_manager'):
            notebook = self.app.notebook
            for i in range(notebook.index('end')):
                if notebook.tab(i, 'text') == 'Template Manager':
                    notebook.select(i)
                    break
                    
    def _refresh_templates(self):
        """Refresh templates in all relevant tabs."""
        self._refresh_template_list()
        if hasattr(self.app, 'tab_template_manager'):
            self.app.tab_template_manager.refresh_templates()
            self.app.log_message("Template list refreshed")
