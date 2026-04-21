"""Exporter and importer for XisWalker missions with base64 templates."""

import json
import base64
import os
import subprocess
from pathlib import Path
from colorama import Fore, Style

from xiswalker.models import parse_composite_yaml

MISSIONS_DIR = Path("missions")
ATOMIC_DIR = MISSIONS_DIR / "atomic"
COMPOSITE_DIR = MISSIONS_DIR / "composite"
TEMPLATES_DIR = MISSIONS_DIR / "templates"


def _encode_template(name: str) -> str:
    """Read a template PNG and return base64 string."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _decode_template(name: str, b64_str: str) -> None:
    """Decode base64 string and write to template PNG."""
    if not b64_str:
        return
    path = TEMPLATES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_str))


def export_mission(mission_type: str, name: str, to_clipboard: bool = False) -> None:
    """Export a mission, resolving dependencies and nesting templates."""
    export_data = {
        "export_version": 1,
        "type": mission_type,
        "name": name,
        "atomics": {},
        "composites": {},
        "templates": {}
    }

    templates_needed = set()
    atomics_needed = set()

    if mission_type == "composite":
        path = COMPOSITE_DIR / f"{name}.yaml"
        if not path.exists():
            print(f"{Fore.RED}❌ Composite missing: {path}{Style.RESET_ALL}")
            return
        with open(path, "r", encoding="utf-8") as f:
            export_data["composites"][name] = f.read()

        # Gather atomic dependencies
        mission = parse_composite_yaml(path)
        for step in mission.steps:
            if step.mission:
                atomics_needed.add(step.mission)
    else:
        atomics_needed.add(name)

    for atomic in atomics_needed:
        path = ATOMIC_DIR / f"{atomic}.jsonl"
        if not path.exists():
            print(f"{Fore.YELLOW}⚠️  Missing atomic dependency {atomic}{Style.RESET_ALL}")
            continue
            
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            export_data["atomics"][atomic] = content
            
            # Find template dependencies in the raw content naive search
            for line in content.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "visual_click" and data.get("template"):
                        templates_needed.add(data["template"])
                except Exception:
                    pass

    for temp in templates_needed:
        b64 = _encode_template(temp)
        if b64:
            export_data["templates"][temp] = b64
        else:
            print(f"{Fore.YELLOW}⚠️  Missing template {temp}{Style.RESET_ALL}")

    json_str = json.dumps(export_data, indent=2)

    if to_clipboard:
        try:
            # Use PowerShell to ensure Unicode clipboard copy
            subprocess.run(["powershell", "-c", "Set-Clipboard -Value $input"], input=json_str.encode("utf-8"), check=True)
            print(f"{Fore.GREEN}✅ Mission '{name}' exported to clipboard.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to copy to clipboard: {e}{Style.RESET_ALL}")
    else:
        out_file = f"{name}_export.json"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"{Fore.GREEN}✅ Mission '{name}' exported to {out_file}.{Style.RESET_ALL}")


def import_mission(filepath_or_json: str) -> None:
    """Import a bundled JSON mission export.
    Can be a filepath or raw JSON string.
    """
    try:
        if filepath_or_json.strip().startswith("{"):
            data = json.loads(filepath_or_json)
        else:
            path = Path(filepath_or_json)
            if not path.exists():
                print(f"{Fore.RED}❌ Export file not found: {path}{Style.RESET_ALL}")
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
        if data.get("export_version") != 1:
            print(f"{Fore.RED}❌ Unknown export version.{Style.RESET_ALL}")
            return
            
        ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
        COMPOSITE_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        
        for name, content in data.get("atomics", {}).items():
            path = ATOMIC_DIR / f"{name}.jsonl"
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
                
        for name, content in data.get("composites", {}).items():
            path = COMPOSITE_DIR / f"{name}.yaml"
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
                
        for name, b64_str in data.get("templates", {}).items():
            _decode_template(name, b64_str)
            
        print(f"{Fore.GREEN}✅ Successfully imported {data.get('type')} mission '{data.get('name')}'.")
        print(f"  Atomcis: {len(data.get('atomics', {}))} | Composites: {len(data.get('composites', {}))} | Templates: {len(data.get('templates', {}))}{Style.RESET_ALL}")
        
    except json.JSONDecodeError:
        print(f"{Fore.RED}❌ Invalid JSON format.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ Import failed: {e}{Style.RESET_ALL}")
