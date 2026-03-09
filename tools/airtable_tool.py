"""
tools/airtable_tool.py — Airtable ledger for tracking all job applications & outreach
"""

import json
from datetime import date, datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pyairtable import Api

from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME


# ── Airtable Client ────────────────────────────────────────────────────────────

def get_table():
    api = Api(AIRTABLE_API_KEY)
    return api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)


# ── Field Constants (must match your Airtable column names exactly) ────────────

F_COMPANY         = "Company"
F_ROLE            = "Role"
F_PLATFORM        = "Platform"
F_JD_URL          = "JD URL"
F_APPLIED_DATE    = "Applied Date"
F_STATUS          = "Status"
F_INMAIL_SENT     = "InMail Sent"
F_INMAIL_DATE     = "InMail Date"
F_INMAIL_RESPONSE = "InMail Response"
F_INMAIL_TO       = "InMail Recipient"
F_EMAIL_SENT      = "Cold Email Sent"
F_EMAIL_DATE      = "Cold Email Date"
F_EMAIL_RESPONSE  = "Cold Email Response"
F_EMAIL_TO        = "Cold Email Recipient"
F_EMAIL_THREAD_ID = "Gmail Thread ID"
F_FOLLOWUP_DATE   = "Follow-up Date"
F_RESUME_PATH     = "Tailored Resume Path"
F_RELEVANCE_SCORE = "Relevance Score"
F_NOTES           = "Notes"


# ── CRUD Helpers ───────────────────────────────────────────────────────────────

def log_application(
    company: str,
    role: str,
    platform: str,
    jd_url: str,
    relevance_score: int,
    resume_path: str = "",
    notes: str = "",
) -> str:
    """Create a new row in Airtable for a job application. Returns the record ID."""
    table = get_table()
    today = date.today().isoformat()
    followup = (date.today() + timedelta(days=7)).isoformat()

    record = table.create({
        F_COMPANY:         company,
        F_ROLE:            role,
        F_PLATFORM:        platform,
        F_JD_URL:          jd_url,
        F_APPLIED_DATE:    today,
        F_STATUS:          "Applied",
        F_INMAIL_SENT:     False,
        F_EMAIL_SENT:      False,
        F_FOLLOWUP_DATE:   followup,
        F_RELEVANCE_SCORE: relevance_score,
        F_RESUME_PATH:     resume_path,
        F_NOTES:           notes,
    })
    print(f"[Airtable] Logged: {company} — {role} | Record: {record['id']}")
    return record["id"]


def log_inmail(record_id: str, recipient_name: str, profile_url: str) -> None:
    """Update an existing record with InMail details."""
    table = get_table()
    table.update(record_id, {
        F_INMAIL_SENT:     True,
        F_INMAIL_DATE:     date.today().isoformat(),
        F_INMAIL_TO:       f"{recipient_name} ({profile_url})",
        F_INMAIL_RESPONSE: "No Reply",
    })
    print(f"[Airtable] InMail logged for record {record_id}")


def log_cold_email(
    record_id: str,
    recipient_email: str,
    thread_id: str = "",
) -> None:
    """Update an existing record with cold email details."""
    table = get_table()
    table.update(record_id, {
        F_EMAIL_SENT:      True,
        F_EMAIL_DATE:      date.today().isoformat(),
        F_EMAIL_TO:        recipient_email,
        F_EMAIL_THREAD_ID: thread_id,
        F_EMAIL_RESPONSE:  "No Reply",
    })
    print(f"[Airtable] Cold email logged for record {record_id}")


def update_status(record_id: str, status: str) -> None:
    """Update application status. Options: Applied, Interview, Offer, Rejected, Withdrawn."""
    table = get_table()
    table.update(record_id, {F_STATUS: status})
    print(f"[Airtable] Status updated → {status} for record {record_id}")


def update_response(record_id: str, channel: str, response: str) -> None:
    """
    channel: 'inmail' or 'email'
    response: 'No Reply', 'Replied', 'Positive', 'Negative'
    """
    table = get_table()
    if channel == "inmail":
        table.update(record_id, {F_INMAIL_RESPONSE: response})
    elif channel == "email":
        table.update(record_id, {F_EMAIL_RESPONSE: response})


def get_pending_followups() -> list[dict]:
    """
    Return all records where:
    - Follow-up Date <= today
    - Status == 'Applied'
    - No positive response yet
    """
    table = get_table()
    today = date.today().isoformat()
    records = table.all(
        formula=(
            f"AND("
            f"  IS_BEFORE({{Follow-up Date}}, TODAY()),"
            f"  {{Status}} = 'Applied',"
            f"  OR({{Cold Email Response}} = 'No Reply', {{Cold Email Response}} = '')"
            f")"
        )
    )
    result = []
    for r in records:
        fields = r["fields"]
        result.append({
            "record_id": r["id"],
            "company": fields.get(F_COMPANY, ""),
            "role": fields.get(F_ROLE, ""),
            "email_to": fields.get(F_EMAIL_TO, ""),
            "email_thread_id": fields.get(F_EMAIL_THREAD_ID, ""),
            "applied_date": fields.get(F_APPLIED_DATE, ""),
            "inmail_to": fields.get(F_INMAIL_TO, ""),
        })
    return result


