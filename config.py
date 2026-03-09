"""
config.py — Central configuration loader for AI Job Hunter
"""

import os
import yaml
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).parent


def load_preferences() -> dict:
    """Load candidate preferences from YAML file."""
    pref_path = BASE_DIR / "data" / "preferences.yaml"
    with open(pref_path, "r") as f:
        return yaml.safe_load(f)


# ── LLM ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = "gpt-4o"

# ── Airtable ─────────────────────────────────────────────────────────────────
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "JobTracker")

# ── Gmail ────────────────────────────────────────────────────────────────────
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "data/gmail_credentials.json")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "data/gmail_token.json")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# ── LinkedIn ─────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
LINKEDIN_BASE_URL = "https://www.linkedin.com"

# ── Naukri ───────────────────────────────────────────────────────────────────
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")
NAUKRI_BASE_URL = "https://www.naukri.com"

# ── Indeed ───────────────────────────────────────────────────────────────────
INDEED_BASE_URL = "https://in.indeed.com"

# ── Candidate ────────────────────────────────────────────────────────────────
CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "Your Name")
CANDIDATE_LINKEDIN = os.getenv("CANDIDATE_LINKEDIN", "")
CANDIDATE_PHONE = os.getenv("CANDIDATE_PHONE", "")

# ── Paths ────────────────────────────────────────────────────────────────────
RESUME_BASE_PATH = BASE_DIR / "data" / "base_resume.pdf"
TAILORED_RESUMES_DIR = BASE_DIR / "data" / "resumes"
TAILORED_RESUMES_DIR.mkdir(exist_ok=True)

# ── Playwright ───────────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True          # Set False to watch browser in action
PLAYWRIGHT_SLOW_MO = 500           # ms between actions (human-like)
PLAYWRIGHT_TIMEOUT = 30_000        # ms

# ── Rate limiting ─────────────────────────────────────────────────────────────
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 8
