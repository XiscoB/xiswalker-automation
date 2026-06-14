"""OCR Step Dialog for creating text-detection conditional steps."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

ATOMIC_DIR = Path("missions/atomic")


class OcrStepDialog(tk.Toplevel):
    """Dialog for creating an OCR conditional step (text detection on screen)."""

    def __init__(self, parent, app, initial_data: dict = None):
        super().__init__(parent)
        self.app = app
        self.result = None
        self.initial_data = initial_data

        if self.initial_data:
            self.title("Edit OCR Conditional Step")
        else:
            self.title("Create OCR Conditional Step (Text Detection)")
            
        self.geometry("800x520")
        self.minsize(700, 480)
        self.resizable(True, True)

        # ---- Variables ----
        self.var_target_text = tk.StringVar()
        self.var_backend = tk.StringVar(value="ollama")
        self.var_model = tk.StringVar(value="blaifa/nanonets-ocr-s:latest")
        self.var_case_sensitive = tk.BooleanVar(value=False)
        self.var_partial_match = tk.BooleanVar(value=False)
        self.var_threshold = tk.DoubleVar(value=0.8)
        self.var_timeout = tk.DoubleVar(value=5.0)
        self.var_roi_x = tk.StringVar(value="")
        self.var_roi_y = tk.StringVar(value="")
        self.var_roi_w = tk.StringVar(value="")
        self.var_roi_h = tk.StringVar(value="")
        self.var_offset_x = tk.IntVar(value=0)
        self.var_offset_y = tk.IntVar(value=0)
        self.var_on_fail = tk.StringVar(value="skip")
        self.var_capture_right_click = tk.BooleanVar(value=False)

        self._create_widgets()
        self._refresh_atomics()
        
        if self.initial_data:
            self._load_initial_data()
            
        self._on_backend_change()

        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()

    def _create_widgets(self):
        outer = ttk.Frame(self, padding="10")
        outer.pack(fill=tk.BOTH, expand=True)

        content = ttk.Frame(outer)
        content.pack(fill=tk.BOTH, expand=True)
        
        left_col = ttk.Frame(content)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_col = ttk.Frame(content)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # 1. Target text (LEFT)
        text_frame = ttk.LabelFrame(left_col, text="1. Text to Find")
        text_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(text_frame, text="Text:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        ttk.Entry(text_frame, textvariable=self.var_target_text).pack(
            fill=tk.X, padx=5, pady=5
        )
        
        opts_frame = ttk.Frame(text_frame)
        opts_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Checkbutton(
            opts_frame, text="Case sensitive", variable=self.var_case_sensitive
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            opts_frame, text="Partial match (substring)", variable=self.var_partial_match
        ).pack(side=tk.LEFT)

        # 2. Backend (LEFT)
        backend_frame = ttk.LabelFrame(left_col, text="2. OCR Engine")
        backend_frame.pack(fill=tk.X, pady=(0, 8))

        bg = ttk.Frame(backend_frame)
        bg.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(bg, text="Backend:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cmb_backend = ttk.Combobox(
            bg,
            textvariable=self.var_backend,
            values=["pytesseract", "ollama"],
            state="readonly",
            width=18,
        )
        self.cmb_backend.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        self.cmb_backend.bind("<<ComboboxSelected>>", lambda _: self._on_backend_change())

        ttk.Label(bg, text="Ollama model:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_model = ttk.Entry(bg, textvariable=self.var_model, width=20)
        self.ent_model.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)

        ttk.Label(
            backend_frame,
            text="(model used for ollama)",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 3. Search region (ROI) (LEFT)
        roi_frame = ttk.LabelFrame(left_col, text="3. Search Region (blank = full screen)")
        roi_frame.pack(fill=tk.X, pady=(0, 8))

        rg = ttk.Frame(roi_frame)
        rg.pack(padx=5, pady=5)

        for col, (lbl, var) in enumerate(
            [("X:", self.var_roi_x), ("Y:", self.var_roi_y),
             ("W:", self.var_roi_w), ("H:", self.var_roi_h)]
        ):
            ttk.Label(rg, text=lbl).grid(row=0, column=col * 2, sticky=tk.W, padx=(8 if col else 0, 0))
            ttk.Entry(rg, textvariable=var, width=5).grid(
                row=0, column=col * 2 + 1, padx=(2, 4), pady=2
            )
            
        btn_frame = ttk.Frame(roi_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Checkbutton(
            btn_frame, text="Right-Click Drag", variable=self.var_capture_right_click
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, text="Interactive Selection", command=self.start_interactive_selection
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, text="Test OCR", command=self.test_ocr
        ).pack(side=tk.LEFT, padx=5)

        # 4. Advanced (LEFT)
        adv_frame = ttk.LabelFrame(left_col, text="4. Advanced")
        adv_frame.pack(fill=tk.X, pady=(0, 8))

        ag = ttk.Frame(adv_frame)
        ag.pack(padx=5, pady=5)

        ttk.Label(ag, text="Threshold:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(ag, from_=0.3, to=1.0, increment=0.05, textvariable=self.var_threshold, width=7).grid(
            row=0, column=1, padx=5, pady=2
        )

        ttk.Label(ag, text="Timeout (s):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(ag, from_=1.0, to=60.0, increment=1.0, textvariable=self.var_timeout, width=7).grid(
            row=1, column=1, padx=5, pady=2
        )

        ttk.Label(ag, text="Click offset X:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ag, textvariable=self.var_offset_x, width=7).grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(ag, text="Click offset Y:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ag, textvariable=self.var_offset_y, width=7).grid(row=3, column=1, padx=5, pady=2)

        # 5. If found (RIGHT)
        found_frame = ttk.LabelFrame(right_col, text="5. If Text IS Found")
        found_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(found_frame, text="Execute atomic (optional):").pack(
            anchor=tk.W, padx=5, pady=(5, 0)
        )
        found_c_frame = ttk.Frame(found_frame)
        found_c_frame.pack(fill=tk.X, padx=5, pady=5)
        self.cmb_on_found = ttk.Combobox(found_c_frame, state="readonly")
        self.cmb_on_found.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(found_c_frame, text="+ New", width=6, command=lambda: self._create_new_atomic(self.cmb_on_found)).pack(side=tk.LEFT, padx=(5, 0))

        # 6. If not found (RIGHT)
        not_found_frame = ttk.LabelFrame(right_col, text="6. If Text NOT Found")
        not_found_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(not_found_frame, text="Execute atomic (optional):").pack(
            anchor=tk.W, padx=5, pady=(5, 0)
        )
        not_found_c_frame = ttk.Frame(not_found_frame)
        not_found_c_frame.pack(fill=tk.X, padx=5, pady=5)
        self.cmb_on_not_found = ttk.Combobox(not_found_c_frame, state="readonly")
        self.cmb_on_not_found.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(not_found_c_frame, text="+ New", width=6, command=lambda: self._create_new_atomic(self.cmb_on_not_found)).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(not_found_frame, text="Otherwise:").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(
            not_found_frame, text="Skip step", variable=self.var_on_fail, value="skip"
        ).pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(
            not_found_frame, text="Abort mission", variable=self.var_on_fail, value="abort"
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # Test Result Area (RIGHT)
        self.test_frame = ttk.LabelFrame(right_col, text="OCR Test Result")
        self.test_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        self.txt_test_result = tk.Text(self.test_frame, height=2, width=30, wrap=tk.WORD)
        self.txt_test_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_test_result.insert("1.0", "Click 'Test OCR' to preview text.")
        self.txt_test_result.config(state="disabled", fg="gray")
        
        self.lbl_match_result = ttk.Label(self.test_frame, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_match_result.pack(pady=(0, 5))

        # Bottom buttons
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
        btn_text = "Save Changes" if self.initial_data else "Add to Mission"
        ttk.Button(btn_row, text=btn_text, command=self._on_confirm).pack(side=tk.RIGHT, padx=5)

    def _load_initial_data(self):
        """Populate the dialog with initial data if provided."""
        if not self.initial_data:
            return
            
        self.var_target_text.set(self.initial_data.get("ocr_text", ""))
        self.var_backend.set(self.initial_data.get("ocr_backend", "ollama"))
        self.var_model.set(self.initial_data.get("ocr_model", "blaifa/nanonets-ocr-s:latest"))
        self.var_case_sensitive.set(self.initial_data.get("ocr_case_sensitive", False))
        self.var_partial_match.set(self.initial_data.get("ocr_partial_match", False))
        self.var_threshold.set(self.initial_data.get("ocr_threshold", 0.8))
        self.var_timeout.set(self.initial_data.get("ocr_timeout", 5.0))
        
        roi = self.initial_data.get("ocr_roi")
        if roi and len(roi) == 4:
            self.var_roi_x.set(str(roi[0]))
            self.var_roi_y.set(str(roi[1]))
            self.var_roi_w.set(str(roi[2]))
            self.var_roi_h.set(str(roi[3]))
            
        self.var_offset_x.set(self.initial_data.get("visual_click_x", 0) or 0)
        self.var_offset_y.set(self.initial_data.get("visual_click_y", 0) or 0)
        self.var_on_fail.set(self.initial_data.get("on_fail", "skip"))
        
        on_found = self.initial_data.get("on_found")
        if on_found:
            self.cmb_on_found.set(on_found)
            
        on_not_found = self.initial_data.get("on_not_found")
        if on_not_found:
            self.cmb_on_not_found.set(on_not_found)

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

    def _on_backend_change(self):
        """Enable/disable model entry based on selected backend."""
        if self.var_backend.get() == "ollama":
            self.ent_model.configure(state="normal")
        else:
            self.ent_model.configure(state="disabled")

    def _refresh_atomics(self):
        atomics = []
        if ATOMIC_DIR.exists():
            atomics = sorted([p.stem for p in ATOMIC_DIR.glob("*.jsonl")])

        self.cmb_on_found["values"] = ["(None — just click)"] + atomics
        self.cmb_on_not_found["values"] = ["(None)"] + atomics
        self.cmb_on_found.set("(None — just click)")
        self.cmb_on_not_found.set("(None)")

    def _parse_roi(self):
        """Parse ROI entries; returns list[int] or None if any field is blank."""
        vals = [self.var_roi_x.get(), self.var_roi_y.get(),
                self.var_roi_w.get(), self.var_roi_h.get()]
        if any(v.strip() == "" for v in vals):
            return None
        try:
            return [int(v) for v in vals]
        except ValueError:
            return None

    def _on_confirm(self):
        target = self.var_target_text.get().strip()
        if not target:
            messagebox.showwarning("Warning", "Please enter the text to search for.")
            return

        step = {
            "ocr_text": target,
            "ocr_backend": self.var_backend.get(),
            "ocr_threshold": round(self.var_threshold.get(), 3),
            "ocr_timeout": round(self.var_timeout.get(), 1),
            "ocr_case_sensitive": self.var_case_sensitive.get(),
            "ocr_partial_match": self.var_partial_match.get(),
            "visual_click_x": self.var_offset_x.get(),
            "visual_click_y": self.var_offset_y.get(),
            "on_fail": self.var_on_fail.get(),
        }

        if self.var_backend.get() == "ollama":
            model = self.var_model.get().strip()
            if model:
                step["ocr_model"] = model

        roi = self._parse_roi()
        if roi:
            step["ocr_roi"] = roi

        on_found = self.cmb_on_found.get()
        if on_found and on_found != "(None — just click)":
            step["on_found"] = on_found

        on_not_found = self.cmb_on_not_found.get()
        if on_not_found and on_not_found != "(None)":
            step["on_not_found"] = on_not_found

        self.result = step
        self.destroy()

    def start_interactive_selection(self):
        self.grab_release()
        self.withdraw()
        if hasattr(self.app, 'withdraw'):
            self.app.withdraw()
            
        # Show hint
        hint = tk.Toplevel()
        hint.overrideredirect(True)
        hint.attributes("-topmost", True)
        hint.attributes("-alpha", 0.85)
        sw = hint.winfo_screenwidth()
        hint.geometry(f"+{sw // 2 - 200}+8")
        
        use_right_click = self.var_capture_right_click.get()
        click_type = "Right-click" if use_right_click else "Click"
        tk.Label(
            hint,
            text=f"  {click_type} and drag to select region  ",
            font=("Segoe UI", 11, "bold"),
            bg="#1e88e5", fg="white", padx=12, pady=8,
        ).pack()
        hint.update()

        import threading
        threading.Thread(
            target=self._run_selection_thread,
            args=(hint, use_right_click),
            daemon=True,
        ).start()

    def _run_selection_thread(self, hint, use_right_click):
        from pynput import mouse
        start_pos = None
        end_pos = None
        
        def on_click(x, y, button, pressed):
            nonlocal start_pos, end_pos
            target_btn = mouse.Button.right if use_right_click else mouse.Button.left
            if button == target_btn:
                if pressed:
                    start_pos = (x, y)
                else:
                    if start_pos is None:
                        # Ignore the mouse release from the button click that started this
                        return True
                    end_pos = (x, y)
                    return False
                    
        with mouse.Listener(on_click=on_click) as listener:
            listener.join()
            
        # Process result on main thread
        self.after(0, lambda: self._selection_done(hint, start_pos, end_pos))

    def _selection_done(self, hint, start_pos, end_pos):
        try:
            hint.destroy()
        except:
            pass
        
        if hasattr(self.app, 'deiconify'):
            self.app.deiconify()
            
        self.deiconify()
        self.lift()
        self.attributes('-topmost', True)
        
        def _restore_state():
            self.attributes('-topmost', False)
            self.focus_force()
            self.grab_set()
            
            if start_pos and end_pos:
                x1, int_y1 = start_pos
                x2, int_y2 = end_pos
                x = int(min(x1, x2))
                y = int(min(int_y1, int_y2))
                w = int(abs(x2 - x1))
                h = int(abs(int_y2 - int_y1))
                
                if w >= 5 and h >= 5:
                    self.var_roi_x.set(str(x))
                    self.var_roi_y.set(str(y))
                    self.var_roi_w.set(str(w))
                    self.var_roi_h.set(str(h))
                    
        self.after(200, _restore_state)

    def test_ocr(self):
        roi = self._parse_roi()
        backend = self.var_backend.get()
        model = self.var_model.get().strip()
        target = self.var_target_text.get().strip()
        case_sensitive = self.var_case_sensitive.get()
        partial_match = self.var_partial_match.get()
        threshold = self.var_threshold.get()
        
        self.txt_test_result.config(state="normal", fg="black")
        self.txt_test_result.delete("1.0", tk.END)
        self.txt_test_result.insert("1.0", "Testing OCR... Please wait.")
        self.txt_test_result.config(state="disabled")
        
        self.lbl_match_result.config(text="")
        
        # Hide just this dialog temporarily
        self.grab_release()
        self.withdraw()
            
        import threading
        threading.Thread(
            target=self._run_test_ocr, 
            args=(roi, backend, model, target, case_sensitive, partial_match, threshold), 
            daemon=True
        ).start()

    def _run_test_ocr(self, roi, backend, model, target, case_sensitive, partial_match, threshold):
        import time
        time.sleep(0.5)  # Wait for UI to hide
        
        from xiswalker.ocr import OcrMatcher
        from xiswalker.config import load_config
        
        text = ""
        error = None
        is_match = False
        
        try:
            cfg = load_config()
            matcher = OcrMatcher(ollama_url=cfg.ocr.ollama_url)
            screenshot = matcher._grab(roi)
            
            # Restore GUI immediately since we have the screenshot
            self.after(0, self._restore_gui_after_grab)
            
            if backend == "ollama":
                import base64, io, json, urllib.request
                buf = io.BytesIO()
                screenshot.save(buf, format="PNG")
                image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                
                payload = json.dumps({
                    "model": model,
                    "prompt": "",
                    "images": [image_b64],
                    "stream": False,
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    f"{matcher.ollama_url.rstrip('/')}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                
                from xiswalker.ocr import _clean_ollama_output, fuzzy_ratio
                text = _clean_ollama_output(body.get("response", "").strip())
                
                a = target if case_sensitive else target.lower()
                b_full = text if case_sensitive else text.lower()
                
                if partial_match and a in b_full:
                    is_match = True
                else:
                    for w in text.split():
                        b = w if case_sensitive else w.lower()
                        ratio = 1.0 if (partial_match and a in b) else fuzzy_ratio(a, b)
                        if ratio >= threshold:
                            is_match = True
                            break
            else:
                import pytesseract
                from xiswalker.ocr import fuzzy_ratio
                data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
                words = [w for w in data["text"] if w.strip()]
                text = " ".join(words)
                
                a = target if case_sensitive else target.lower()
                b_full = text if case_sensitive else text.lower()
                
                if partial_match and a in b_full:
                    is_match = True
                else:
                    for w in words:
                        b = w if case_sensitive else w.lower()
                        ratio = 1.0 if (partial_match and a in b) else fuzzy_ratio(a, b)
                        if ratio >= threshold:
                            is_match = True
                            break
        except Exception as e:
            error = str(e)
            
            # Ensure GUI is restored if grab failed
            self.after(0, self._restore_gui_after_grab)
            
        self.after(0, lambda: self._test_ocr_done(text, error, is_match))

    def _restore_gui_after_grab(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(200, lambda: self.grab_set())

    def _test_ocr_done(self, text, error, is_match):
        self.txt_test_result.config(state="normal")
        self.txt_test_result.delete("1.0", tk.END)
        
        if error:
            self.txt_test_result.insert("1.0", f"Error:\n{error}")
            self.txt_test_result.config(fg="red")
            self.lbl_match_result.config(text="Match: ERROR", foreground="red")
        elif not text.strip():
            self.txt_test_result.insert("1.0", "No text detected in the region.")
            self.txt_test_result.config(fg="gray")
            self.lbl_match_result.config(text="Match: FAIL (No text)", foreground="red")
        else:
            self.txt_test_result.insert("1.0", text)
            self.txt_test_result.config(fg="black")
            
            if is_match:
                self.lbl_match_result.config(text="Match: YES (Pass)", foreground="green")
            else:
                self.lbl_match_result.config(text="Match: NO (Fail)", foreground="red")
            
        self.txt_test_result.config(state="disabled")

