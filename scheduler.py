"""
scheduler.py
------------
Registers a Windows Task Scheduler task to run the AI Job Finder daily.

Usage:
  python scheduler.py           — Register / update the daily task
  python scheduler.py --remove  — Remove the scheduled task
  python scheduler.py --status  — Check if task is registered
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


VENV_PYTHON = str(
    Path(r"C:\Users\rajar\.gemini\antigravity\scratch\neon-assistant\.venv\Scripts\python.exe")
)


def get_task_command() -> tuple[str, str]:
    """Return (python_exe, agent_script_path) for the scheduled task."""
    # Use the venv Python that has all packages installed
    if Path(VENV_PYTHON).exists():
        python_exe = VENV_PYTHON
    else:
        python_exe = sys.executable
    agent_script = str(Path(__file__).parent.resolve() / "agent.py")
    return python_exe, agent_script


def register_task(config: dict):
    """Create or update a Windows Task Scheduler task."""
    schedule_cfg = config.get("schedule", {})
    run_time = schedule_cfg.get("time", "00:00")
    task_name = schedule_cfg.get("task_name", "AIJobFinder")

    proj_dir = Path(__file__).parent.resolve()
    bat_path = str(proj_dir / "run_agent.bat")

    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{bat_path}"',
        "/sc", "DAILY",
        "/st", run_time,
        "/f",  # Force overwrite if exists
    ]

    print(f"\n[+] Registering daily task: '{task_name}'")
    print(f"   [-] Time: {run_time} every day (Midnight)")
    print(f"   [-] Launcher: {bat_path}")
    print(f"   [-] Working dir: {proj_dir}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
        )
        if result.returncode == 0:
            print(f"\n[OK] Task '{task_name}' registered successfully!")
            print(f"   The agent will run daily at {run_time}.")
            print(f"\n   To verify: Open Task Scheduler -> Task Scheduler Library -> {task_name}")
        else:
            print(f"\n[ERROR] Failed to register task:")
            print(f"   {result.stderr.strip()}")
            print("\nTry running this script as Administrator.")
    except FileNotFoundError:
        print("[ERROR] schtasks not found. This script requires Windows.")
        sys.exit(1)


def remove_task(config: dict):
    """Remove the scheduled task."""
    task_name = config.get("schedule", {}).get("task_name", "AIJobFinder")
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] Task '{task_name}' removed.")
    else:
        print(f"[ERROR] {result.stderr.strip()}")


def check_status(config: dict):
    """Check if the scheduled task is registered."""
    task_name = config.get("schedule", {}).get("task_name", "AIJobFinder")
    cmd = ["schtasks", "/query", "/tn", task_name, "/fo", "LIST"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] Task '{task_name}' is registered:\n")
        print(result.stdout)
    else:
        print(f"[ERROR] Task '{task_name}' is NOT registered. Run: python scheduler.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Windows Task Scheduler manager for AI Job Finder")
    ap.add_argument("--remove", action="store_true", help="Remove the scheduled task")
    ap.add_argument("--status", action="store_true", help="Check task status")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    config = load_config(args.config)

    if args.remove:
        remove_task(config)
    elif args.status:
        check_status(config)
    else:
        register_task(config)
