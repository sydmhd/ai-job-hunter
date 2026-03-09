"""
tools/gmail_tool.py — Gmail API integration for sending cold emails & tracking replies
"""

import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_SCOPES, SENDER_EMAIL


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_gmail_service():
    """
    Authenticate and return an authorized Gmail API service.
    First run: opens browser for OAuth consent.
    Subsequent runs: uses saved token.json.
    """
    creds = None

    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(GMAIL_TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Email Builder ──────────────────────────────────────────────────────────────

def build_email_message(
    to: str,
    subject: str,
    html_body: str,
    attachment_path: Optional[str] = None,
) -> dict:
    """Create a Gmail API-compatible message dict."""
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["from"] = SENDER_EMAIL
    message["subject"] = subject

    # HTML body
    part = MIMEText(html_body, "html")
    message.attach(part)

    # Optional attachment (tailored resume PDF)
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            payload = MIMEBase("application", "octet-stream")
            payload.set_payload(f.read())
            encoders.encode_base64(payload)
            payload.add_header(
                "Content-Disposition",
                f"attachment; filename={Path(attachment_path).name}",
            )
            message.attach(payload)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


# ── Send Email ─────────────────────────────────────────────────────────────────

def send_cold_email(
    to_email: str,
    subject: str,
    html_body: str,
    attachment_path: Optional[str] = None,
) -> dict:
    """
    Send a cold email via Gmail API.
    Returns: {success: bool, message_id: str, thread_id: str}
    """
    try:
        service = get_gmail_service()
        msg = build_email_message(to_email, subject, html_body, attachment_path)
        result = service.users().messages().send(userId="me", body=msg).execute()
        print(f"[Gmail] Email sent to {to_email} | ID: {result['id']}")
        return {
            "success": True,
            "message_id": result["id"],
            "thread_id": result.get("threadId", ""),
        }
    except HttpError as e:
        print(f"[Gmail] Send error: {e}")
        return {"success": False, "message_id": "", "thread_id": ""}


# ── Check Replies ──────────────────────────────────────────────────────────────

def check_thread_reply(thread_id: str) -> dict:
    """
    Check if a recruiter replied to a specific email thread.
    Returns: {replied: bool, reply_snippet: str}
    """
    try:
        service = get_gmail_service()
        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        messages = thread.get("messages", [])
        if len(messages) > 1:
            last_msg = messages[-1]
            headers = {h["name"]: h["value"] for h in last_msg["payload"]["headers"]}
            snippet = last_msg.get("snippet", "")
            sender = headers.get("From", "")
            # If reply is NOT from us, it's a recruiter reply
            if SENDER_EMAIL not in sender:
                return {"replied": True, "reply_snippet": snippet, "from": sender}
        return {"replied": False, "reply_snippet": "", "from": ""}
    except HttpError as e:
        print(f"[Gmail] Check reply error: {e}")
        return {"replied": False, "reply_snippet": "", "from": ""}


def get_all_sent_threads() -> list[dict]:
    """Retrieve all sent email thread IDs for follow-up checking."""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me", labelIds=["SENT"], maxResults=100
        ).execute()
        return results.get("messages", [])
    except HttpError as e:
        print(f"[Gmail] List error: {e}")
        return []


# ── Email Templates ────────────────────────────────────────────────────────────

