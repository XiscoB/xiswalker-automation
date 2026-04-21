# XisWalker — Screen-Driven UI Validation Engine

Python framework for automated visual validation of desktop and emulator interfaces. Combines computer vision (OpenCV), dual OCR backends (classical + local LLM vision), and priority-based mission scheduling to enable unattended UI testing and verification workflows without requiring DOM or API access.

## Overview

XisWalker validates application states by detecting visual elements on screen, extracting text via OCR, and executing conditional verification sequences. Designed for scenarios where traditional test automation (Selenium, Playwright) is unavailable — native Windows applications, emulators, remote desktops, or legacy systems.

## Key Capabilities

- **Visual Template Matching** — OpenCV `matchTemplate` with ROI cropping, configurable thresholds, and retry logic
- **Dual OCR Backend** — Classical OCR via Tesseract + LLM-powered vision OCR via local Ollama models
- **Conditional Mission Logic** — Branch on visual findings (`on_found` / `on_not_found`), OCR text assertions, and timer-based waits
- **Priority Scheduling** — Heap-based execution queue with cooperative preemption; `INTERRUPT` missions yield over `NORMAL` jobs with automatic resume
- **Safety Layer** — Window focus verification, global emergency stop, Gaussian humanization variance, and guaranteed input release on abort
- **Native GUI** — tkinter desktop interface for mission composition, template capture, and real-time monitoring
- **Headless CLI** — Full feature set available via command line for CI/CD integration

## Architecture

```
CLI / GUI
    ↓
Scheduler → Executor Queue (priority heap)
    ↓
Safety Layer (focus check, emergency stop, humanization)
    ↓
Player → Visual Matcher (OpenCV) + OCR Engine (Tesseract / Ollama)
```

- Serial single-worker execution with preemption support
- Thread-safe GUI communication via `queue.Queue`
- All OS-dependent code isolated behind safety context managers

## Tech Stack

**Core:** Python · OpenCV · Pillow · pytesseract · Ollama (REST API) · tkinter  
**Infrastructure:** schedule · colorama · tqdm · PyInstaller  
**Patterns:** Priority queue threading · Cooperative preemption · Template matching · Fuzzy string matching

## Usage Example

```bash
# Record an atomic interaction sequence
xiswalker record --name login_sequence

# Capture a visual template for validation
xiswalker capture-template --name submit_button

# Compose a conditional verification mission
xiswalker compose --name verify_login

# Execute with safety checks enabled
xiswalker play --mission verify_login --humanize 0.3 --guardian
```

## Project Status

Functional prototype with core record-playback, visual matching, OCR integration, and scheduling subsystems operational. Actively extended for emulator-based UI testing workflows.

## License

MIT
