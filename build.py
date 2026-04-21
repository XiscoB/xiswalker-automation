#!/usr/bin/env python3
"""
Build script to create a standalone executable for XisWalker.

Usage:
    python build.py              # Auto-increment patch (0.0.1)
    python build.py --minor      # Increment minor (0.1.0)
    python build.py --major      # Increment major (1.0.0)
    python build.py --set 1.2.3  # Set specific version
"""

import argparse
import subprocess
import sys
import shutil
import os
import re
from pathlib import Path

VERSION_FILE = Path(".buildversion")
DEFAULT_BUMP = "patch"


def get_current_version() -> str:
    """Read current version from file or return default."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.1.0"


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string to tuple."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return tuple(int(x) for x in match.groups())


def bump_version(current: str, bump_type: str) -> str:
    """Bump version according to type."""
    major, minor, patch = parse_version(current)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def save_version(version: str) -> None:
    """Save version to file."""
    VERSION_FILE.write_text(version)


def clean_build_dirs() -> None:
    """Remove previous build artifacts."""
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"  Cleaning {folder}/...")
            try:
                shutil.rmtree(folder)
            except PermissionError:
                print(f"    Warning: Could not remove {folder}/ (in use). Skipping...")
            except Exception as e:
                print(f"    Warning: Could not clean {folder}/: {e}")


def build_executable() -> Path:
    """Run PyInstaller and return path to created exe."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=XisWalker",
        "--onefile",
        "--windowed",
        "--add-data=config;config",
        "--add-data=missions;missions",
        # Core dependencies with full collection
        "--collect-all=pynput",
        "--collect-all=pywin32",
        "--collect-all=yaml",
        "--collect-all=colorama",
        "--collect-all=PIL",
        "--collect-all=cv2",
        "--collect-all=numpy",
        "--collect-all=tqdm",
        "xiswalker/__main__.py"
    ]
    
    print("  Running PyInstaller (this may take a minute)...")
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        raise RuntimeError("PyInstaller build failed")
    
    return Path("dist/XisWalker.exe")


def create_distribution(version: str) -> tuple[Path, Path]:
    """Create distribution folder and zip. Returns (folder_path, zip_path)."""
    output_dir = Path(f"dist/XisWalker-v{version}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    exe_source = Path("dist/XisWalker.exe")
    exe_target = output_dir / "XisWalker.exe"
    shutil.move(str(exe_source), str(exe_target))
    
    for folder in ["config", "missions"]:
        if os.path.exists(folder):
            shutil.copytree(folder, output_dir / folder, dirs_exist_ok=True)
    
    _create_helper_files(output_dir, version)
    
    zip_path = Path(f"dist/XisWalker-v{version}-windows")
    shutil.make_archive(str(zip_path), 'zip', root_dir="dist", base_dir=f"XisWalker-v{version}")
    
    return output_dir, Path(f"{zip_path}.zip")


def _create_helper_files(output_dir: Path, version: str) -> None:
    """Create helper batch files and README."""
    
    (output_dir / "START.bat").write_text(
        "@echo off\n"
        f"echo XisWalker v{version}\n"
        "echo ====================\n"
        "echo Starting with console output (for debugging)...\n"
        "XisWalker.exe gui\n"
        "pause\n"
    )
    
    (output_dir / "README.txt").write_text(
        f"XISWALKER v{version} - Input Automation Tool\n"
        + "=" * 45 + "\n\n"
        "QUICK START:\n"
        "1. Double-click XisWalker.exe to start the GUI\n"
        "2. Or use START.bat to see console output\n\n"
        "SAFETY:\n"
        "- Safe Mode is ON by default\n"
        "- Only works on the focused window\n"
        "- Press ESC anytime to stop\n\n"
        "FOLDERS:\n"
        "- config/     Settings and configuration\n"
        "- missions/   Your automation missions\n\n"
        "Need help? Contact the developer!\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Build XisWalker executable",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build.py              # Build with auto patch bump (+0.0.1)
  python build.py --minor      # Bump minor version (+0.1.0)
  python build.py --major      # Bump major version (+1.0.0)
  python build.py --set 1.2.3  # Use specific version
        """
    )
    
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument("--minor", action="store_true", help="Bump minor version")
    version_group.add_argument("--major", action="store_true", help="Bump major version")
    version_group.add_argument("--set", metavar="VERSION", help="Set specific version (e.g., 1.2.3)")
    
    args = parser.parse_args()
    
    current = get_current_version()
    
    if args.set:
        new_version = args.set
        parse_version(new_version)
    elif args.major:
        new_version = bump_version(current, "major")
    elif args.minor:
        new_version = bump_version(current, "minor")
    else:
        new_version = bump_version(current, "patch")
    
    print(f"[BUILD] Building XisWalker v{new_version} (was v{current})")
    
    clean_build_dirs()
    
    try:
        build_executable()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    output_dir, zip_path = create_distribution(new_version)
    
    save_version(new_version)
    
    print("\n" + "=" * 50)
    print(f"[OK] Build complete! v{new_version}")
    print("=" * 50)
    print(f"   Folder: {output_dir}")
    print(f"   Zip:    {zip_path}")
    print(f"\n   Size:   {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    print("\n[SHARE] Share the zip file directly or upload to GitHub Releases!")


if __name__ == "__main__":
    main()
