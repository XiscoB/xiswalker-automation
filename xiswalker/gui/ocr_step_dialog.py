"""OCR Step Dialog for creating text-detection conditional steps."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

ATOMIC_DIR = Path("missions/atomic")


class OcrStepDialog(tk.Toplevel):
    """Dialog for creating an OCR conditional step (text detection on screen)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.result = None

        self.title("Create OCR Conditional Step (Text Detection)")
        self.geometry("580x620")
        self.minsize(500, 560)
        self.resizable(True, True)

        # ---- Variables ----
        self.var_target_text = tk.StringVar()
        self.var_backend = tk.StringVar(value="ollama")
        self.var_model = tk.StringVar(value="blaifa/nanonets-ocr-s:latest")
        self.var_case_sensitive = tk.BooleanVar(value=False)
        self.var_threshold = tk.DoubleVar(value=0.8)
        self.var_timeout = tk.DoubleVar(value=5.0)
        self.var_roi_x = tk.StringVar(value="")
        self.var_roi_y = tk.StringVar(value="")
        self.var_roi_w = tk.StringVar(value="")
        self.var_roi_h = tk.StringVar(value="")
        self.var_offset_x = tk.IntVar(value=0)
        self.var_offset_y = tk.IntVar(value=0)
        self.var_on_fail = tk.StringVar(value="skip")

        self._create_widgets()
        self._refresh_atomics()
        self._on_backend_change()

        # Make modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()

    def _create_widgets(self):
        outer = ttk.Frame(self, padding="10")
        outer.pack(fill=tk.BOTH, expand=True)

        # 1. Target text
        text_frame = ttk.LabelFrame(outer, text="1. Text to Find")
        text_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(text_frame, text="Text:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        ttk.Entry(text_frame, textvariable=self.var_target_text).pack(
            fill=tk.X, padx=5, pady=5
        )
        ttk.Checkbutton(
            text_frame, text="Case sensitive", variable=self.var_case_sensitive
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 2. Backend
        backend_frame = ttk.LabelFrame(outer, text="2. OCR Engine")
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
            text="(model only used when backend=ollama; requires Ollama running locally)",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 3. Search region (ROI) — optional
        roi_frame = ttk.LabelFrame(outer, text="3. Search Region (optional — leave blank for full screen)")
        roi_frame.pack(fill=tk.X, pady=(0, 8))

        rg = ttk.Frame(roi_frame)
        rg.pack(padx=5, pady=5)

        for col, (lbl, var) in enumerate(
            [("X:", self.var_roi_x), ("Y:", self.var_roi_y),
             ("W:", self.var_roi_w), ("H:", self.var_roi_h)]
        ):
            ttk.Label(rg, text=lbl).grid(row=0, column=col * 2, sticky=tk.W, padx=(8 if col else 0, 0))
            ttk.Entry(rg, textvariable=var, width=7).grid(
                row=0, column=col * 2 + 1, padx=(2, 8), pady=2
            )

        # 4. Advanced
        adv_frame = ttk.LabelFrame(outer, text="4. Advanced")
        adv_frame.pack(fill=tk.X, pady=(0, 8))

        ag = ttk.Frame(adv_frame)
        ag.pack(padx=5, pady=5)

        ttk.Label(ag, text="Threshold (fuzzy ratio):").grid(row=0, column=0, sticky=tk.W, pady=2)
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

        ttk.Label(
            adv_frame,
            text="(offset is relative to top-left of found text; 0,0 = click text center)",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 5. If found
        found_frame = ttk.LabelFrame(outer, text="5. If Text IS Found")
        found_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(found_frame, text="Execute atomic (optional):").pack(
            anchor=tk.W, padx=5, pady=(5, 0)
        )
        self.cmb_on_found = ttk.Combobox(found_frame, state="readonly")
        self.cmb_on_found.pack(fill=tk.X, padx=5, pady=5)

        # 6. If not found
        not_found_frame = ttk.LabelFrame(outer, text="6. If Text NOT Found")
        not_found_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(not_found_frame, text="Execute atomic (optional):").pack(
            anchor=tk.W, padx=5, pady=(5, 0)
        )
        self.cmb_on_not_found = ttk.Combobox(not_found_frame, state="readonly")
        self.cmb_on_not_found.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(not_found_frame, text="Otherwise:").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(
            not_found_frame, text="Skip step", variable=self.var_on_fail, value="skip"
        ).pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(
            not_found_frame, text="Abort mission", variable=self.var_on_fail, value="abort"
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # Bottom buttons
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_row, text="Add to Mission", command=self._on_confirm).pack(side=tk.RIGHT, padx=5)

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
