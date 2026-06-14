"""Visual Step Dialog for creating image-based conditional steps."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

TEMPLATES_DIR = Path("missions/templates")
ATOMIC_DIR = Path("missions/atomic")


class VisualStepDialog(tk.Toplevel):
    """Dialog for creating a visual conditional step."""
    
    def __init__(self, parent, app, initial_data=None):
        super().__init__(parent)
        self.app = app
        self.result = None
        self.initial_data = initial_data
        
        self.title("Edit Visual Conditional Step" if initial_data else "Create Visual Conditional Step")
        self.geometry("900x600")
        self.minsize(800, 500)
        
        # Variables
        self.selected_template = None
        self.preview_image = None
        self.click_x = tk.IntVar(value=0)
        self.click_y = tk.IntVar(value=0)
        self.threshold = tk.DoubleVar(value=0.8)
        self.timeout = tk.DoubleVar(value=5.0)
        self.scale_factor = 1.0
        self.orig_width = 0
        self.orig_height = 0
        
        self._create_widgets()
        self._refresh_templates()
        self._refresh_atomics()
        
        if self.initial_data:
            self._load_initial_data()
            
        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
    def _create_widgets(self):
        """Create the dialog widgets with left/right split layout."""
        # Main container with padding
        main_container = ttk.Frame(self, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_container.columnconfigure(0, weight=1)  # Left panel (controls)
        main_container.columnconfigure(1, weight=2)  # Right panel (image)
        main_container.rowconfigure(0, weight=1)
        
        # LEFT PANEL - Controls
        left_panel = ttk.Frame(main_container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_panel.rowconfigure(5, weight=1)  # Make bottom area expandable
        
        # 1. Template Selection
        template_frame = ttk.LabelFrame(left_panel, text="1. Select Template")
        template_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(template_frame, text="Template:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.cmb_template = ttk.Combobox(template_frame, state="readonly")
        self.cmb_template.pack(fill=tk.X, padx=5, pady=5)
        self.cmb_template.bind("<<ComboboxSelected>>", self._on_template_select)
        
        ttk.Button(template_frame, text="Refresh List", command=self._refresh_templates).pack(anchor=tk.E, padx=5, pady=5)
        
        # 2. Action Point (coordinates)
        coord_frame = ttk.LabelFrame(left_panel, text="2. Click Point on Image")
        coord_frame.pack(fill=tk.X, pady=(0, 10))
        
        coord_inputs = ttk.Frame(coord_frame)
        coord_inputs.pack(padx=5, pady=5)
        
        ttk.Label(coord_inputs, text="X:").pack(side=tk.LEFT)
        self.ent_x = ttk.Entry(coord_inputs, width=6, textvariable=self.click_x)
        self.ent_x.pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(coord_inputs, text="Y:").pack(side=tk.LEFT)
        self.ent_y = ttk.Entry(coord_inputs, width=6, textvariable=self.click_y)
        self.ent_y.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(coord_frame, text="(relative to top-left)", font=("Segoe UI", 8)).pack(pady=(0, 5))
        
        # 3. If Found
        found_frame = ttk.LabelFrame(left_panel, text="3. If Template IS Found")
        found_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(found_frame, text="Execute Atomic:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        found_c_frame = ttk.Frame(found_frame)
        found_c_frame.pack(fill=tk.X, padx=5, pady=5)
        self.cmb_on_found = ttk.Combobox(found_c_frame, state="readonly")
        self.cmb_on_found.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(found_c_frame, text="+ New", width=6, command=lambda: self._create_new_atomic(self.cmb_on_found)).pack(side=tk.LEFT, padx=(5, 0))
        
        # 4. If Not Found
        not_found_frame = ttk.LabelFrame(left_panel, text="4. If Template NOT Found")
        not_found_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(not_found_frame, text="Execute Atomic (optional):").pack(anchor=tk.W, padx=5, pady=(5, 0))
        not_found_c_frame = ttk.Frame(not_found_frame)
        not_found_c_frame.pack(fill=tk.X, padx=5, pady=5)
        self.cmb_on_not_found = ttk.Combobox(not_found_c_frame, state="readonly")
        self.cmb_on_not_found.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(not_found_c_frame, text="+ New", width=6, command=lambda: self._create_new_atomic(self.cmb_on_not_found)).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Label(not_found_frame, text="Otherwise:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.var_on_fail = tk.StringVar(value="skip")
        ttk.Radiobutton(not_found_frame, text="Skip step", variable=self.var_on_fail, value="skip").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(not_found_frame, text="Abort mission", variable=self.var_on_fail, value="abort").pack(anchor=tk.W, padx=5)
        
        # 5. Advanced Settings
        advanced_frame = ttk.LabelFrame(left_panel, text="5. Advanced")
        advanced_frame.pack(fill=tk.X, pady=(0, 10))
        
        adv_grid = ttk.Frame(advanced_frame)
        adv_grid.pack(padx=5, pady=5)
        
        ttk.Label(adv_grid, text="Threshold:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(adv_grid, from_=0.5, to=1.0, increment=0.05, textvariable=self.threshold, width=6).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(adv_grid, text="Timeout (s):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(adv_grid, from_=1.0, to=30.0, increment=1.0, textvariable=self.timeout, width=6).grid(row=1, column=1, padx=5, pady=2)
        
        # Buttons at bottom of left panel
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        btn_text = "Update Step" if self.initial_data else "Add to Mission"
        ttk.Button(btn_frame, text=btn_text, command=self._on_confirm).pack(side=tk.RIGHT, padx=5)
        
        # RIGHT PANEL - Image Preview
        right_panel = ttk.LabelFrame(main_container, text="Click on Image to Set Action Point")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)
        
        # Canvas with scrollbar support
        canvas_container = ttk.Frame(right_panel)
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(
            canvas_container, 
            bg="#2b2b2b",
            highlightthickness=1,
            highlightbackground="#555"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbars for canvas
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        
        h_scroll = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Bind click event
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        # Hint label at bottom
        hint = "Click on the image to set where the action should be performed."
        ttk.Label(right_panel, text=hint, font=("Segoe UI", 9), foreground="gray").pack(pady=5)
        
    def _refresh_templates(self):
        """Refresh the template dropdown."""
        templates = []
        if TEMPLATES_DIR.exists():
            templates = sorted([f.name for f in TEMPLATES_DIR.iterdir() 
                               if f.suffix.lower() in ('.png', '.jpg', '.jpeg')])
        
        self.cmb_template['values'] = templates
        if templates:
            self.cmb_template.set(templates[0])
            self._on_template_select()
            
    def _refresh_atomics(self):
        """Refresh atomic mission dropdowns."""
        atomics = []
        if ATOMIC_DIR.exists():
            atomics = sorted([p.stem for p in ATOMIC_DIR.glob("*.jsonl")])
        
        self.cmb_on_found['values'] = [
            "(None - just click at point)",
            "(None - just double click at point)",
            "(None - just right click at point)",
        ] + atomics
        self.cmb_on_not_found['values'] = ["(None)"] + atomics

        self.cmb_on_found.set("(None - just click at point)")
        self.cmb_on_not_found.set("(None)")
        
    def _load_initial_data(self):
        """Populate the dialog with initial data."""
        data = self.initial_data
        if "visual_condition" in data:
            self.cmb_template.set(data["visual_condition"])
            self._on_template_select()
            
        if "visual_threshold" in data and data["visual_threshold"] is not None:
            self.threshold.set(data["visual_threshold"])
        if "visual_timeout" in data and data["visual_timeout"] is not None:
            self.timeout.set(data["visual_timeout"])
            
        if "visual_click_x" in data and data["visual_click_x"] is not None:
            self.click_x.set(data["visual_click_x"])
        if "visual_click_y" in data and data["visual_click_y"] is not None:
            self.click_y.set(data["visual_click_y"])
            self._draw_click_marker()
            
        if "on_fail" in data:
            self.var_on_fail.set(data["on_fail"])
            
        if "on_found" in data and data["on_found"] is not None:
            self.cmb_on_found.set(data["on_found"])
        elif data.get("visual_click_type") == "double":
            self.cmb_on_found.set("(None - just double click at point)")
        elif data.get("visual_click_type") == "right":
            self.cmb_on_found.set("(None - just right click at point)")
        else:
            self.cmb_on_found.set("(None - just click at point)")
            
        if "on_not_found" in data and data["on_not_found"] is not None:
            self.cmb_on_not_found.set(data["on_not_found"])
        else:
            self.cmb_on_not_found.set("(None)")
        
    def _on_template_select(self, event=None):
        """Handle template selection - load and display image."""
        template_name = self.cmb_template.get()
        if not template_name:
            return
            
        self.selected_template = template_name
        template_path = TEMPLATES_DIR / template_name
        
        try:
            from PIL import Image, ImageTk
            
            # Load image
            img = Image.open(template_path)
            orig_w, orig_h = img.size
            
            # Scale down if too large (max 600x500 for display)
            max_w, max_h = 600, 500
            scale = min(max_w / orig_w, max_h / orig_h, 1.0)
            
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            
            if scale < 1.0:
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.preview_image = ImageTk.PhotoImage(img)
            
            # Update canvas
            self.canvas.delete("all")
            self.canvas.config(width=new_w, height=new_h)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_image)
            
            # Update scroll region
            self.canvas.config(scrollregion=(0, 0, new_w, new_h))
            
            # Store scale factor for coordinate conversion
            self.scale_factor = scale
            self.orig_width = orig_w
            self.orig_height = orig_h
            
            # Reset click point to center
            self.click_x.set(orig_w // 2)
            self.click_y.set(orig_h // 2)
            self._draw_click_marker()
            
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(
                200, 150, 
                text=f"Cannot load image:\n{e}",
                fill="white",
                justify=tk.CENTER
            )
            
    def _on_canvas_click(self, event):
        """Handle click on canvas - set action point."""
        if not self.selected_template:
            return
        
        # Get canvas coordinates considering scroll
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
            
        # Convert to original image coordinates
        orig_x = int(x / self.scale_factor)
        orig_y = int(y / self.scale_factor)
        
        # Clamp to image bounds
        orig_x = max(0, min(orig_x, self.orig_width))
        orig_y = max(0, min(orig_y, self.orig_height))
        
        self.click_x.set(orig_x)
        self.click_y.set(orig_y)
        
        self._draw_click_marker()
        
    def _draw_click_marker(self):
        """Draw a marker on the canvas showing the click point."""
        if not self.selected_template:
            return
            
        # Remove old marker
        self.canvas.delete("marker")
        
        # Calculate canvas coordinates
        canvas_x = int(self.click_x.get() * self.scale_factor)
        canvas_y = int(self.click_y.get() * self.scale_factor)
        
        # Draw crosshair
        size = 10
        self.canvas.create_line(
            canvas_x - size, canvas_y, canvas_x + size, canvas_y,
            fill="red", width=2, tags="marker"
        )
        self.canvas.create_line(
            canvas_x, canvas_y - size, canvas_x, canvas_y + size,
            fill="red", width=2, tags="marker"
        )
        
        # Draw circle
        self.canvas.create_oval(
            canvas_x - 5, canvas_y - 5, canvas_x + 5, canvas_y + 5,
            outline="red", width=2, tags="marker"
        )
        
    def _create_new_atomic(self, combobox):
        from tkinter import simpledialog, messagebox
        import threading
        
        name = simpledialog.askstring("New Atomic", "Enter a name for the new atomic mission:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
            
        if name.endswith(".jsonl"):
            name = name[:-6]
            
        filepath = ATOMIC_DIR / f"{name}.jsonl"
        if filepath.exists():
            messagebox.showerror("Error", f"Atomic mission '{name}' already exists.")
            return
            
        # Hide the dialog and app so the user can interact with the desktop
        self.grab_release()
        self.withdraw()
        if hasattr(self, 'app') and self.app:
            self.app.withdraw()
            
        self.app.log_message(f"Starting recording of atomic mission '{name}'...")
        
        def _run_record():
            try:
                from xiswalker.recorder import record_mission
                record_mission(name, visual=False)
                self.after(0, lambda: _record_done(None))
            except Exception as e:
                self.after(0, lambda: _record_done(e))
                
        def _record_done(error):
            if hasattr(self, 'app') and self.app:
                self.app.deiconify()
            
            self.deiconify()
            self.lift()
            self.attributes('-topmost', True)
            
            def _restore_state():
                self.attributes('-topmost', False)
                self.focus_force()
                self.grab_set()
                
                if error:
                    messagebox.showerror("Error", f"Failed to record atomic:\n{error}")
                else:
                    self._refresh_atomics()
                    combobox.set(name)
                    self.app.log_message(f"Successfully recorded new atomic: {name}")
                    if hasattr(self.app, 'tab_dashboard'):
                        self.app.tab_dashboard.refresh_missions()
                        
            self.after(200, _restore_state)

        threading.Thread(target=_run_record, daemon=True).start()

    def _on_confirm(self):
        """Handle confirm button - build step dict."""
        if not self.selected_template:
            messagebox.showwarning("Warning", "Please select a template.")
            return
            
        # Build step dict
        step = {
            "visual_condition": self.selected_template,
            "visual_threshold": self.threshold.get(),
            "visual_timeout": self.timeout.get(),
            "visual_click_x": self.click_x.get(),
            "visual_click_y": self.click_y.get(),
            "on_fail": self.var_on_fail.get()
        }
        
        # Add on_found / visual_click_type based on selection
        on_found = self.cmb_on_found.get()
        if on_found == "(None - just double click at point)":
            step["visual_click_type"] = "double"
        elif on_found == "(None - just right click at point)":
            step["visual_click_type"] = "right"
        elif on_found and on_found not in (
            "(None - just click at point)",
            "(None - just double click at point)",
            "(None - just right click at point)",
        ):
            step["on_found"] = on_found
            
        # Add on_not_found if selected
        on_not_found = self.cmb_on_not_found.get()
        if on_not_found and on_not_found != "(None)":
            step["on_not_found"] = on_not_found
            
        self.result = step
        self.destroy()
