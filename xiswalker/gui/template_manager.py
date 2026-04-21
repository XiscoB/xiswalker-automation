"""Template Manager tab for XisWalker GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path

from xiswalker.gui.components import ToggleableLogPanel

TEMPLATES_DIR = Path("missions/templates")
ATOMIC_DIR = Path("missions/atomic")


class TemplateManagerTab(ttk.Frame):
    """Template manager for viewing, testing, and building relative click missions."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_template = None
        self.template_preview_img = None
        self._create_widgets()
        self.refresh_templates()
        
    def _create_widgets(self):
        """Create the UI widgets."""
        # Left side: Template list
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Template list with scrollbar
        list_frame = ttk.LabelFrame(left_frame, text="Available Templates")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.template_list = tk.Listbox(
            list_frame, 
            yscrollcommand=scrollbar.set,
            bg="#3c3f41",
            fg="white",
            selectbackground="#2f65ca",
            selectforeground="white",
            font=("Segoe UI", 10)
        )
        self.template_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.template_list.yview)
        
        self.template_list.bind('<<ListboxSelect>>', self._on_template_select)
        
        # Buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_templates).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Test Find", command=self._test_find_template).pack(side=tk.LEFT, padx=2)
        
        # Right side: Details and actions
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Template preview
        preview_frame = ttk.LabelFrame(right_frame, text="Template Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.preview_label = ttk.Label(preview_frame, text="Select a template to preview")
        self.preview_label.pack(padx=10, pady=10)
        
        # Template info
        info_frame = ttk.LabelFrame(right_frame, text="Template Info")
        info_frame.pack(fill=tk.X, pady=5)
        
        self.info_label = ttk.Label(info_frame, text="No template selected")
        self.info_label.pack(padx=10, pady=5)
        
        # Relative Click Builder
        builder_frame = ttk.LabelFrame(right_frame, text="Relative Click Mission Builder")
        builder_frame.pack(fill=tk.X, pady=5)
        
        # Offset inputs
        offset_frame = ttk.Frame(builder_frame)
        offset_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(offset_frame, text="Offset X:").pack(side=tk.LEFT)
        self.offset_x = ttk.Entry(offset_frame, width=6)
        self.offset_x.insert(0, "0")
        self.offset_x.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(offset_frame, text="Offset Y:").pack(side=tk.LEFT)
        self.offset_y = ttk.Entry(offset_frame, width=6)
        self.offset_y.insert(0, "0")
        self.offset_y.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(offset_frame, text="Pick Offset", command=self._pick_offset).pack(side=tk.LEFT, padx=5)
        
        # Options
        options_frame = ttk.Frame(builder_frame)
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(options_frame, text="Mission Name:").pack(side=tk.LEFT)
        self.mission_name = ttk.Entry(options_frame, width=20)
        self.mission_name.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Build buttons
        build_frame = ttk.Frame(builder_frame)
        build_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(build_frame, text="Create Find-Only Mission", 
                   command=lambda: self._create_mission("find")).pack(side=tk.LEFT, padx=2)
        ttk.Button(build_frame, text="Create Relative Click Mission", 
                   command=lambda: self._create_mission("click")).pack(side=tk.LEFT, padx=2)
        
        # Full Screen Finder section
        finder_frame = ttk.LabelFrame(right_frame, text="Full Screen Template Finder")
        finder_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(finder_frame, text="Finds template anywhere on screen. Aborts after 3 failed attempts.",
                  wraplength=300).pack(padx=5, pady=5)
        
        ttk.Button(finder_frame, text="Create Full-Screen Finder Mission", 
                   command=self._create_finder_mission).pack(padx=5, pady=5)
        
        # Log panel (toggleable)
        self.log_panel = ToggleableLogPanel(self, self.app, height=5)
        self.log_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.app.register_log_panel(self.log_panel)
        
    def refresh_templates(self):
        """Refresh the template list."""
        self.template_list.delete(0, tk.END)
        
        if not TEMPLATES_DIR.exists():
            return
            
        templates = sorted([f.name for f in TEMPLATES_DIR.iterdir() 
                           if f.suffix.lower() in ('.png', '.jpg', '.jpeg')])
        
        for template in templates:
            self.template_list.insert(tk.END, template)
            
    def _on_template_select(self, event=None):
        """Handle template selection."""
        selection = self.template_list.curselection()
        if not selection:
            return
            
        template_name = self.template_list.get(selection[0])
        self.selected_template = template_name
        
        template_path = TEMPLATES_DIR / template_name
        
        # Try to show preview
        try:
            from PIL import Image, ImageTk
            img = Image.open(template_path)
            orig_w, orig_h = img.size
            
            # Scale down if too large
            max_size = (200, 150)
            img.thumbnail(max_size)
            
            self.template_preview_img = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.template_preview_img, text="")
            
            # Update info
            self.info_label.config(text=f"Name: {template_name}\nSize: {orig_w}x{orig_h}px\nPath: {template_path}")
            
        except Exception as e:
            self.preview_label.config(image="", text=f"Cannot preview: {e}")
            self.info_label.config(text=f"Name: {template_name}\nPath: {template_path}")
            
    def _delete_template(self):
        """Delete the selected template."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template to delete.")
            return
            
        if messagebox.askyesno("Confirm", f"Delete template '{self.selected_template}'?"):
            template_path = TEMPLATES_DIR / self.selected_template
            try:
                template_path.unlink()
                self.refresh_templates()
                self.preview_label.config(image="", text="Select a template to preview")
                self.info_label.config(text="No template selected")
                self.selected_template = None
                self.app.log_message(f"Deleted template: {self.selected_template}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")
                
    def _test_find_template(self):
        """Test finding the selected template on screen."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template first.")
            return
            
        self.app.log_message(f"Testing template find: {self.selected_template}")
        
        def test_thread():
            try:
                from xiswalker.visual import VisualMatcher
                matcher = VisualMatcher(TEMPLATES_DIR)
                
                # Try to find on full screen
                result = matcher.find_template_with_retry(
                    self.selected_template,
                    max_attempts=1,
                    roi=None,  # Full screen
                    threshold=0.8
                )
                
                if result.found:
                    self.app.log_message(f"✓ Template found at ({result.x}, {result.y}) "
                                        f"confidence: {result.confidence:.2f}")
                else:
                    self.app.log_message(f"✗ Template not found (confidence: {result.confidence:.2f})")
                    
            except Exception as e:
                self.app.log_message(f"Error testing template: {e}")
                
        threading.Thread(target=test_thread, daemon=True).start()
        
    def _pick_offset(self):
        """Pick offset by clicking on screen."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template first.")
            return
            
        messagebox.showinfo("Pick Offset", 
            "After closing this dialog, you have 3 seconds to position your mouse "
            "at the desired click location relative to where the template would be found.\n\n"
            "The offset will be calculated from the template's top-left corner.")
            
        def pick_thread():
            import time
            from pynput.mouse import Controller
            
            time.sleep(3)
            mouse = Controller()
            x, y = mouse.position
            
            # We need to know where the template would be found to calculate offset
            # For now, just store the absolute position - user can adjust
            self.offset_x.delete(0, tk.END)
            self.offset_x.insert(0, str(x))
            self.offset_y.delete(0, tk.END)
            self.offset_y.insert(0, str(y))
            
            self.app.log_message(f"Picked position: ({x}, {y}) - "
                                f"adjust relative to template top-left if needed")
            
        threading.Thread(target=pick_thread, daemon=True).start()
        
    def _create_mission(self, mission_type):
        """Create a mission file."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template first.")
            return
            
        mission_name = self.mission_name.get().strip()
        if not mission_name:
            messagebox.showwarning("Warning", "Please enter a mission name.")
            return
            
        # Ensure atomic directory exists
        ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
        
        mission_path = ATOMIC_DIR / f"{mission_name}.jsonl"
        
        try:
            if mission_type == "find":
                # Create template_find mission
                event = {
                    "timestamp": 0.0,
                    "type": "template_find",
                    "template": self.selected_template,
                    "threshold": 0.8,
                    "retry": 3,
                    "abort_on_fail": True
                }
            else:  # click
                # Create relative_click mission
                try:
                    offset_x = int(self.offset_x.get())
                    offset_y = int(self.offset_y.get())
                except ValueError:
                    messagebox.showerror("Error", "Offset X and Y must be integers.")
                    return
                    
                event = {
                    "timestamp": 0.0,
                    "type": "relative_click",
                    "template": self.selected_template,
                    "offset_x": offset_x,
                    "offset_y": offset_y,
                    "threshold": 0.8,
                    "retry": 3
                }
                
            # Write the mission
            import json
            with open(mission_path, "w") as f:
                f.write(json.dumps(event) + "\n")
                
            self.app.log_message(f"Created mission: {mission_path}")
            messagebox.showinfo("Success", f"Mission '{mission_name}' created!")
            
            # Refresh dashboard if available
            if hasattr(self.app, 'tab_dashboard'):
                self.app.tab_dashboard.refresh_missions()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create mission: {e}")
            
    def _create_finder_mission(self):
        """Create a full-screen template finder mission."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template first.")
            return
            
        mission_name = self.mission_name.get().strip()
        if not mission_name:
            # Auto-generate name
            base_name = Path(self.selected_template).stem
            mission_name = f"find_{base_name}"
            self.mission_name.delete(0, tk.END)
            self.mission_name.insert(0, mission_name)
            
        # Ensure atomic directory exists
        ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
        
        mission_path = ATOMIC_DIR / f"{mission_name}.jsonl"
        
        try:
            # Create a template_find event (full screen, no ROI)
            event = {
                "timestamp": 0.0,
                "type": "template_find",
                "template": self.selected_template,
                "roi": None,  # Full screen search
                "threshold": 0.8,
                "retry": 3,
                "abort_on_fail": True
            }
            
            import json
            with open(mission_path, "w") as f:
                f.write(json.dumps(event) + "\n")
                
            self.app.log_message(f"Created finder mission: {mission_path}")
            messagebox.showinfo("Success", 
                f"Finder mission '{mission_name}' created!\n\n"
                f"This mission will:\n"
                f"1. Search the entire screen for '{self.selected_template}'\n"
                f"2. Try up to 3 times with 1-second delays\n"
                f"3. Abort if not found\n\n"
                f"Use this as a building block for composite missions.")
            
            if hasattr(self.app, 'tab_dashboard'):
                self.app.tab_dashboard.refresh_missions()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create mission: {e}")
