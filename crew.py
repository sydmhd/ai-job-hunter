"""
crew.py — Main CrewAI orchestrator for the AI Job Hunter
Run this daily: python crew.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path
from crewai import Crew, Process
from dotenv import load_dotenv

load_dotenv()

# ── Import agent builders ─────────────────────────────────────────────────────
from agents.job_scout import build_job_scout_agent, build_scout_task
from agents.resume_tailor import build_resume_tailor_agent, build_tailor_task
from agents.outreach import build_outreach_agent, build_outreach_task
from agents.tracker import build_tracker_agent, build_tracker_task
from tools.airtable_tool import setup_airtable_schema
from config import RESUME_BASE_PATH, load_preferences


# ── Pre-flight checks ──────────────────────────────────────────────────────────

def preflight_check() -> bool:
    """Verify all required config and files exist before running."""
    issues = []

    required_env = [
        "OPENAI_API_KEY", "AIRTABLE_API_KEY", "AIRTABLE_BASE_ID",
        "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD", "SENDER_EMAIL",
    ]
    for var in required_env:
        if not os.getenv(var):
            issues.append(f"  ✗ Missing env var: {var}")

    if not RESUME_BASE_PATH.exists():
        issues.append(f"  ✗ Resume not found at: {RESUME_BASE_PATH}")

    gmail_creds = os.getenv("GMAIL_CREDENTIALS_PATH", "data/gmail_credentials.json")
    if not Path(gmail_creds).exists():
        issues.append(f"  ✗ Gmail credentials not found: {gmail_creds}")

    if issues:
        print("\n⚠️  PRE-FLIGHT FAILED — Fix these issues before running:\n")
        for issue in issues:
            print(issue)
        print()
        return False

    print("✅ Pre-flight check passed\n")
    return True


# ── Report Writer ──────────────────────────────────────────────────────────────

def save_daily_report(report_md: str):
    """Save the daily markdown report to /reports/YYYY-MM-DD.md"""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"{date.today().isoformat()}.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\n📄 Daily report saved to: {report_path}")
    return report_path


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║           🤖  AI JOB HUNTER  —  CrewAI              ║
║   Discover → Tailor → Outreach → Track → Repeat     ║
╚══════════════════════════════════════════════════════╝
""")


# ── Main Orchestrator ──────────────────────────────────────────────────────────

def run_job_hunt(dry_run: bool = False):
    """
    Full pipeline:
    1. Scout    — finds jobs across platforms
    2. Tailor   — adapts resume per JD, logs to Airtable
    3. Outreach — sends InMails + cold emails
    4. Tracker  — checks replies, sends follow-ups, generates report
    """
    print_banner()
    print(f"📅 Date: {date.today()}")
    print(f"⚙️  Mode: {'DRY RUN (no emails/InMails sent)' if dry_run else 'LIVE'}\n")

    if not preflight_check():
        sys.exit(1)

    prefs = load_preferences()
    print(f"👤 Candidate: {prefs['candidate']['name']}")
    print(f"🎯 Roles: {', '.join(prefs['target_roles'][:3])}")
    print(f"📍 Locations: {', '.join(prefs['locations'][:3])}\n")

    # ── Build agents ──────────────────────────────────────────────────────────
    print("🔧 Initialising agents...\n")
    scout_agent   = build_job_scout_agent()
    tailor_agent  = build_resume_tailor_agent()
    outreach_agent = build_outreach_agent()
    tracker_agent = build_tracker_agent()

    # ── Build tasks with context chaining ────────────────────────────────────
    scout_task   = build_scout_task(scout_agent)
    tailor_task  = build_tailor_task(tailor_agent)
    outreach_task = build_outreach_task(outreach_agent)
    tracker_task = build_tracker_task(tracker_agent)

    # Chain context: each task receives the output of the previous
    tailor_task.context   = [scout_task]
    outreach_task.context = [tailor_task]
    tracker_task.context  = [outreach_task]

    # ── Assemble Crew ─────────────────────────────────────────────────────────
    crew = Crew(
        agents=[scout_agent, tailor_agent, outreach_agent, tracker_agent],
        tasks=[scout_task, tailor_task, outreach_task, tracker_task],
        process=Process.sequential,   # Agents run one after another, passing outputs
        verbose=True,
        memory=True,                  # Shared memory across agents
        embedder={
            "provider": "openai",
            "config": {"model": "text-embedding-3-small"},
        },
    )

    # ── Kick off ──────────────────────────────────────────────────────────────
    print("🚀 Starting job hunt crew...\n")
    print("=" * 60)

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("✅ Crew completed\n")

    # ── Parse and display results ─────────────────────────────────────────────
    try:
        raw = str(result)
        # Try to extract JSON from the tracker output
        start = raw.rfind("{")
        end = raw.rfind("}") + 1
        if start != -1:
            tracker_output = json.loads(raw[start:end])
            report_md = tracker_output.get("daily_report", "")
            if report_md:
                save_daily_report(report_md)
                print("\n" + "─" * 60)
                print(report_md)
                print("─" * 60)

            action_items = tracker_output.get("action_required", [])
            if action_items:
                print(f"\n🔔 ACTION REQUIRED ({len(action_items)} items):")
                for item in action_items:
                    print(f"  ► {item['company']} — {item['role']}: {item['note']}")
        else:
            print("Raw crew output:")
            print(raw[:2000])
    except Exception as e:
        print(f"Could not parse final output: {e}")
        print(str(result)[:1000])

    return result


# ── Follow-ups Only Mode ───────────────────────────────────────────────────────

def run_followups_only():
    """
    Run only the Tracker agent to check replies and send follow-ups.
    Useful for mid-day checks without doing a full job search.
    """
    print_banner()
    print("📬 MODE: Follow-ups & Reply Check Only\n")

    tracker_agent = build_tracker_agent()
    tracker_task  = build_tracker_task(tracker_agent)

    crew = Crew(
        agents=[tracker_agent],
        tasks=[tracker_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs={"outreach_output": '{"outreach_results": []}'})
    print("\n✅ Follow-up check complete")
    return result


# ── CLI Entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Job Hunter — CrewAI Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["full", "followups", "setup"],
        default="full",
        help=(
            "full = full daily pipeline | "
            "followups = only check replies & send follow-ups | "
            "setup = print Airtable schema setup instructions"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without sending real emails or InMails",
    )
    args = parser.parse_args()

    if args.mode == "setup":
        setup_airtable_schema()
    elif args.mode == "followups":
        run_followups_only()
    else:
        run_job_hunt(dry_run=args.dry_run)
