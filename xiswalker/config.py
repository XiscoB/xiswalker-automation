"""Global configuration management for XisWalker."""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass
class SafetyConfig:
    check_window_focus: bool = True
    window_patterns: List[str] = field(default_factory=lambda: [
        "XisWalker", "Windows PowerShell", "Command Prompt", "cmd"
    ])


@dataclass
class InputConfig:
    """Configuration for input controls including stop keys."""
    # Key to stop recording (default: ESC)
    recording_stop_key: str = "esc"
    # Key combination to stop playback (format: "ctrl+shift+end")
    playback_stop_key: str = "ctrl+shift+end"
    # Show overlay during recording/playback
    show_overlay: bool = True


@dataclass
class AppConfig:
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    input: InputConfig = field(default_factory=InputConfig)
    ocr: "OcrConfig" = field(default_factory=lambda: OcrConfig())


@dataclass
class OcrConfig:
    backend: str = "ollama"                        # "pytesseract" | "ollama"
    ollama_model: str = "blaifa/nanonets-ocr-s:latest"  # Ollama model name
    ollama_url: str = "http://localhost:11434"


def _get_default_config() -> dict:
    """Get the default configuration dictionary."""
    return {
        "safety": {
            "check_window_focus": True,
            "window_patterns": [
                "XisWalker", "Windows PowerShell", "Command Prompt", "cmd"
            ]
        },
        "input": {
            "recording_stop_key": "esc",
            "playback_stop_key": "ctrl+shift+end",
            "show_overlay": True
        }
    }


def load_config() -> AppConfig:
    """Load global configuration, creating defaults if missing."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        default_config = _get_default_config()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, sort_keys=False)
        return AppConfig()
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        safety_data = data.get("safety", {})
        safety_config = SafetyConfig(
            check_window_focus=safety_data.get("check_window_focus", True),
            window_patterns=safety_data.get("window_patterns", [
                "XisWalker", "Windows PowerShell", "Command Prompt", "cmd"
            ])
        )
        
        input_data = data.get("input", {})
        input_config = InputConfig(
            recording_stop_key=input_data.get("recording_stop_key", "esc"),
            playback_stop_key=input_data.get("playback_stop_key", "ctrl+shift+end"),
            show_overlay=input_data.get("show_overlay", True)
        )

        ocr_data = data.get("ocr", {})
        ocr_config = OcrConfig(
            backend=ocr_data.get("backend", "pytesseract"),
            ollama_model=ocr_data.get("ollama_model", "llava"),
            ollama_url=ocr_data.get("ollama_url", "http://localhost:11434"),
        )
        
        return AppConfig(safety=safety_config, input=input_config, ocr=ocr_config)
    except Exception as e:
        print(f"⚠️ Failed to load config.yaml: {e}. Using defaults.")
        return AppConfig()