def render_cold_email_html(
    recruiter_name: str,
    company: str,
    role: str,
    candidate_name: str,
    candidate_linkedin: str,
    top_skill: str,
    key_achievement: str,
) -> tuple[str, str]:
    """Returns (subject, html_body) for a cold email."""
    subject = f"Exploring {role} Opportunities at {company}"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 15px; color: #222; line-height: 1.6;">
    <p>Hi {recruiter_name},</p>
    <p>
        I noticed that <strong>{company}</strong> is hiring for <strong>{role}</strong>.
        With my background in <strong>{top_skill}</strong> — including {key_achievement} —
        I believe I could add meaningful value to your team.
    </p>
    <p>
        I would love the opportunity to learn more about the role and share how my experience
        aligns with what you're looking for. Would you be open to a brief 15-minute conversation?
    </p>
    <p>I've attached my resume for your reference.</p>
    <p>
        Best regards,<br>
        <strong>{candidate_name}</strong><br>
        <a href="{candidate_linkedin}">{candidate_linkedin}</a>
    </p>
    </body></html>
    """
    return subject, html


def render_followup_email_html(
    recruiter_name: str,
    company: str,
    role: str,
    candidate_name: str,
    original_date: str,
) -> tuple[str, str]:
    """Returns (subject, html_body) for a follow-up email."""
    subject = f"Following Up — {role} at {company}"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 15px; color: #222; line-height: 1.6;">
    <p>Hi {recruiter_name},</p>
    <p>
        I wanted to follow up on my previous email from <strong>{original_date}</strong>
        regarding the <strong>{role}</strong> position at <strong>{company}</strong>.
    </p>
    <p>
        I remain very interested in this opportunity and would welcome any update on the
        hiring process. I'm happy to provide any additional information you might need.
    </p>
    <p>Thank you for your time!</p>
    <p>
        Best regards,<br>
        <strong>{candidate_name}</strong>
    </p>
    </body></html>
    """
    return subject, html


# ── CrewAI Tool Wrappers ──────────────────────────────────────────────────────

class SendEmailInput(BaseModel):
    to_email: str = Field(description="Recipient email address")
    recruiter_name: str = Field(description="Recruiter's first name")
    company: str = Field(description="Company name")
    role: str = Field(description="Job role/title")
    top_skill: str = Field(description="Candidate's top matching skill")
    key_achievement: str = Field(description="One key achievement relevant to the role")
    resume_path: Optional[str] = Field(default=None, description="Path to tailored resume file")


class GmailColdEmailTool(BaseTool):
    name: str = "Gmail Cold Email Tool"
    description: str = (
        "Sends a personalized cold email to a recruiter via Gmail API. "
        "Returns a JSON with success status, message_id, and thread_id for tracking."
    )
    args_schema: type[BaseModel] = SendEmailInput

    def _run(
        self,
        to_email: str,
        recruiter_name: str,
        company: str,
        role: str,
        top_skill: str,
        key_achievement: str,
        resume_path: Optional[str] = None,
    ) -> str:
        from config import CANDIDATE_NAME, CANDIDATE_LINKEDIN
        subject, html = render_cold_email_html(
            recruiter_name, company, role,
            CANDIDATE_NAME, CANDIDATE_LINKEDIN,
            top_skill, key_achievement,
        )
        result = send_cold_email(to_email, subject, html, resume_path)
        return json.dumps(result)


class CheckReplyInput(BaseModel):
    thread_id: str = Field(description="Gmail thread ID to check for recruiter replies")


class GmailCheckReplyTool(BaseTool):
    name: str = "Gmail Reply Checker Tool"
    description: str = (
        "Checks if a recruiter replied to a specific Gmail thread. "
        "Input: thread_id. Returns JSON with replied (bool) and reply_snippet."
    )
    args_schema: type[BaseModel] = CheckReplyInput

    def _run(self, thread_id: str) -> str:
        result = check_thread_reply(thread_id)
        return json.dumps(result)


class SendFollowupInput(BaseModel):
    to_email: str = Field(description="Recruiter email address")
    recruiter_name: str = Field(description="Recruiter first name")
    company: str = Field(description="Company name")
    role: str = Field(description="Role applied for")
    original_date: str = Field(description="Date of original email (e.g. March 1, 2026)")


class GmailFollowupTool(BaseTool):
    name: str = "Gmail Follow-up Tool"
    description: str = (
        "Sends a follow-up email to a recruiter who hasn't replied. "
        "Input: to_email, recruiter_name, company, role, original_date."
    )
    args_schema: type[BaseModel] = SendFollowupInput

    def _run(
        self,
        to_email: str,
        recruiter_name: str,
        company: str,
        role: str,
        original_date: str,
    ) -> str:
        from config import CANDIDATE_NAME
        subject, html = render_followup_email_html(
            recruiter_name, company, role, CANDIDATE_NAME, original_date
        )
        result = send_cold_email(to_email, subject, html)
        return json.dumps(result)
