"""OCR Timer Step Dialog — read a timer from the screen and schedule a mission."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

ATOMIC_DIR = Path("missions/atomic")
COMPOSITE_DIR = Path("missions/composite")


class OcrTimerDialog(tk.Toplevel):
    """Dialog for creating a timer-OCR composite step.

    At runtime this step:
      1. OCRs a screen region to extract a timer string (e.g. "1h. 21min.")
      2. Parses it to seconds
      3. Waits that duration (interruptible by emergency stop)
      4. Executes a chosen atomic mission
      5. Optionally loops: re-scans the region and reschedules
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.result = None

        self.title("Create Timer OCR Step (Read & Wait for Timer)")
        self.geometry("560x600")
        self.minsize(500, 540)
        self.resizable(True, True)

        # ---- Variables ----
        self.var_roi_x = tk.StringVar()
        self.var_roi_y = tk.StringVar()
        self.var_roi_w = tk.StringVar()
        self.var_roi_h = tk.StringVar()
        self.var_backend = tk.StringVar(value="ollama")
        self.var_model = tk.StringVar(value="blaifa/nanonets-ocr-s:latest")
        self.var_loop = tk.BooleanVar(value=False)
        self.var_pre_scan_delay = tk.DoubleVar(value=0.0)
        self.var_recheck_delay = tk.DoubleVar(value=10.0)
        self.var_on_fail = tk.StringVar(value="skip")

        self._create_widgets()
        self._refresh_missions()
        self._on_backend_change()
        self._on_loop_toggle()

        self.transient(parent)
        self.grab_set()
        self.focus_set()

    # keep old name as alias so existing callers don't break
    def _refresh_atomics(self):
        self._refresh_missions()

    def _create_widgets(self):
        outer = ttk.Frame(self, padding="10")
        outer.pack(fill=tk.BOTH, expand=True)

        # 1. Screen region
        roi_frame = ttk.LabelFrame(outer, text="1. Screen Region Containing the Timer (required)")
        roi_frame.pack(fill=tk.X, pady=(0, 8))

        rg = ttk.Frame(roi_frame)
        rg.pack(padx=5, pady=5)
        for col, (lbl, var) in enumerate(
            [("X:", self.var_roi_x), ("Y:", self.var_roi_y),
             ("W:", self.var_roi_w), ("H:", self.var_roi_h)]
        ):
            ttk.Label(rg, text=lbl).grid(row=0, column=col * 2, sticky=tk.W, padx=(8 if col else 0, 0))
            ttk.Entry(rg, textvariable=var, width=7).grid(
                row=0, column=col * 2 + 1, padx=(2, 6), pady=3
            )

        ttk.Button(
            rg, text="📷 Capture Region", command=self._capture_region,
        ).grid(row=1, column=0, columnspan=8, pady=(2, 4))

        self.lbl_capture_status = ttk.Label(rg, text="", font=("Segoe UI", 8), foreground="gray")
        self.lbl_capture_status.grid(row=2, column=0, columnspan=8, pady=(0, 2))

        pre_row = ttk.Frame(roi_frame)
        pre_row.pack(anchor=tk.W, padx=5, pady=(0, 5))
        ttk.Label(pre_row, text="Initial delay before first scan:").pack(side=tk.LEFT)
        ttk.Spinbox(
            pre_row, from_=0.0, to=300.0, increment=1.0,
            textvariable=self.var_pre_scan_delay, width=7,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(pre_row, text="seconds  (0 = scan immediately)").pack(side=tk.LEFT)

        ttk.Label(
            roi_frame,
            text='The region must contain text matching patterns like "1h. 21min.", "45min", "01:21:30" etc.',
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 2. OCR engine
        engine_frame = ttk.LabelFrame(outer, text="2. OCR Engine")
        engine_frame.pack(fill=tk.X, pady=(0, 8))

        eg = ttk.Frame(engine_frame)
        eg.pack(padx=5, pady=5)

        ttk.Label(eg, text="Backend:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cmb_backend = ttk.Combobox(
            eg, textvariable=self.var_backend,
            values=["pytesseract", "ollama"],
            state="readonly", width=18,
        )
        self.cmb_backend.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        self.cmb_backend.bind("<<ComboboxSelected>>", lambda _: self._on_backend_change())

        ttk.Label(eg, text="Ollama model:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_model = ttk.Entry(eg, textvariable=self.var_model, width=20)
        self.ent_model.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)

        # 3. On expire
        expire_frame = ttk.LabelFrame(outer, text="3. When Timer Expires — Execute Mission")
        expire_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(expire_frame, text="Mission to run:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.cmb_on_expire = ttk.Combobox(expire_frame, state="readonly")
        self.cmb_on_expire.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(
            expire_frame,
            text="atomic:name  or  composite:name  — use composite: to re-run this same YAML",
            font=("Segoe UI", 8), foreground="gray",
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # 4. Loop
        loop_frame = ttk.LabelFrame(outer, text="4. Loop (Reschedule After Each Run)")
        loop_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Checkbutton(
            loop_frame, text="Repeat: re-scan timer and reschedule after atomic runs",
            variable=self.var_loop, command=self._on_loop_toggle,
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))

        delay_row = ttk.Frame(loop_frame)
        delay_row.pack(anchor=tk.W, padx=5, pady=(3, 8))
        ttk.Label(delay_row, text="Wait before re-scanning:").pack(side=tk.LEFT)
        self.spn_recheck = ttk.Spinbox(
            delay_row, from_=1.0, to=120.0, increment=1.0,
            textvariable=self.var_recheck_delay, width=7,
        )
        self.spn_recheck.pack(side=tk.LEFT, padx=5)
        ttk.Label(delay_row, text="seconds").pack(side=tk.LEFT)

        # 5. If no timer found
        fail_frame = ttk.LabelFrame(outer, text="5. If No Timer Found in Region")
        fail_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Radiobutton(
            fail_frame, text="Skip step", variable=self.var_on_fail, value="skip"
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        ttk.Radiobutton(
            fail_frame, text="Abort mission", variable=self.var_on_fail, value="abort"
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # Buttons
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_row, text="Add to Mission", command=self._on_confirm).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------
    # Region capture helpers
    # ------------------------------------------------------------------

    def _capture_region(self) -> None:
        """Hide all windows, show a hint overlay, let user click-drag, then restore."""
        import threading
        from pynput import mouse

        # Hide main window + this dialog so the screen is clear
        self.withdraw()
        if self.app and hasattr(self.app, "withdraw"):
            self.app.withdraw()

        # Small always-on-top hint so the user knows what to do
        hint = tk.Toplevel()
        hint.overrideredirect(True)
        hint.attributes("-topmost", True)
        hint.attributes("-alpha", 0.85)
        sw = hint.winfo_screenwidth()
        hint.geometry(f"+{sw // 2 - 180}+8")
        tk.Label(
            hint,
            text="  Click and drag to select the timer region  ",
            font=("Segoe UI", 11, "bold"),
            bg="#1e88e5", fg="white", padx=12, pady=8,
        ).pack()
        hint.update()

        def run() -> None:
            start: list = []
            end: list = []

            def on_click(x: int, y: int, button, pressed: bool):
                if button == mouse.Button.left:
                    if pressed:
                        start.clear()
                        start.append((x, y))
                    else:
                        end.clear()
                        end.append((x, y))
                        return False  # stop listener

            with mouse.Listener(on_click=on_click) as listener:
                listener.join()

            if start and end:
                sx, sy = start[0]
                ex, ey = end[0]
                x = int(min(sx, ex))
                y = int(min(sy, ey))
                w = int(abs(ex - sx))
                h = int(abs(ey - sy))
                self.after(0, lambda: self._apply_captured_roi(x, y, w, h, hint))
            else:
                self.after(0, lambda: self._capture_cancelled(hint))

        threading.Thread(target=run, daemon=True).start()

    def _apply_captured_roi(self, x: int, y: int, w: int, h: int, hint=None) -> None:
        if hint:
            try:
                hint.destroy()
            except Exception:
                pass
        self.var_roi_x.set(str(x))
        self.var_roi_y.set(str(y))
        self.var_roi_w.set(str(w))
        self.var_roi_h.set(str(h))
        self.lbl_capture_status.configure(
            text=f"✓ Captured: X={x}  Y={y}  W={w}  H={h}",
            foreground="#4caf50",
        )
        self._restore_dialog()

    def _capture_cancelled(self, hint=None) -> None:
        if hint:
            try:
                hint.destroy()
            except Exception:
                pass
        self.lbl_capture_status.configure(
            text="✗ Capture cancelled — try again",
            foreground="#e57373",
        )
        self._restore_dialog()

    def _restore_dialog(self) -> None:
        if self.app and hasattr(self.app, "deiconify"):
            self.app.deiconify()
        self.deiconify()
        self.lift()
        self.focus_set()

    def _on_backend_change(self):
        state = "normal" if self.var_backend.get() == "ollama" else "disabled"
        self.ent_model.configure(state=state)

    def _on_loop_toggle(self):
        state = "normal" if self.var_loop.get() else "disabled"
        self.spn_recheck.configure(state=state)

    def _refresh_missions(self):
        entries = []
        if ATOMIC_DIR.exists():
            entries += [f"atomic:{p.stem}" for p in sorted(ATOMIC_DIR.glob("*.jsonl"))]
        if COMPOSITE_DIR.exists():
            entries += [f"composite:{p.stem}" for p in sorted(COMPOSITE_DIR.glob("*.yaml"))]
        self.cmb_on_expire["values"] = ["(None — just wait)"] + entries
        self.cmb_on_expire.set("(None — just wait)")

    def _parse_roi(self):
        vals = [self.var_roi_x.get(), self.var_roi_y.get(),
                self.var_roi_w.get(), self.var_roi_h.get()]
        if any(v.strip() == "" for v in vals):
            return None
        try:
            return [int(v) for v in vals]
        except ValueError:
            return None

    def _on_confirm(self):
        roi = self._parse_roi()
        if roi is None:
            messagebox.showwarning(
                "Warning",
                "Please fill in all four ROI fields (X, Y, W, H).\n"
                "The region must contain the timer text on screen."
            )
            return

        step = {
            "ocr_timer": True,
            "ocr_roi": roi,
            "ocr_backend": self.var_backend.get(),
            "on_fail": self.var_on_fail.get(),
        }

        pre_delay = round(self.var_pre_scan_delay.get(), 1)
        if pre_delay > 0:
            step["ocr_timer_pre_scan_delay"] = pre_delay

        if self.var_backend.get() == "ollama":
            model = self.var_model.get().strip()
            if model:
                step["ocr_model"] = model

        on_expire = self.cmb_on_expire.get().strip()
        if on_expire and on_expire != "(None — just wait)":
            step["timer_on_expire"] = on_expire

        if self.var_loop.get():
            step["timer_loop"] = True
            step["timer_loop_recheck_delay"] = round(self.var_recheck_delay.get(), 1)

        self.result = step
        self.destroy()
