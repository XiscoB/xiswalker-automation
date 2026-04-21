# XisWalker — Usage Guide

Before running any `xiswalker` commands, you must **activate the virtual environment**.

## 1. Activate Virtual Environment (Windows)

Open your terminal in the `xiswalker` project directory:

**Using PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Using Command Prompt (cmd):**
```cmd
.\.venv\Scripts\activate.bat
```

*(Note: Once activated, your terminal prompt should start with `(.venv)`)*

## 2. Re-install in Development Mode (Required once)
Since the `xiswalker` executable command config was just added to your `pyproject.toml`, you need to run this command once (while the venv is activated) so it builds the `xiswalker.exe` shim:
```powershell
pip install -e .
```

---

## 3. Available `xiswalker` Commands

### Phase 4: Visual Commands

#### Template Capture
- **Capture a Template Interactively:**
  ```powershell
  xiswalker capture-template target_icon
  ```
  *(Prompts you to click and drag to select an area, saving it as `target_icon.png` in `missions/templates/`)*

#### Template Finding (Full Screen)
- **Find Template Anywhere on Screen:**
  ```powershell
  xiswalker play atomic example_find_dialog_window
  ```
  *(Searches the entire screen for the template, retries 3 times, aborts if not found)*

#### Relative Clicking (Click Within Found Template)
- **Click at Offset Within Template:**
  ```powershell
  xiswalker play atomic example_click_menu_option
  ```
  *(Finds template, then clicks at offset_x, offset_y from its top-left corner)*

#### Visual Checkpoints During Recording
- **Record Atomic Mission with Visual (F8) Support:**
  ```powershell
  xiswalker record atomic click_confirm --visual
  ```
  *(Press `F8` during recording to capture an automatic visual checkpoint around the mouse cursor)*

### Template Mission Format Examples

**Find Template (Full Screen Search):**
```jsonl
{"timestamp": 0.0, "type": "template_find", "template": "dialog_window.png", "roi": null, "threshold": 0.8, "retry": 3, "abort_on_fail": true}
```

**Relative Click (Click inside found template):**
```jsonl
{"timestamp": 0.0, "type": "relative_click", "template": "dialog_window.png", "offset_x": 50, "offset_y": 30, "threshold": 0.8, "retry": 3}
```

**Relative Recording (Actions relative to template):**
```jsonl
{"timestamp": 0.0, "type": "mouse_press", "x": 50, "y": 30, "button": "left", "relative_to_template": "dialog_window.png", "is_relative": true}
```
*This finds "dialog_window.png" and clicks 50px right, 30px down from its top-left corner*

### Phase 1 & 2: Core Record & Play Commands
- **Record Standard Atomic Mission:**
  ```powershell
  xiswalker record atomic basic_test
  ```
  *(Press `ESC` to stop recording)*

- **Play Atomic Mission:**
  ```powershell
  xiswalker play atomic basic_test
  ```

- **Play Atomic Mission with Humanization and Safe Mode:**
  ```powershell
  xiswalker play atomic basic_test --humanize 0.05 --safe-mode
  ```

### Phase 3: Composable Commands
- **Compose a Mission (Interactive YAML creation):**
  ```powershell
  xiswalker compose daily_workflow --add open_menu --add click_confirm --add close_dialog
  ```

- **Dry-run (Plan) a Composite Mission:**
  ```powershell
  xiswalker plan daily_workflow
  ```

- **Play a Composite Mission:**
  ```powershell
  xiswalker play composite daily_workflow
  ```

## Emergency Stop
Emergency Stop: Press `Ctrl + Shift + End` during playback to halt execution immediately.
