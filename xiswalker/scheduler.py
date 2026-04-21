"""Scheduling and automation for XisWalker."""

import random
import time
import schedule
import threading
from typing import List, Optional
from xiswalker.models import parse_schedules_yaml, ScheduleTask, MissionPriority

class SchedulerController:
    """Controller for running and managing scheduled tasks via the ExecutorQueue."""

    def __init__(self, executor: "ExecutorQueue", log_fn=None) -> None:
        self._executor = executor
        self._log = log_fn or print

    def execute_job(self, task: ScheduleTask) -> None:
        """Enqueue a scheduled task into the executor queue, with optional jitter."""
        jitter = 0
        if task.jitter_seconds and task.jitter_seconds > 0:
            jitter = random.randint(0, task.jitter_seconds)
        if jitter:
            self._log(f"[Scheduler] '{task.name}' will start in {jitter}s (jitter)")
            time.sleep(jitter)
        self._log(f"[Scheduler] '{task.name}' enqueued at {time.strftime('%H:%M:%S')}")
        self._executor.enqueue(task.composite, task.priority)
                
def setup_schedule(tasks: List[ScheduleTask], controller: SchedulerController) -> None:
    """Register all tasks with the schedule library.
    Pure function to wrap logic around schedule parsing.
    """
    schedule.clear()

    for task in tasks:
        # repeat_every_minutes takes precedence over time/days scheduling
        if task.repeat_every_minutes is not None:
            schedule.every(task.repeat_every_minutes).minutes.do(controller.execute_job, task)
            continue

        job = None
        if not task.days:
            # Everyday if no days provided
            job = schedule.every().day.at(task.time)
            job.do(controller.execute_job, task)
        else:
            # Specific days
            for day in task.days:
                day_clean = day.lower().strip()
                if day_clean == "mon":
                    job = schedule.every().monday.at(task.time)
                elif day_clean == "tue":
                    job = schedule.every().tuesday.at(task.time)
                elif day_clean == "wed":
                    job = schedule.every().wednesday.at(task.time)
                elif day_clean == "thu":
                    job = schedule.every().thursday.at(task.time)
                elif day_clean == "fri":
                    job = schedule.every().friday.at(task.time)
                elif day_clean == "sat":
                    job = schedule.every().saturday.at(task.time)
                elif day_clean == "sun":
                    job = schedule.every().sunday.at(task.time)
                else:
                    print(f"⚠️ Unknown day '{day}' for task '{task.name}'")
                    continue
                job.do(controller.execute_job, task)

def start_daemon(config_path: str, executor: Optional["ExecutorQueue"] = None) -> None:
    """Run the scheduler daemon."""
    from xiswalker.executor import ExecutorQueue

    print(f"\U0001f680 Starting XisWalker Daemon with config: {config_path}")
    tasks = parse_schedules_yaml(config_path)
    if not tasks:
        print("\u26a0\ufe0f No valid schedules found.")
        return

    if executor is None:
        executor = ExecutorQueue()

    controller = SchedulerController(executor)
    setup_schedule(tasks, controller)
    
    print("\n📋 Active Schedules:")
    list_schedules(config_path)
    print("\n⏳ Daemon running. Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ Daemon stopped.")

def run_at(time_str: str, composite: str) -> None:
    """Schedule a one-off run at a specific time today."""
    from xiswalker.executor import ExecutorQueue
    print(f"⏰ Scheduling '{composite}' to run at {time_str}")
    executor = ExecutorQueue()
    controller = SchedulerController(executor)
    task = ScheduleTask(name="one-off", composite=composite, time=time_str, days=[])
    schedule.every().day.at(time_str).do(controller.execute_job, task).tag('one-off')
    
    try:
        while True:
            schedule.run_pending()
            if not schedule.get_jobs('one-off'):
                break # completed
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ Cancelled one-off schedule.")

def list_schedules(config_path: str):
    """List all configured schedules."""
    tasks = parse_schedules_yaml(config_path)
    if not tasks:
        print("No schedules configured.")
        return
        
    for idx, t in enumerate(tasks, 1):
        days_str = ", ".join(t.days) if t.days else "Everyday"
        rep_str = f", Repeat: {t.repeat}x" if t.repeat > 1 else ""
        print(f"  {idx}. {t.name} -> {t.composite} | {t.time} on {days_str}{rep_str}")
