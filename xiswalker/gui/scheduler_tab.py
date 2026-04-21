"""Scheduler tab for XisWalker GUI.

Shows configured schedules from config/schedule.yaml and a live view
of the executor queue (pending / running jobs). Provides Start/Stop Daemon,
Add/Remove schedule, and manual Run Now controls.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import yaml

from xiswalker.models import MissionPriority, parse_schedules_yaml


_SCHEDULE_YAML = Path("config/schedule.yaml")
_POLL_INTERVAL_MS = 1000  # Queue status refresh interval
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class SchedulerTab(ttk.Frame):
    """Scheduler & Queue management tab."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Daemon state
        self._daemon_thread: threading.Thread | None = None
        self._daemon_stop = threading.Event()

        # Shared executor — created on first daemon start, reused for Run Now
        self._executor = None

        # Tracks {eid: (mission, type, priority)} for queue polling
        self._tracked: dict = {}

        self._create_widgets()
        self._refresh_schedules()
        self._poll_queue()

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _create_widgets(self):
        # ── Configured Schedules ──────────────────────────────────────
        sched_frame = ttk.LabelFrame(self, text="Configured Schedules (config/schedule.yaml)")
        sched_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 2))

        cols = ("Name", "Composite", "Time / Interval", "Days", "Priority", "Repeat", "Jitter (s)")
        self.tree_schedules = ttk.Treeview(sched_frame, columns=cols, show="headings", height=5)
        for col in cols:
            self.tree_schedules.heading(col, text=col)
        self.tree_schedules.column("Name", width=110)
        self.tree_schedules.column("Composite", width=130)
        self.tree_schedules.column("Time / Interval", width=100)
        self.tree_schedules.column("Days", width=120)
        self.tree_schedules.column("Priority", width=75)
        self.tree_schedules.column("Repeat", width=55)
        self.tree_schedules.column("Jitter (s)", width=70)
        self.tree_schedules.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        sb_sched = ttk.Scrollbar(sched_frame, orient="vertical", command=self.tree_schedules.yview)
        sb_sched.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_schedules.configure(yscrollcommand=sb_sched.set)

        # ── Schedule action buttons ────────────────────────────────────
        btn_sched_frame = ttk.Frame(self)
        btn_sched_frame.pack(fill=tk.X, padx=10, pady=2)

        ttk.Button(btn_sched_frame, text="Refresh", command=self._refresh_schedules).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_sched_frame, text="Run Now (selected)", command=self._run_now).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_sched_frame, text="Remove Selected", command=self._remove_selected).pack(side=tk.LEFT, padx=4)

        # ── Add Schedule form ─────────────────────────────────────────
        add_frame = ttk.LabelFrame(self, text="Add Schedule")
        add_frame.pack(fill=tk.X, padx=10, pady=2)

        # Row 1: Name, Composite, Priority, Repeat
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, padx=8, pady=(6, 2))

        ttk.Label(row1, text="Name:").pack(side=tk.LEFT)
        self.ent_name = ttk.Entry(row1, width=14)
        self.ent_name.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(row1, text="Composite:").pack(side=tk.LEFT)
        self.cmb_composite = ttk.Combobox(row1, width=18, state="readonly")
        self.cmb_composite.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Button(row1, text="⟳", width=2, command=self._refresh_composites).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text="Priority:").pack(side=tk.LEFT)
        self.cmb_priority = ttk.Combobox(row1, values=["NORMAL", "INTERRUPT"], width=9, state="readonly")
        self.cmb_priority.current(0)
        self.cmb_priority.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(row1, text="Repeat:").pack(side=tk.LEFT)
        self.ent_repeat = ttk.Entry(row1, width=4)
        self.ent_repeat.insert(0, "1")
        self.ent_repeat.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(row1, text="Jitter (s):").pack(side=tk.LEFT)
        self.ent_jitter = ttk.Entry(row1, width=5)
        self.ent_jitter.insert(0, "0")
        self.ent_jitter.pack(side=tk.LEFT, padx=(2, 0))

        # Row 2: Trigger type toggle
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, padx=8, pady=2)

        self.var_trigger = tk.StringVar(value="time")
        ttk.Radiobutton(row2, text="At time:", variable=self.var_trigger,
                        value="time", command=self._on_trigger_toggle).pack(side=tk.LEFT)

        self.ent_time = ttk.Entry(row2, width=7)
        self.ent_time.insert(0, "HH:MM")
        self.ent_time.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(row2, text="Days:").pack(side=tk.LEFT)
        self._day_vars = {}
        for d in _DAYS:
            v = tk.BooleanVar(value=False)
            self._day_vars[d] = v
            ttk.Checkbutton(row2, text=d, variable=v).pack(side=tk.LEFT)

        # Row 3: Interval trigger (hidden initially via state)
        row3 = ttk.Frame(add_frame)
        row3.pack(fill=tk.X, padx=8, pady=(2, 6))

        self.rb_interval = ttk.Radiobutton(row3, text="Every (minutes):", variable=self.var_trigger,
                                           value="interval", command=self._on_trigger_toggle)
        self.rb_interval.pack(side=tk.LEFT)
        self.ent_interval = ttk.Entry(row3, width=6, state=tk.DISABLED)
        self.ent_interval.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Button(row3, text="Add Schedule", command=self._add_schedule).pack(side=tk.RIGHT, padx=4)

        # ── Daemon controls ───────────────────────────────────────────
        daemon_frame = ttk.LabelFrame(self, text="Daemon")
        daemon_frame.pack(fill=tk.X, padx=10, pady=2)

        self.lbl_daemon_status = ttk.Label(daemon_frame, text="Status: Stopped")
        self.lbl_daemon_status.pack(side=tk.LEFT, padx=10, pady=6)

        self.btn_start_daemon = ttk.Button(daemon_frame, text="Start Daemon", command=self._start_daemon)
        self.btn_start_daemon.pack(side=tk.LEFT, padx=4)

        self.btn_stop_daemon = ttk.Button(daemon_frame, text="Stop Daemon", command=self._stop_daemon, state=tk.DISABLED)
        self.btn_stop_daemon.pack(side=tk.LEFT, padx=4)

        # ── Live Queue ────────────────────────────────────────────────
        queue_frame = ttk.LabelFrame(self, text="Live Executor Queue")
        queue_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        qcols = ("Execution ID", "Mission", "Type", "Priority", "Status", "Enqueued At")
        self.tree_queue = ttk.Treeview(queue_frame, columns=qcols, show="headings", height=4)
        for col in qcols:
            self.tree_queue.heading(col, text=col)
        self.tree_queue.column("Execution ID", width=240)
        self.tree_queue.column("Mission", width=130)
        self.tree_queue.column("Type", width=75)
        self.tree_queue.column("Priority", width=75)
        self.tree_queue.column("Status", width=80)
        self.tree_queue.column("Enqueued At", width=140)
        self.tree_queue.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        sb_q = ttk.Scrollbar(queue_frame, orient="vertical", command=self.tree_queue.yview)
        sb_q.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_queue.configure(yscrollcommand=sb_q.set)

        # Queue action buttons
        stop_frame = ttk.Frame(self)
        stop_frame.pack(fill=tk.X, padx=10, pady=(2, 8))

        ttk.Button(stop_frame, text="⛔ Stop All", command=self._stop_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(stop_frame, text="Clear Finished", command=self._clear_finished).pack(side=tk.RIGHT, padx=4)

        # Populate composite dropdown on first load
        self._refresh_composites()

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _on_trigger_toggle(self):
        """Enable/disable time vs interval fields based on radio selection."""
        if self.var_trigger.get() == "time":
            self.ent_time.config(state=tk.NORMAL)
            self.ent_interval.config(state=tk.DISABLED)
        else:
            self.ent_time.config(state=tk.DISABLED)
            self.ent_interval.config(state=tk.NORMAL)

    def _refresh_composites(self):
        """Populate the composite combobox from missions/composite/."""
        composite_dir = Path("missions/composite")
        names = sorted(p.stem for p in composite_dir.glob("*.yaml")) if composite_dir.exists() else []
        self.cmb_composite["values"] = names
        if names and not self.cmb_composite.get():
            self.cmb_composite.current(0)

    # ------------------------------------------------------------------
    # Schedule list
    # ------------------------------------------------------------------

    def _refresh_schedules(self):
        """Reload schedule.yaml and repopulate the treeview."""
        for row in self.tree_schedules.get_children():
            self.tree_schedules.delete(row)

        tasks = parse_schedules_yaml(str(_SCHEDULE_YAML))
        if not tasks:
            self.tree_schedules.insert("", tk.END, values=("(no schedules configured)", "", "", "", "", ""))
            return

        for t in tasks:
            if t.repeat_every_minutes is not None:
                time_str = f"every {t.repeat_every_minutes} min"
                days_str = "—"
            else:
                time_str = t.time or "—"
                days_str = ", ".join(t.days) if t.days else "Everyday"

            priority_str = getattr(t, "priority", "NORMAL")
            if hasattr(priority_str, "name"):
                priority_str = priority_str.name

            repeat_str = str(t.repeat) if t.repeat > 1 else "—"
            jitter_str = str(t.jitter_seconds) if t.jitter_seconds else "\u2014"
            self.tree_schedules.insert("", tk.END, values=(
                t.name, t.composite, time_str, days_str, priority_str, repeat_str, jitter_str,
            ))

    # ------------------------------------------------------------------
    # Add / Remove schedules
    # ------------------------------------------------------------------

    def _add_schedule(self):
        """Validate form and append a new entry to schedule.yaml."""
        name = self.ent_name.get().strip()
        composite = self.cmb_composite.get().strip()
        priority = self.cmb_priority.get().strip() or "NORMAL"

        try:
            repeat = int(self.ent_repeat.get().strip())
            if repeat < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Validation", "Repeat must be a positive integer.")
            return

        try:
            jitter = int(self.ent_jitter.get().strip())
            if jitter < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Validation", "Jitter must be 0 or a positive integer (seconds).")
            return

        if not name:
            messagebox.showwarning("Validation", "Name is required.")
            return
        if not composite:
            messagebox.showwarning("Validation", "Select a composite mission.")
            return

        entry: dict = {"name": name, "composite": composite, "priority": priority}
        if repeat > 1:
            entry["repeat"] = repeat
        if jitter > 0:
            entry["jitter_seconds"] = jitter

        if self.var_trigger.get() == "interval":
            try:
                minutes = int(self.ent_interval.get().strip())
                if minutes < 1:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Validation", "Interval must be a positive integer (minutes).")
                return
            entry["repeat_every_minutes"] = minutes
        else:
            time_val = self.ent_time.get().strip()
            # Basic HH:MM validation
            parts = time_val.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                messagebox.showwarning("Validation", "Time must be in HH:MM format.")
                return
            entry["time"] = time_val
            selected_days = [d for d in _DAYS if self._day_vars[d].get()]
            if selected_days:
                entry["days"] = selected_days

        self._write_schedule_entry(entry)
        self._refresh_schedules()
        self.app.log_message(f"[Scheduler] Added schedule '{name}'.")

        # Clear name field for next entry
        self.ent_name.delete(0, tk.END)

    def _write_schedule_entry(self, entry: dict):
        """Append entry to schedule.yaml, preserving existing entries."""
        _SCHEDULE_YAML.parent.mkdir(parents=True, exist_ok=True)

        # Load raw data (ignore parse errors — file may have only comments)
        data = {}
        if _SCHEDULE_YAML.exists():
            try:
                with open(_SCHEDULE_YAML, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                data = {}

        schedules = data.get("schedules") or []
        if not isinstance(schedules, list):
            schedules = []
        schedules.append(entry)

        with open(_SCHEDULE_YAML, "w", encoding="utf-8") as f:
            yaml.dump({"schedules": schedules}, f, sort_keys=False, allow_unicode=True)

    def _remove_selected(self):
        """Remove the selected schedule from schedule.yaml."""
        sel = self.tree_schedules.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a schedule row to remove.")
            return

        row_vals = self.tree_schedules.item(sel[0])["values"]
        if not row_vals or str(row_vals[0]).startswith("("):
            return

        name_to_remove = str(row_vals[0])

        if not messagebox.askyesno("Confirm", f"Remove schedule '{name_to_remove}'?"):
            return

        # Load, filter, save
        data = {}
        if _SCHEDULE_YAML.exists():
            try:
                with open(_SCHEDULE_YAML, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                data = {}

        schedules = data.get("schedules") or []
        if isinstance(schedules, list):
            schedules = [s for s in schedules if s.get("name") != name_to_remove]

        with open(_SCHEDULE_YAML, "w", encoding="utf-8") as f:
            yaml.dump({"schedules": schedules or None}, f, sort_keys=False, allow_unicode=True)

        self._refresh_schedules()
        self.app.log_message(f"[Scheduler] Removed schedule '{name_to_remove}'.")

    # ------------------------------------------------------------------
    # Run Now
    # ------------------------------------------------------------------

    def _run_now(self):
        """Enqueue the currently selected schedule's composite immediately."""
        sel = self.tree_schedules.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a schedule row first.")
            return

        row = self.tree_schedules.item(sel[0])["values"]
        if not row or str(row[0]).startswith("("):
            return

        composite_name = str(row[1])
        priority_str = str(row[4]).upper()
        priority = MissionPriority.INTERRUPT if priority_str == "INTERRUPT" else MissionPriority.NORMAL

        executor = self._get_or_create_executor()
        eid = executor.enqueue(composite_name, priority, "composite", 0.0)
        self._track_execution(eid, composite_name, "composite", priority_str)
        self.app.log_message(f"[Scheduler] Enqueued '{composite_name}' (id={eid[:8]}…)")

    # ------------------------------------------------------------------
    # Daemon
    # ------------------------------------------------------------------

    def _start_daemon(self):
        if self._daemon_thread and self._daemon_thread.is_alive():
            return

        if not _SCHEDULE_YAML.exists():
            messagebox.showerror("Error", f"Schedule config not found: {_SCHEDULE_YAML}")
            return

        tasks = parse_schedules_yaml(str(_SCHEDULE_YAML))
        if not tasks:
            messagebox.showwarning("No Schedules", "No valid schedules in config/schedule.yaml.")
            return

        self._daemon_stop.clear()
        executor = self._get_or_create_executor()

        def _run():
            import schedule as schedule_lib
            from xiswalker.scheduler import setup_schedule, SchedulerController
            import time

            controller = SchedulerController(executor, log_fn=self.app.log_message)
            setup_schedule(tasks, controller)
            self.app.log_message("[Daemon] Started.")

            while not self._daemon_stop.is_set():
                schedule_lib.run_pending()
                time.sleep(1)

            schedule_lib.clear()
            self.app.log_message("[Daemon] Stopped.")

        self._daemon_thread = threading.Thread(target=_run, daemon=True, name="GUIDaemon")
        self._daemon_thread.start()

        self.lbl_daemon_status.config(text="Status: Running")
        self.btn_start_daemon.config(state=tk.DISABLED)
        self.btn_stop_daemon.config(state=tk.NORMAL)

    def _stop_daemon(self):
        self._daemon_stop.set()
        self.lbl_daemon_status.config(text="Status: Stopped")
        self.btn_start_daemon.config(state=tk.NORMAL)
        self.btn_stop_daemon.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Executor & tracking
    # ------------------------------------------------------------------

    def _get_or_create_executor(self):
        if self._executor is None:
            from xiswalker.executor import ExecutorQueue
            self._executor = ExecutorQueue()
        return self._executor

    def _track_execution(self, eid: str, mission: str, mtype: str, priority: str):
        self._tracked[eid] = (mission, mtype, priority)
        enqueued_at = ""
        if self._executor is not None:
            enqueued_at = self._executor.list_executions().get(eid, {}).get("enqueued_at", "")
        self.tree_queue.insert("", 0, iid=eid, values=(eid, mission, mtype, priority, "pending", enqueued_at))

    # ------------------------------------------------------------------
    # Queue polling
    # ------------------------------------------------------------------

    def _poll_queue(self):
        """Refresh status of tracked jobs and discover daemon-fired jobs every second."""
        if self._executor is not None:
            all_executions = self._executor.list_executions()

            for eid, info in all_executions.items():
                status = info.get("status", "?")
                if eid not in self._tracked:
                    # Auto-discover jobs enqueued by the daemon (not via Run Now)
                    mission = info.get("mission", "?")
                    mtype = info.get("mission_type", "composite")
                    priority = info.get("priority", "NORMAL")
                    self._tracked[eid] = (mission, mtype, priority)
                    enqueued_at = info.get("enqueued_at", "")
                    self.tree_queue.insert("", 0, iid=eid,
                                          values=(eid, mission, mtype, priority, status, enqueued_at))
                else:
                    try:
                        self.tree_queue.set(eid, "Status", status)
                    except tk.TclError:
                        pass

        self.after(_POLL_INTERVAL_MS, self._poll_queue)

    def _clear_finished(self):
        """Remove completed/failed/stopped/cancelled rows from the queue view."""
        terminal = {"success", "failed", "stopped", "cancelled", "not_found"}
        to_remove = [eid for eid in list(self._tracked.keys())
                     if self._executor and self._executor.get_status(eid) in terminal]
        for eid in to_remove:
            try:
                self.tree_queue.delete(eid)
            except tk.TclError:
                pass
            self._tracked.pop(eid, None)

    def _stop_all(self):
        """Drain queue and trigger emergency stop."""
        if self._executor is None:
            return
        self._executor.abort_all()
        self.app.log_message("[Scheduler] ⛔ Stop All triggered — queue drained.")
        self._poll_queue()