def deduplicate_check(company: str, role: str) -> bool:
    """Return True if this company+role combo already exists in Airtable."""
    table = get_table()
    formula = f"AND({{Company}} = '{company}', {{Role}} = '{role}')"
    existing = table.all(formula=formula)
    return len(existing) > 0


def get_all_applications() -> list[dict]:
    """Return all application records for reporting."""
    table = get_table()
    records = table.all()
    return [{"id": r["id"], **r["fields"]} for r in records]


# ── Airtable Schema Setup Script ───────────────────────────────────────────────

def setup_airtable_schema():
    """
    Print instructions for manually creating the Airtable table.
    (Airtable API v2 supports programmatic field creation via Metadata API,
    but that requires an Enterprise plan. These are the fields to create manually.)
    """
    schema = [
        ("Company",             "Single line text"),
        ("Role",                "Single line text"),
        ("Platform",            "Single select — LinkedIn, Naukri, Indeed"),
        ("JD URL",              "URL"),
        ("Applied Date",        "Date"),
        ("Status",              "Single select — Applied, Interview, Offer, Rejected, Withdrawn"),
        ("Relevance Score",     "Number (integer 1-10)"),
        ("Tailored Resume Path","Single line text"),
        ("InMail Sent",         "Checkbox"),
        ("InMail Date",         "Date"),
        ("InMail Recipient",    "Single line text"),
        ("InMail Response",     "Single select — No Reply, Replied, Positive, Negative"),
        ("Cold Email Sent",     "Checkbox"),
        ("Cold Email Date",     "Date"),
        ("Cold Email Recipient","Single line text"),
        ("Gmail Thread ID",     "Single line text"),
        ("Cold Email Response", "Single select — No Reply, Replied, Positive, Negative"),
        ("Follow-up Date",      "Date"),
        ("Notes",               "Long text"),
    ]
    print("\n" + "─" * 60)
    print("  AIRTABLE SCHEMA — Create these fields in your base")
    print("─" * 60)
    for field_name, field_type in schema:
        print(f"  • {field_name:<30} → {field_type}")
    print("─" * 60 + "\n")


# ── CrewAI Tool Wrappers ──────────────────────────────────────────────────────

class LogApplicationInput(BaseModel):
    company: str = Field(description="Company name")
    role: str = Field(description="Job role/title")
    platform: str = Field(description="Platform: LinkedIn, Naukri, or Indeed")
    jd_url: str = Field(description="URL of the job posting")
    relevance_score: int = Field(description="Relevance score 1-10")
    resume_path: str = Field(default="", description="Path to tailored resume file")
    notes: str = Field(default="", description="Any extra notes")


class AirtableLogTool(BaseTool):
    name: str = "Airtable Application Logger"
    description: str = (
        "Logs a new job application to Airtable. "
        "First checks for duplicates. Returns the Airtable record ID."
    )
    args_schema: type[BaseModel] = LogApplicationInput

    def _run(
        self,
        company: str,
        role: str,
        platform: str,
        jd_url: str,
        relevance_score: int,
        resume_path: str = "",
        notes: str = "",
    ) -> str:
        if deduplicate_check(company, role):
            return json.dumps({"status": "duplicate", "record_id": None})
        record_id = log_application(company, role, platform, jd_url, relevance_score, resume_path, notes)
        return json.dumps({"status": "logged", "record_id": record_id})


class LogInMailInput(BaseModel):
    record_id: str = Field(description="Airtable record ID for this application")
    recipient_name: str = Field(description="Recruiter's name")
    profile_url: str = Field(description="Recruiter's LinkedIn profile URL")


class AirtableInMailTool(BaseTool):
    name: str = "Airtable InMail Logger"
    description: str = "Updates an Airtable record with InMail outreach details."
    args_schema: type[BaseModel] = LogInMailInput

    def _run(self, record_id: str, recipient_name: str, profile_url: str) -> str:
        log_inmail(record_id, recipient_name, profile_url)
        return f"InMail logged for record {record_id}"


class LogEmailInput(BaseModel):
    record_id: str = Field(description="Airtable record ID")
    recipient_email: str = Field(description="Email address of recruiter")
    thread_id: str = Field(default="", description="Gmail thread ID for reply tracking")


class AirtableEmailTool(BaseTool):
    name: str = "Airtable Email Logger"
    description: str = "Updates an Airtable record with cold email outreach details."
    args_schema: type[BaseModel] = LogEmailInput

    def _run(self, record_id: str, recipient_email: str, thread_id: str = "") -> str:
        log_cold_email(record_id, recipient_email, thread_id)
        return f"Cold email logged for record {record_id}"


class GetFollowupsInput(BaseModel):
    dummy: str = Field(default="", description="No input needed")


class AirtableFollowupTool(BaseTool):
    name: str = "Airtable Follow-up Checker"
    description: str = (
        "Returns all applications that are due for a follow-up today "
        "(no response within 7 days of applying)."
    )
    args_schema: type[BaseModel] = GetFollowupsInput

    def _run(self, dummy: str = "") -> str:
        followups = get_pending_followups()
        return json.dumps(followups, indent=2)
