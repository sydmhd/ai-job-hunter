"""
agents/outreach.py — Agent 3: Finds recruiters, sends InMails and cold emails
"""

import json
from crewai import Agent, Task
from config import LLM_MODEL, load_preferences, CANDIDATE_NAME, CANDIDATE_LINKEDIN
from tools.playwright_scraper import RecruiterFinderTool, SendInMailTool
from tools.gmail_tool import GmailColdEmailTool
from tools.airtable_tool import AirtableInMailTool, AirtableEmailTool

# ── Tool instances ─────────────────────────────────────────────────────────────
recruiter_finder = RecruiterFinderTool()
inmail_tool = SendInMailTool()
gmail_tool = GmailColdEmailTool()
airtable_inmail = AirtableInMailTool()
airtable_email = AirtableEmailTool()


# ── InMail Message Generator ───────────────────────────────────────────────────

def build_inmail_message(recruiter_name: str, company: str, role: str, top_skill: str) -> str:
    """Generate a concise, personalized LinkedIn connection note (max 300 chars)."""
    msg = (
        f"Hi {recruiter_name.split()[0]}, I came across the {role} opening at {company}. "
        f"With my background in {top_skill}, I'd love to connect and learn more. "
        f"— {CANDIDATE_NAME}"
    )
    return msg[:300]


# ── Agent ──────────────────────────────────────────────────────────────────────

def build_outreach_agent() -> Agent:
    prefs = load_preferences()
    max_inmails = prefs["limits"]["max_inmails_per_day"]
    max_emails = prefs["limits"]["max_cold_emails_per_day"]

    return Agent(
        role="Outreach Specialist",
        goal=(
            "For each job application, find the relevant HR/recruiter contact, "
            "send a personalized LinkedIn InMail, and send a cold email if an address is available. "
            f"Do not exceed {max_inmails} InMails or {max_emails} emails per day."
        ),
        backstory=(
            "You are a networking expert who has mastered the art of getting responses "
            "from busy recruiters. You write crisp, human, relevant messages that get opened. "
            "You never use generic templates — every message references the specific company "
            "and role. You respect daily rate limits to protect the candidate's accounts."
        ),
        tools=[recruiter_finder, inmail_tool, gmail_tool, airtable_inmail, airtable_email],
        llm=LLM_MODEL,
        verbose=True,
        memory=True,
        max_iter=15,
    )


# ── Task ───────────────────────────────────────────────────────────────────────

def build_outreach_task(agent: Agent) -> Task:
    prefs = load_preferences()
    skills = prefs["skills"]["primary"]
    max_inmails = prefs["limits"]["max_inmails_per_day"]
    max_emails = prefs["limits"]["max_cold_emails_per_day"]

    return Task(
        description=f"""
You will receive 'tailor_output' from the previous agent with a "tailored_jobs" list.
Process only jobs where status == "tailored" (skip duplicates/skipped).

DAILY LIMITS: Max {max_inmails} InMails, Max {max_emails} cold emails. Stop once either limit is hit.

For EACH job (in order):

─── STEP 1: FIND RECRUITER ───
Use the Recruiter Finder Tool with company = job["company"].
Pick the BEST match (HR Manager, Talent Acquisition, Recruiter).
If no results, note "recruiter_not_found" and continue to email-only.

─── STEP 2: SEND LINKEDIN INMAIL ───
Use the LinkedIn InMail Tool with:
  - profile_url = recruiter["profile_url"]
  - message = A personalized 300-char message containing:
    * Recruiter's first name
    * The exact role title
    * The company name
    * Your strongest matching skill from: {skills}
    * Your name
  Example: "Hi Sarah, I came across the Senior Backend Engineer role at Stripe. 
  With 5 years in Python/FastAPI at scale, I'd love to connect. — {CANDIDATE_NAME}"

If InMail sent successfully:
  - Use Airtable InMail Logger with record_id, recruiter name, and profile_url

─── STEP 3: FIND RECRUITER EMAIL ───
If the recruiter's email is visible on their profile, capture it.
Otherwise try common patterns: firstname.lastname@company.com, firstname@company.com
Note: only send email if you have a reasonable address — do NOT guess random emails.

─── STEP 4: SEND COLD EMAIL ───
If email found, use the Gmail Cold Email Tool with:
  - to_email = recruiter's email
  - recruiter_name = recruiter's name
  - company = job["company"]
  - role = job["title"]
  - top_skill = the best matching skill from {skills}
  - key_achievement = a 1-sentence achievement from the candidate's background
    that directly relates to the JD (synthesize from the JD context)
  - resume_path = job["resume_path"]

If email sent:
  - Capture thread_id from the response
  - Use Airtable Email Logger with record_id, recipient_email, thread_id

─── STEP 5: OUTPUT ───
After processing all jobs, return JSON:
{{
  "outreach_results": [
    {{
      "company": "...",
      "role": "...",
      "airtable_record_id": "...",
      "recruiter_name": "...",
      "recruiter_profile": "...",
      "inmail_sent": true,
      "email_sent": true,
      "email_to": "...",
      "thread_id": "...",
      "notes": "..."
    }}
  ],
  "inmails_sent_today": 8,
  "emails_sent_today": 6
}}
""",
        agent=agent,
        expected_output=(
            "JSON with 'outreach_results' array detailing InMail and email status per job, "
            "plus daily totals for inmails_sent_today and emails_sent_today"
        ),
        context=[],  # Will receive tailor_task output via crew.py
    )
