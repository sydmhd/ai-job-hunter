"""
scripts/scheduler.py — Run the job hunt automatically every weekday morning.
Alternative to cron for cross-platform scheduling.

Usage: python scripts/scheduler.py
       (keep this running in background / screen / tmux)
"""

import schedule
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VENV_PYTHON = sys.executable   # Uses current Python (should be venv)
CREW_SCRIPT = str(Path(__file__).parent.parent / "crew.py")
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def run_full_pipeline():
    """Execute the full job hunt pipeline and log output."""
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_file = LOG_DIR / f"run_{now}.log"
    print(f"\n[{datetime.now()}] 🚀 Starting daily job hunt...")

    with open(log_file, "w") as f:
        result = subprocess.run(
            [VENV_PYTHON, CREW_SCRIPT, "--mode", "full"],
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )

    status = "✅ SUCCESS" if result.returncode == 0 else "❌ FAILED"
    print(f"[{datetime.now()}] {status} | Log: {log_file}")


def run_followup_check():
    """Midday follow-up check only."""
    print(f"\n[{datetime.now()}] 📬 Running follow-up check...")
    subprocess.run([VENV_PYTHON, CREW_SCRIPT, "--mode", "followups"])


# ── Schedule ──────────────────────────────────────────────────────────────────
# Full pipeline: Every weekday at 9:00 AM
schedule.every().monday.at("09:00").do(run_full_pipeline)
schedule.every().tuesday.at("09:00").do(run_full_pipeline)
schedule.every().wednesday.at("09:00").do(run_full_pipeline)
schedule.every().thursday.at("09:00").do(run_full_pipeline)
schedule.every().friday.at("09:00").do(run_full_pipeline)

# Follow-up check: Every weekday at 2:00 PM
schedule.every().monday.at("14:00").do(run_followup_check)
schedule.every().tuesday.at("14:00").do(run_followup_check)
schedule.every().wednesday.at("14:00").do(run_followup_check)
schedule.every().thursday.at("14:00").do(run_followup_check)
schedule.every().friday.at("14:00").do(run_followup_check)


if __name__ == "__main__":
    print("⏰ Scheduler started. Waiting for next run...")
    print("   → Full pipeline: Weekdays at 9:00 AM")
    print("   → Follow-up check: Weekdays at 2:00 PM")
    print("   → Press Ctrl+C to stop\n")

    while True:
        schedule.run_pending()
        time.sleep(30)
