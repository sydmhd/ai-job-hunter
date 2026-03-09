"""
agents/tracker.py — Agent 4: Monitors replies, manages follow-ups, generates daily report
"""

import json
from crewai import Agent, Task
from config import LLM_MODEL
from tools.airtable_tool import AirtableFollowupTool, AirtableEmailTool, AirtableInMailTool
from tools.gmail_tool import GmailCheckReplyTool, GmailFollowupTool

# ── Tool instances ─────────────────────────────────────────────────────────────
followup_checker = AirtableFollowupTool()
reply_checker = GmailCheckReplyTool()
followup_sender = GmailFollowupTool()
airtable_email_log = AirtableEmailTool()
airtable_inmail_log = AirtableInMailTool()


# ── Agent ──────────────────────────────────────────────────────────────────────

def build_tracker_agent() -> Agent:
    return Agent(
        role="Application Tracker & Follow-up Manager",
        goal=(
            "Monitor all job applications for recruiter replies. "
            "Send follow-up emails for applications with no response after 7 days. "
            "Produce a clean daily summary report of all activity."
        ),
        backstory=(
            "You are an obsessively organized career coach who never lets a hot lead go cold. "
            "You know that 80% of placements come from following up. You track every thread, "
            "check every reply, and send timely follow-ups that feel warm — not desperate. "
            "You keep meticulous records so the candidate always knows exactly where they stand."
        ),
        tools=[followup_checker, reply_checker, followup_sender, airtable_email_log],
        llm=LLM_MODEL,
        verbose=True,
        memory=True,
        max_iter=20,
    )


# ── Task ───────────────────────────────────────────────────────────────────────

def build_tracker_task(agent: Agent) -> Task:
    return Task(
        description="""
You have TWO responsibilities in this task:

══════════════════════════════════════════════════
PART A: CHECK FOR REPLIES ON TODAY'S OUTREACH
══════════════════════════════════════════════════
You will receive 'outreach_output' from the previous agent with an "outreach_results" list.

For each result where email_sent == true AND thread_id is not empty:
1. Use the Gmail Reply Checker Tool with thread_id
2. If replied == true:
   - Note the reply snippet
   - Update the status in your output as "Replied ✓"
3. If replied == false:
   - Status remains "Awaiting Reply"

══════════════════════════════════════════════════
PART B: PROCESS FOLLOW-UPS FROM PREVIOUS DAYS
══════════════════════════════════════════════════
1. Use the Airtable Follow-up Checker tool (no input needed)
   - This returns all applications due for follow-up today

2. For each item in the follow-up list:
   a. If email_to is not empty AND thread_id not empty:
      - First use Gmail Reply Checker to see if they already replied
      - If already replied: skip (no follow-up needed), mark as "Replied"
      - If no reply: use the Gmail Follow-up Tool to send a follow-up email:
          to_email = record["email_to"]
          recruiter_name = (extract first name from inmail_to or email_to)
          company = record["company"]
          role = record["role"]
          original_date = record["applied_date"]
   b. If no email available: note "no email — manual follow-up needed"

3. After sending each follow-up, log it using Airtable Email Logger:
   - Pass the new thread_id from the follow-up email

══════════════════════════════════════════════════
PART C: GENERATE DAILY SUMMARY REPORT
══════════════════════════════════════════════════
Compile a clean markdown-formatted daily report:

```
# 📋 Job Hunt Daily Report — {today's date}

## Today's Activity
- Jobs Applied: X
- Resumes Tailored: X
- LinkedIn InMails Sent: X
- Cold Emails Sent: X

## Recruiter Responses (Today)
| Company | Role | Response |
|---------|------|----------|
| ...     | ...  | ...      |

## Follow-ups Sent
| Company | Role | Email Sent To |
|---------|------|---------------|
| ...     | ...  | ...           |

## Action Required (Positive Responses)
[List any positive/interested replies that need human attention]

## Pipeline Overview
- Applied (awaiting): X
- Interview stage: X  
- Offer stage: X
- Rejected: X
```

OUTPUT FORMAT:
{
  "reply_checks": [
    {"company": "...", "role": "...", "replied": true/false, "snippet": "..."}
  ],
  "followups_sent": [
    {"company": "...", "role": "...", "email_to": "...", "status": "sent"/"skipped"}
  ],
  "daily_report": "...full markdown report string...",
  "action_required": [
    {"company": "...", "role": "...", "note": "Positive reply — schedule call"}
  ]
}
""",
        agent=agent,
        expected_output=(
            "JSON with reply_checks, followups_sent, daily_report (markdown), "
            "and action_required list for human review"
        ),
        context=[],  # Will receive outreach_task output via crew.py
    )
