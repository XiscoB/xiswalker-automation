"""Utilities module for mission management and validation."""

import os
from pathlib import Path
from colorama import Fore, Style
import yaml

from xiswalker.models import deserialize_event, parse_composite_yaml

MISSIONS_DIR = Path("missions")
ATOMIC_DIR = MISSIONS_DIR / "atomic"
COMPOSITE_DIR = MISSIONS_DIR / "composite"
TEMPLATES_DIR = MISSIONS_DIR / "templates"


def list_missions() -> None:
    """List all atomic and composite missions."""
    print(f"\n{Fore.CYAN}--- Atomic Missions ---{Style.RESET_ALL}")
    if ATOMIC_DIR.exists():
        atomics = list(ATOMIC_DIR.glob("*.jsonl"))
        if not atomics:
            print(f"{Fore.YELLOW}  (None found){Style.RESET_ALL}")
        for mission in sorted(atomics):
            print(f"  {Fore.GREEN}•{Style.RESET_ALL} {mission.stem}")
    else:
        print(f"{Fore.YELLOW}  (Directory missions/atomic not found){Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}--- Composite Missions ---{Style.RESET_ALL}")
    if COMPOSITE_DIR.exists():
        composites = list(COMPOSITE_DIR.glob("*.yaml"))
        if not composites:
            print(f"{Fore.YELLOW}  (None found){Style.RESET_ALL}")
        for mission in sorted(composites):
            print(f"  {Fore.GREEN}•{Style.RESET_ALL} {mission.stem}")
    else:
        print(f"{Fore.YELLOW}  (Directory missions/composite not found){Style.RESET_ALL}")
    print()


def mission_info(mission_type: str, name: str) -> None:
    """Print information about a mission.
    
    Args:
        mission_type: "atomic" or "composite"
        name: Name of the mission
    """
    if mission_type == "atomic":
        path = ATOMIC_DIR / f"{name}.jsonl"
        if not path.exists():
            print(f"{Fore.RED}❌ Atomic mission not found: {path}{Style.RESET_ALL}")
            return
            
        events = []
        templates = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ev = deserialize_event(line.strip())
                    events.append(ev)
                    if ev.template:
                        templates.add(ev.template)
                        
        duration = events[-1].timestamp if events else 0.0
        print(f"\n{Fore.CYAN}ℹ️  Atomic Mission Info: {name}{Style.RESET_ALL}")
        print(f"  Duration:      {duration:.2f}s")
        print(f"  Event Count:   {len(events)}")
        if templates:
            print(f"  Templates:     {', '.join(templates)}")
        else:
            print(f"  Templates:     None")
            
    elif mission_type == "composite":
        path = COMPOSITE_DIR / f"{name}.yaml"
        if not path.exists():
            print(f"{Fore.RED}❌ Composite mission not found: {path}{Style.RESET_ALL}")
            return
            
        mission = parse_composite_yaml(path)
        print(f"\n{Fore.CYAN}ℹ️  Composite Mission Info: {name}{Style.RESET_ALL}")
        print(f"  Description:   {mission.description}")
        print(f"  Grace Period:  {mission.grace_period}s")
        print(f"  Steps Count:   {len(mission.steps)}")
        
        total_wait = 0.0
        atomic_deps = set()
        for step in mission.steps:
            if step.wait is not None:
                total_wait += step.wait
            if step.mission:
                atomic_deps.add(step.mission)
                
        print(f"  Total Wait:    {total_wait:.2f}s")
        print(f"  Dependencies:  {', '.join(atomic_deps) if atomic_deps else 'None'}")
    print()


def validate_mission(mission_type: str, name: str) -> None:
    """Validate mission JSONL integrity and template existence."""
    print(f"\n{Fore.CYAN}🔍 Validating {mission_type} mission: {name}{Style.RESET_ALL}")
    
    errors = 0
    warnings = 0
    
    if mission_type == "atomic":
        path = ATOMIC_DIR / f"{name}.jsonl"
        if not path.exists():
            print(f"  {Fore.RED}❌ Mission file missing.{Style.RESET_ALL}")
            return
            
        with open(path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    ev = deserialize_event(line.strip())
                    if ev.type == "visual_click" and ev.template:
                        template_path = TEMPLATES_DIR / ev.template
                        if not template_path.exists():
                            print(f"  {Fore.RED}❌ Line {line_idx}: Missing template image '{ev.template}'{Style.RESET_ALL}")
                            errors += 1
                except Exception as e:
                    print(f"  {Fore.RED}❌ Line {line_idx}: Invalid JSON or event format ({e}){Style.RESET_ALL}")
                    errors += 1
                    
    elif mission_type == "composite":
        path = COMPOSITE_DIR / f"{name}.yaml"
        if not path.exists():
            print(f"  {Fore.RED}❌ Mission file missing.{Style.RESET_ALL}")
            return
            
        try:
            mission = parse_composite_yaml(path)
            for i, step in enumerate(mission.steps, 1):
                if step.mission:
                    atomic_path = ATOMIC_DIR / f"{step.mission}.jsonl"
                    if not atomic_path.exists():
                        print(f"  {Fore.RED}❌ Step {i}: Missing atomic dependency '{step.mission}'{Style.RESET_ALL}")
                        errors += 1
        except Exception as e:
            print(f"  {Fore.RED}❌ Failed to parse YAML: {e}{Style.RESET_ALL}")
            errors += 1
            
    if errors == 0:
        print(f"  {Fore.GREEN}✅ Validation passed! No issues found.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.RED}❌ Validation failed with {errors} errors.{Style.RESET_ALL}")
    print()


def edit_composite(name: str, action: str, **kwargs) -> None:
    """Add or remove steps from a composite mission.
    
    Args:
        name: Composite mission name.
        action: 'add' or 'remove'
        kwargs: Contains 'mission', 'wait' for add; 'index' for remove.
    """
    path = COMPOSITE_DIR / f"{name}.yaml"
    if not path.exists():
        print(f"{Fore.RED}❌ Composite mission not found: {path}{Style.RESET_ALL}")
        return
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not isinstance(data, dict) or "steps" not in data:
        print(f"{Fore.RED}❌ Invalid composite file format.{Style.RESET_ALL}")
        return
        
    if action == "add":
        new_step = {}
        if kwargs.get("mission"):
            new_step["mission"] = kwargs["mission"]
            new_step["atomic"] = True
        elif kwargs.get("wait") is not None:
            new_step["wait"] = float(kwargs["wait"])
        else:
            print(f"{Fore.RED}❌ Must specify mission or wait to add.{Style.RESET_ALL}")
            return
            
        data["steps"].append(new_step)
        print(f"{Fore.GREEN}✅ Added step to {name}.{Style.RESET_ALL}")
        
    elif action == "remove":
        index = kwargs.get("index")
        if index is None or not (1 <= index <= len(data["steps"])):
            print(f"{Fore.RED}❌ Invalid step index.{Style.RESET_ALL}")
            return
        removed = data["steps"].pop(index - 1)
        print(f"{Fore.GREEN}✅ Removed step {index}: {removed}{Style.RESET_ALL}")
        
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False)
