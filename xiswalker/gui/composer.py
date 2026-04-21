import tkinter as tk
from tkinter import ttk, messagebox
import yaml
from pathlib import Path

from xiswalker.utilities import ATOMIC_DIR, COMPOSITE_DIR
from xiswalker.gui.components import ToggleableLogPanel
from xiswalker.gui.visual_step_dialog import VisualStepDialog
from xiswalker.gui.ocr_step_dialog import OcrStepDialog
from xiswalker.gui.ocr_timer_dialog import OcrTimerDialog

class ComposerTab(ttk.Frame):
    """Visual Mission Composer to build composite yaml files."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.steps = []  # List of dicts representing steps
        self._create_widgets()
        self.refresh_atomics()
        self.refresh_composites()

    def _create_widgets(self):
        # ── Load Existing Frame (topmost) ──────────────────────────────────────
        load_frame = ttk.LabelFrame(self, text="Load Existing Composite Mission")
        load_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(load_frame, text="Mission:").pack(side=tk.LEFT, padx=5, pady=5)
        self.cmb_composites = ttk.Combobox(load_frame, state="readonly")
        self.cmb_composites.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(load_frame, text="Load", command=self._load_selected_composite).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(load_frame, text="New / Clear", command=self.clear_composer).pack(side=tk.LEFT, padx=5, pady=5)

        # ── Current Sequence ──────────────────────────────────────────────────
        # Top Frame: Current Sequence
        seq_frame = ttk.LabelFrame(self, text="Current Sequence")
        seq_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.seq_listbox = tk.Listbox(seq_frame, selectmode=tk.SINGLE, height=10)
        self.seq_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        seq_scroll = ttk.Scrollbar(seq_frame, orient="vertical", command=self.seq_listbox.yview)
        self.seq_listbox.configure(yscrollcommand=seq_scroll.set)
        seq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons for sequence manipulation
        btn_frame = ttk.Frame(seq_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        btn_up = ttk.Button(btn_frame, text="▲ Move Up", command=self.move_step_up)
        btn_up.pack(side=tk.LEFT, padx=2)
        
        btn_down = ttk.Button(btn_frame, text="▼ Move Down", command=self.move_step_down)
        btn_down.pack(side=tk.LEFT, padx=2)
        
        btn_remove = ttk.Button(btn_frame, text="Remove", command=self.remove_step)
        btn_remove.pack(side=tk.RIGHT, padx=2)

        # Middle Frame: Add Steps
        add_frame = ttk.LabelFrame(self, text="Add Steps")
        add_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Add Atomic
        ttk.Label(add_frame, text="Atomic Mission:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.cmb_atomics = ttk.Combobox(add_frame, state="readonly")
        self.cmb_atomics.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(add_frame, text="Add Atomic", command=self.add_atomic).grid(row=0, column=2, padx=5, pady=5)
        
        # Add Wait
        ttk.Label(add_frame, text="Wait (seconds):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.ent_wait = ttk.Entry(add_frame, width=10)
        self.ent_wait.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(add_frame, text="Add Wait", command=self.add_wait).grid(row=1, column=2, padx=5, pady=5)
        
        # Buttons for logic blocks (future) or refresh
        ttk.Button(add_frame, text="Refresh Atomics", command=self.refresh_atomics).grid(row=0, column=3, padx=10, pady=5)
        
        # Add Visual Step button
        ttk.Button(add_frame, text="➕ Add Visual Step (Image Detection)",
                   command=self.add_visual_step).grid(row=2, column=0, columnspan=4, padx=5, pady=(10, 2), sticky=tk.EW)

        # Add OCR Step button
        ttk.Button(add_frame, text="🔤 Add OCR Step (Text Detection)",
                   command=self.add_ocr_step).grid(row=3, column=0, columnspan=4, padx=5, pady=(2, 10), sticky=tk.EW)

        # Add Timer OCR Step button
        ttk.Button(add_frame, text="⏱ Add Timer OCR Step (Wait for Timer)",
                   command=self.add_ocr_timer_step).grid(row=4, column=0, columnspan=4, padx=5, pady=(0, 10), sticky=tk.EW)

        # Bottom Frame: Save Composite
        save_frame = ttk.LabelFrame(self, text="Save Composite Mission")
        save_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        ttk.Label(save_frame, text="Mission Name:").pack(side=tk.LEFT, padx=5, pady=5)
        self.ent_name = ttk.Entry(save_frame)
        self.ent_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Button(save_frame, text="Save as Composite", command=self.save_composite).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Log panel (toggleable)
        self.log_panel = ToggleableLogPanel(self, self.app, height=6)
        self.log_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.app.register_log_panel(self.log_panel)

    def refresh_atomics(self):
        """Reload available atomic missions into the combobox."""
        if ATOMIC_DIR.exists():
            atomics = [p.stem for p in sorted(ATOMIC_DIR.glob("*.jsonl"))]
            self.cmb_atomics['values'] = atomics
            if atomics:
                self.cmb_atomics.current(0)

    def refresh_composites(self):
        """Reload available composite missions into the load combobox."""
        if COMPOSITE_DIR.exists():
            composites = [p.stem for p in sorted(COMPOSITE_DIR.glob("*.yaml"))]
            self.cmb_composites['values'] = composites

    def _load_selected_composite(self):
        """Load the composite selected in the dropdown into the editor."""
        name = self.cmb_composites.get()
        if not name:
            messagebox.showwarning("Warning", "Please select a composite mission to load.")
            return
        self.load_composite(name)

    def load_composite(self, name: str):
        """Load a composite YAML by stem name into the composer editor."""
        path = COMPOSITE_DIR / f"{name}.yaml"
        if not path.exists():
            messagebox.showerror("Error", f"Composite mission not found: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.steps = list(data.get("steps", []))
            self.ent_name.delete(0, tk.END)
            self.ent_name.insert(0, data.get("name", name))
            self._update_seq_listbox()
            self.app.log_message(f"Loaded composite for editing: {name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load composite '{name}': {e}")

    def clear_composer(self):
        """Reset the composer to an empty state."""
        self.steps = []
        self.ent_name.delete(0, tk.END)
        self._update_seq_listbox()
        self.app.log_message("Composer cleared.")
    
    def _update_seq_listbox(self):
        self.seq_listbox.delete(0, tk.END)
        for i, step in enumerate(self.steps, 1):
            if "mission" in step:
                self.seq_listbox.insert(tk.END, f"{i}. [Atomic] {step['mission']}")
            elif "wait" in step:
                self.seq_listbox.insert(tk.END, f"{i}. [Wait] {step['wait']}s")
            elif "visual_condition" in step:
                template = step['visual_condition']
                on_found = step.get('on_found', 'Click Only')
                on_not_found = step.get('on_not_found', step.get('on_fail', 'skip'))
                display = f"{i}. [Visual] {template[:20]} → Found:{on_found[:15]} / NotFound:{on_not_found[:15]}"
                self.seq_listbox.insert(tk.END, display)
            elif "ocr_text" in step:
                text = step['ocr_text']
                backend = step.get('ocr_backend', 'pytesseract')
                on_fail = step.get('on_fail', 'skip')
                display = f"{i}. [OCR] \"{text[:25]}\" via {backend} (on_fail={on_fail})"
                self.seq_listbox.insert(tk.END, display)
            elif step.get('ocr_timer'):
                roi = step.get('ocr_roi', [])
                backend = step.get('ocr_backend', 'pytesseract')
                on_expire = step.get('timer_on_expire', 'none')
                loop = '↺ loop' if step.get('timer_loop') else ''
                display = f"{i}. [Timer OCR] ROI{roi} → expire:{on_expire}{loop}"
                self.seq_listbox.insert(tk.END, display)

    def add_atomic(self):
        val = self.cmb_atomics.get()
        if not val:
            messagebox.showwarning("Warning", "Please select an atomic mission to add.")
            return
        self.steps.append({"mission": val, "atomic": True})
        self._update_seq_listbox()

    def add_wait(self):
        val = self.ent_wait.get().strip()
        try:
            val_float = float(val)
            if val_float <= 0:
                raise ValueError
            self.steps.append({"wait": val_float})
            self._update_seq_listbox()
            self.ent_wait.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Error", "Wait must be a positive number.")

    def remove_step(self):
        sel = self.seq_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.steps.pop(idx)
        self._update_seq_listbox()
        
    def move_step_up(self):
        """Move selected step up in the sequence."""
        sel = self.seq_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx > 0:
            # Swap with previous item
            self.steps[idx], self.steps[idx-1] = self.steps[idx-1], self.steps[idx]
            self._update_seq_listbox()
            # Reselect the moved item
            self.seq_listbox.selection_set(idx-1)
    
    def move_step_down(self):
        """Move selected step down in the sequence."""
        sel = self.seq_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.steps) - 1:
            # Swap with next item
            self.steps[idx], self.steps[idx+1] = self.steps[idx+1], self.steps[idx]
            self._update_seq_listbox()
            # Reselect the moved item
            self.seq_listbox.selection_set(idx+1)
        
    def add_visual_step(self):
        """Open dialog to add a visual conditional step."""
        dialog = VisualStepDialog(self, self.app)
        self.wait_window(dialog)
        if dialog.result:
            self.steps.append(dialog.result)
            self._update_seq_listbox()
            self.app.log_message(f"Added visual step: {dialog.result['visual_condition']}")

    def add_ocr_step(self):
        """Open dialog to add an OCR text-detection conditional step."""
        dialog = OcrStepDialog(self, self.app)
        self.wait_window(dialog)
        if dialog.result:
            self.steps.append(dialog.result)
            self._update_seq_listbox()
            self.app.log_message(f"Added OCR step: '{dialog.result['ocr_text']}' via {dialog.result['ocr_backend']}")

    def add_ocr_timer_step(self):
        """Open dialog to add a timer-OCR step (read timer, wait, run atomic)."""
        dialog = OcrTimerDialog(self, self.app)
        self.wait_window(dialog)
        if dialog.result:
            self.steps.append(dialog.result)
            self._update_seq_listbox()
            on_expire = dialog.result.get('timer_on_expire', 'none')
            self.app.log_message(f"Added Timer OCR step: on expire → {on_expire}")

    def save_composite(self):
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a mission name.")
            return
            
        if not self.steps:
            messagebox.showwarning("Warning", "Cannot save an empty composite mission.")
            return

        path = COMPOSITE_DIR / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "name": name,
            "type": "composite",
            "description": "Composed using GUI",
            "grace_period": 5,
            "steps": self.steps
        }
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False)
            messagebox.showinfo("Success", f"Composite mission saved to {path}")
            self.app.log_message(f"Created composite mission: {name}")
            
            # Optionally refresh other tabs
            if hasattr(self.app, 'tab_dashboard'):
                self.app.tab_dashboard.refresh_missions()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save composite mission: {e}")
        else:
            self.refresh_composites()
