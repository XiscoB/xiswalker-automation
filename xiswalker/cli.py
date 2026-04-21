"""CLI entry point for XisWalker — routes commands to recorder/player."""

import argparse
import sys


def main() -> None:
    """Parse CLI arguments and route to the appropriate command."""
    parser = argparse.ArgumentParser(
        prog="xiswalker",
        description="XisWalker — Record and replay keyboard/mouse input sequences.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Record command
    record_parser = subparsers.add_parser("record", help="Record a new mission")
    record_parser.add_argument("type", choices=["atomic"], help="Mission type")
    record_parser.add_argument("name", type=str, help="Mission name")
    record_parser.add_argument("--visual", action="store_true", help="Enable visual checkpoints (F8)")
    record_parser.add_argument("--relative-to", type=str, metavar="TEMPLATE", 
                               help="Record mouse coordinates relative to template position")

    # Play command
    play_parser = subparsers.add_parser("play", help="Play a recorded mission")
    play_parser.add_argument("type", choices=["atomic", "composite"], help="Mission type")
    play_parser.add_argument("name", type=str, help="Mission name")
    play_parser.add_argument(
        "--humanize",
        type=float,
        default=0.0,
        help="Humanization variance percentage (e.g., 0.05 for 5%)",
    )
    play_parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Require user confirmation before executing based on active window",
    )
    
    # Compose command
    compose_parser = subparsers.add_parser("compose", help="Create a composite mission")
    compose_parser.add_argument("name", type=str, help="Composite mission name")
    compose_parser.add_argument("--add", action="append", default=[], help="Atomic missions to add", required=True)
    
    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Dry run a composite mission")
    plan_parser.add_argument("name", type=str, help="Composite mission name")

    # Capture Template command
    capture_parser = subparsers.add_parser("capture-template", help="Interactively capture a screen region and save as template")
    capture_parser.add_argument("name", type=str, help="Name of the template (without .png)")

    # Run at command
    run_at_parser = subparsers.add_parser("run-at", help="Schedule a one-off run")
    run_at_parser.add_argument("time", type=str, help="Time to run (HH:MM)")
    run_at_parser.add_argument("composite", type=str, help="Composite mission name")

    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Start background scheduler")
    daemon_parser.add_argument("--config", type=str, default="config/schedule.yaml", help="Path to schedule config")

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Manage schedules")
    schedule_parser.add_argument("--list", action="store_true", help="List upcoming schedules")

    # Phase 7 Commands
    list_parser = subparsers.add_parser("list", help="List all missions")
    
    info_parser = subparsers.add_parser("info", help="Show mission info")
    info_parser.add_argument("type", choices=["atomic", "composite"], help="Mission type")
    info_parser.add_argument("name", type=str, help="Mission name")
    
    validate_parser = subparsers.add_parser("validate", help="Validate a mission")
    validate_parser.add_argument("type", choices=["atomic", "composite"], help="Mission type")
    validate_parser.add_argument("name", type=str, help="Mission name")

    edit_parser = subparsers.add_parser("edit", help="Edit a composite mission")
    edit_parser.add_argument("name", type=str, help="Composite mission name")
    edit_parser.add_argument("--add", type=str, help="Add atomic mission")
    edit_parser.add_argument("--wait", type=float, help="Add wait step")
    edit_parser.add_argument("--remove", type=int, help="Remove step index")
    
    export_parser = subparsers.add_parser("export", help="Export a mission")
    export_parser.add_argument("type", choices=["atomic", "composite"], help="Mission type")
    export_parser.add_argument("name", type=str, help="Mission name")
    export_parser.add_argument("--clipboard", action="store_true", help="Copy to clipboard")
    
    import_parser = subparsers.add_parser("import", help="Import a mission")
    import_parser.add_argument("file", type=str, help="JSON export file path or raw JSON")
    
    stats_parser = subparsers.add_parser("stats", help="Show execution stats")

    # Phase 8 GUI command
    gui_parser = subparsers.add_parser("gui", help="Launch the Native Desktop GUI")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "record":
        if args.type == "atomic":
            if args.relative_to:
                from xiswalker.recorder import record_relative_mission
                record_relative_mission(args.name, template_name=args.relative_to, visual=args.visual)
            else:
                from xiswalker.recorder import record_mission
                record_mission(args.name, visual=args.visual)

    elif args.command == "play":
        if args.type == "atomic":
            from xiswalker.player import play_atomic
            play_atomic(
                args.name,
                humanize=args.humanize,
                safe_mode=args.safe_mode,
            )
        elif args.type == "composite":
            from xiswalker.player import play_composite
            play_composite(
                args.name,
                humanize=args.humanize,
                safe_mode=args.safe_mode,
            )

    elif args.command == "compose":
        import yaml
        from pathlib import Path
        path = Path("missions/composite") / f"{args.name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        steps = [{"mission": a, "atomic": True} for a in args.add]
        data = {
            "name": args.name,
            "type": "composite",
            "description": "Composed mission",
            "grace_period": 5,
            "steps": steps
        }
        
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"✅ Created composite mission at {path}")
        
    elif args.command == "plan":
        from pathlib import Path
        from xiswalker.models import parse_composite_yaml
        path = Path("missions/composite") / f"{args.name}.yaml"
        try:
            mission = parse_composite_yaml(path)
            print(f"📋 Plan for '{mission.name}':")
            for i, step in enumerate(mission.steps, 1):
                if step.wait is not None:
                    print(f"  Step {i}/{len(mission.steps)}: Wait {step.wait}s")
                else:
                    print(f"  Step {i}/{len(mission.steps)}: [atomic] {step.mission}")
        except Exception as e:
            print(f"❌ Failed to parse composite mission: {e}")

    elif args.command == "capture-template":
        from xiswalker.recorder import capture_template
        capture_template(args.name)

    elif args.command == "run-at":
        from xiswalker.scheduler import run_at
        run_at(args.time, args.composite)
        
    elif args.command == "daemon":
        from xiswalker.executor import ExecutorQueue
        from xiswalker.scheduler import start_daemon
        executor = ExecutorQueue()
        start_daemon(args.config, executor)
        
    elif args.command == "schedule":
        if args.list:
            from xiswalker.scheduler import list_schedules
            # List schedules from default config path
            list_schedules("config/schedule.yaml")
            
    # Phase 7 handlers
    elif args.command == "list":
        from xiswalker.utilities import list_missions
        list_missions()
        
    elif args.command == "info":
        from xiswalker.utilities import mission_info
        mission_info(args.type, args.name)
        
    elif args.command == "validate":
        from xiswalker.utilities import validate_mission
        validate_mission(args.type, args.name)
        
    elif args.command == "edit":
        from xiswalker.utilities import edit_composite
        if args.remove is not None:
            edit_composite(args.name, "remove", index=args.remove)
        elif args.add is not None:
            edit_composite(args.name, "add", mission=args.add)
        elif args.wait is not None:
            edit_composite(args.name, "add", wait=args.wait)
        else:
            print("❌ Must provide --add, --wait, or --remove")
            
    elif args.command == "export":
        from xiswalker.importer import export_mission
        export_mission(args.type, args.name, to_clipboard=args.clipboard)
        
    elif args.command == "import":
        from xiswalker.importer import import_mission
        import_mission(args.file)
        
    elif args.command == "stats":
        from xiswalker.stats import show_stats
        show_stats()
        
    elif args.command == "gui":
        from xiswalker.gui import run_gui
        run_gui()

if __name__ == "__main__":
    main()
