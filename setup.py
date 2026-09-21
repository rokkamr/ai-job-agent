"""
setup.py
--------
One-time interactive setup wizard for the AI Resume Job Finder.
Guides the user through:
  1. Installing Python dependencies
  2. Configuring API keys (Gemini, RapidAPI, Adzuna)
  3. Configuring email (Gmail App Password)
  4. Registering the Windows Task Scheduler daily task

Run once:  python setup.py
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path("config.yaml")
BANNER = r"""
  ╔══════════════════════════════════════════════════════╗
  ║       🤖  AI Resume Job Finder — Setup Wizard        ║
  ║        Find your perfect job, every morning!         ║
  ╚══════════════════════════════════════════════════════╝
"""


def print_step(n: int, title: str):
    print(f"\n{'─'*55}")
    print(f"  Step {n}: {title}")
    print(f"{'─'*55}")


def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    """Prompt the user for input with an optional default."""
    display_default = "****" if secret and default else default
    full_prompt = f"  {prompt}"
    if default:
        full_prompt += f" [{display_default}]"
    full_prompt += ": "

    if secret:
        import getpass
        value = getpass.getpass(full_prompt)
    else:
        value = input(full_prompt).strip()

    return value if value else default


def find_python() -> str:
    """Find the best available Python executable."""
    candidates = [
        sys.executable,
        r"C:\Users\rajar\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe",
    ]
    # Also check for any .venv in parent scratch dir
    scratch = Path(r"C:\Users\rajar\.gemini\antigravity\scratch")
    for venv_python in scratch.glob("*/.venv/Scripts/python.exe"):
        candidates.append(str(venv_python))
    for c in candidates:
        if Path(c).exists():
            return c
    return sys.executable  # fallback


def install_dependencies():
    print_step(1, "Installing Python Dependencies")
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("  ❌ requirements.txt not found! Make sure you're in the resume_agent folder.")
        sys.exit(1)

    # Try uv first (faster)
    uv_path = Path(r"C:\Users\rajar\AppData\Roaming\uv\bin\uv.exe")
    if uv_path.exists():
        print("  Using uv to create virtual environment...")
        subprocess.run([str(uv_path), "venv", ".venv"], check=False)
        print("  Running: uv pip install -r requirements.txt")
        result = subprocess.run(
            [str(uv_path), "pip", "install", "-r", "requirements.txt"],
            capture_output=False,
        )
    else:
        python_exe = find_python()
        print(f"  Using Python: {python_exe}")
        print(f"  Creating virtual environment...")
        subprocess.run([python_exe, "-m", "venv", ".venv"], check=False)
        venv_python = str(Path(".venv") / "Scripts" / "python.exe")
        print(f"  Running: pip install -r requirements.txt")
        result = subprocess.run(
            [venv_python, "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=False,
        )
    if result.returncode != 0:
        print("  ⚠️  Some packages may have failed to install. Check the output above.")
    else:
        print("  ✅ Dependencies installed in .venv!")


def configure_gemini(config: dict) -> dict:
    print_step(2, "Google Gemini API Key (Required)")
    print("  Get your FREE key at: https://aistudio.google.com/app/apikey")
    print("  (Free tier: 1500 requests/day — more than enough!)\n")

    # Check if already set via environment
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        print(f"  ✅ Found GEMINI_API_KEY in environment variables!")
        use_env = ask("Use it from environment? (y/n)", default="y").lower()
        if use_env == "y":
            config["gemini"]["api_key"] = "__ENV__"
            return config

    current = config.get("gemini", {}).get("api_key", "")
    if current and current != "YOUR_GEMINI_API_KEY":
        print(f"  Current key: {current[:8]}...")
        keep = ask("Keep existing key? (y/n)", default="y").lower()
        if keep == "y":
            return config

    api_key = ask("Enter your Gemini API key", secret=True)
    if api_key:
        config["gemini"]["api_key"] = api_key
        print("  ✅ Gemini API key saved!")
    else:
        print("  ⚠️  No key provided — you must set GEMINI_API_KEY environment variable before running.")

    return config


def configure_email(config: dict) -> dict:
    print_step(3, "Gmail Email Configuration")
    print("  You need a Gmail App Password (not your regular password).")
    print("  Guide: https://support.google.com/accounts/answer/185833\n")
    print("  Steps:")
    print("  1. Go to Google Account → Security → 2-Step Verification (enable it)")
    print("  2. Go to Security → App passwords → Generate one for 'Mail'\n")

    sender = ask("Your Gmail address", default=config["email"].get("sender_email", ""))
    if sender and sender != "YOUR_EMAIL@gmail.com":
        config["email"]["sender_email"] = sender

    password = ask("Gmail App Password (16-char, no spaces)", secret=True)
    if password:
        config["email"]["sender_password"] = password

    recipient = ask(
        "Send reports to (press Enter to use same email)",
        default=config["email"].get("sender_email", sender),
    )
    config["email"]["recipient_email"] = recipient or sender

    config["email"]["enabled"] = True
    print("  ✅ Email configured!")
    return config


def configure_optional_apis(config: dict) -> dict:
    print_step(4, "Optional Job APIs (More Results)")
    print("  These are optional but give you more job listings:\n")

    # RapidAPI / JSearch
    print("  📡 JSearch (RapidAPI) — 200 free requests/month")
    print("     Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch\n")
    key = ask("RapidAPI key (press Enter to skip)", default="")
    if key:
        config["apis"]["rapidapi_key"] = key
        print("  ✅ JSearch configured!")

    # Adzuna
    print("\n  📡 Adzuna India — 1000 free requests/month")
    print("     Sign up: https://developer.adzuna.com/\n")
    app_id = ask("Adzuna App ID (press Enter to skip)", default="")
    if app_id:
        app_key = ask("Adzuna App Key", secret=True)
        config["apis"]["adzuna_app_id"] = app_id
        config["apis"]["adzuna_app_key"] = app_key
        print("  ✅ Adzuna configured!")

    return config


def configure_schedule(config: dict) -> dict:
    print_step(5, "Daily Schedule")
    time_str = ask(
        "What time should the agent run daily? (HH:MM, 24-hour format)",
        default=config.get("schedule", {}).get("time", "08:00"),
    )
    config["schedule"]["time"] = time_str
    print(f"  ✅ Agent will run daily at {time_str}")
    return config


def check_resume(config: dict):
    print_step(6, "Resume Setup")
    resume_path = Path(config["resume"]["path"])
    print(f"  Expected resume location: {resume_path.resolve()}\n")
    if resume_path.exists():
        print(f"  ✅ Found resume: {resume_path.name}")
    else:
        print(f"  ⚠️  Resume not found yet!")
        print(f"  → Copy your PDF resume to: {resume_path.resolve()}")
        print(f"  → Then run: python agent.py --test")


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"\n  💾 Configuration saved to: {CONFIG_PATH.resolve()}")


def register_scheduler(config: dict):
    print_step(7, "Register Daily Scheduler (Windows Task Scheduler)")
    register = ask("Register the daily task now? (y/n)", default="y").lower()
    if register == "y":
        import scheduler as sched
        sched.register_task(config)
    else:
        print("  Skipped. Run 'python scheduler.py' later to register.")


def run_test():
    print_step(8, "Test Run")
    run = ask("Run a quick test now? (y/n)", default="y").lower()
    if run == "y":
        print("\n  Running: python agent.py --test\n")
        result = subprocess.run(
            [sys.executable, "agent.py", "--test"],
            capture_output=False,
        )
        if result.returncode == 0:
            print("\n  ✅ Test passed! Check the output/ folder for your first HTML report.")
        else:
            print("\n  ⚠️  Test encountered errors. Check the output above.")


def main():
    print(BANNER)
    print("  This wizard will set up your AI Resume Job Finder in a few steps.")
    print("  Press Ctrl+C at any time to exit.\n")

    # Load current config
    if not CONFIG_PATH.exists():
        print("❌ config.yaml not found. Make sure you're in the resume_agent/ folder.")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    try:
        install_dependencies()
        config = configure_gemini(config)
        config = configure_email(config)
        config = configure_optional_apis(config)
        config = configure_schedule(config)
        save_config(config)
        check_resume(config)
        register_scheduler(config)
        run_test()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Setup interrupted. Saving progress...")
        save_config(config)
        print("  Run 'python setup.py' again to continue.")
        sys.exit(0)

    print("\n" + "═" * 55)
    print("  🎉 Setup complete!")
    print("     ✅ The agent will run daily automatically")
    print("     ✅ You'll receive job matches by email each morning")
    print("     ✅ HTML reports are saved in: output/")
    print("\n  Next steps:")
    print("     1. Place your resume PDF in: resume/resume.pdf")
    print("     2. Run manually anytime: python agent.py")
    print("     3. Check task status: python scheduler.py --status")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()
