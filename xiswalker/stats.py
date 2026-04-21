"""Execution statistics tracking module."""

import json
from pathlib import Path
from colorama import Fore, Style
from datetime import datetime

STATS_FILE = Path("missions") / "stats.json"

def _load_stats() -> dict:
    if not STATS_FILE.exists():
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_stats(data: dict) -> None:
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dumps(data)
        json.dump(data, f, indent=2)


def record_execution(mission_type: str, name: str, success: bool, duration: float) -> None:
    """Record a single execution outcome."""
    data = _load_stats()
    key = f"{mission_type}:{name}"
    
    if key not in data:
        data[key] = {
            "attempts": 0,
            "successes": 0,
            "total_duration": 0.0,
            "last_run": None
        }
        
    entry = data[key]
    entry["attempts"] += 1
    if success:
        entry["successes"] += 1
    entry["total_duration"] += duration
    entry["last_run"] = datetime.now().isoformat()
    
    _save_stats(data)


def show_stats() -> None:
    """Print statistics."""
    data = _load_stats()
    if not data:
        print(f"\n{Fore.YELLOW}No statistics recorded yet.{Style.RESET_ALL}")
        return
        
    print(f"\n{Fore.CYAN}📊 Execution Statistics{Style.RESET_ALL}")
    
    for key, stats in data.items():
        m_type, name = key.split(":", 1)
        attempts = stats["attempts"]
        successes = stats["successes"]
        rate = (successes / attempts * 100) if attempts > 0 else 0
        avg_time = stats["total_duration"] / attempts if attempts > 0 else 0
        
        color = Fore.GREEN if rate >= 90 else (Fore.YELLOW if rate >= 50 else Fore.RED)
        
        print(f"\n  {Fore.WHITE}{m_type.upper()}:{name}{Style.RESET_ALL}")
        print(f"    Success Rate: {color}{successes}/{attempts} ({rate:.1f}%){Style.RESET_ALL}")
        print(f"    Avg Duration: {avg_time:.1f}s")
    print()
