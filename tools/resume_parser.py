"""
tools/resume_parser.py — Extract and structure resume content from PDF
"""

import re
from pathlib import Path
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import PyPDF2
from config import RESUME_BASE_PATH, TAILORED_RESUMES_DIR, LLM_MODEL, OPENAI_API_KEY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract raw text from a PDF file."""
    text = []
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)


def get_resume_text() -> str:
    """Return base resume text."""
    return extract_text_from_pdf(RESUME_BASE_PATH)


def get_structured_resume() -> dict:
    """
    Use GPT to parse raw resume text into structured JSON.
    Returns: {name, email, phone, summary, skills, experience, education, certifications}
    """
    raw = get_resume_text()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a resume parser. Extract structured data from the resume text. "
                    "Return JSON with keys: name, email, phone, summary, skills (list), "
                    "experience (list of {company, title, dates, bullets}), "
                    "education (list), certifications (list)."
                ),
            },
            {"role": "user", "content": raw},
        ],
    )
    import json
    return json.loads(response.choices[0].message.content)


def tailor_resume_text(base_resume_text: str, job_description: str, company: str, role: str) -> str:
    """
    Use GPT-4o to produce a tailored resume text aligned with the JD.
    Strict rules: no fabrication, only rephrase/reorder existing content.
    """
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": """You are an expert ATS resume optimizer.

RULES (non-negotiable):
- ONLY use information present in the original resume
- DO NOT add fake skills, tools, certifications, or experience
- DO NOT change company names, job titles, or employment dates
- You MAY rephrase bullet points using vocabulary from the JD
- You MAY reorder skills to prioritize JD-matched skills
- You MAY add JD keywords that genuinely describe existing experience
- Keep the same resume structure and length
- Return ONLY the modified resume text, nothing else""",
            },
            {
                "role": "user",
                "content": (
                    f"ORIGINAL RESUME:\n{base_resume_text}\n\n"
                    f"JOB DESCRIPTION for {role} at {company}:\n{job_description}\n\n"
                    "Produce a tailored resume text. Follow all rules strictly."
                ),
            },
        ],
        max_tokens=3000,
    )
    return response.choices[0].message.content.strip()


def save_tailored_resume_as_text(tailored_text: str, company: str, role: str) -> Path:
    """Save tailored resume as a .txt file (PDF generation requires reportlab/weasyprint)."""
    safe_company = re.sub(r"[^\w]", "_", company)[:30]
    safe_role = re.sub(r"[^\w]", "_", role)[:30]
    filename = f"resume_{safe_company}_{safe_role}.txt"
    path = TAILORED_RESUMES_DIR / filename
    path.write_text(tailored_text, encoding="utf-8")
    return path


def score_resume_vs_jd(resume_text: str, jd_text: str) -> int:
    """Return a relevance score 1-10."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a recruiter scoring resume-to-JD fit. Return JSON: {score: int, reasons: list}",
            },
            {
                "role": "user",
                "content": (
                    f"RESUME:\n{resume_text[:3000]}\n\nJOB DESCRIPTION:\n{jd_text[:3000]}\n\n"
                    "Score from 1-10 how well this resume matches the JD."
                ),
            },
        ],
    )
    import json
    data = json.loads(response.choices[0].message.content)
    return int(data.get("score", 5))


# ── CrewAI Tool Wrappers ──────────────────────────────────────────────────────

class ResumeParserInput(BaseModel):
    action: str = Field(description="One of: 'get_text', 'get_structured', 'score_jd'")
    jd_text: Optional[str] = Field(default=None, description="Job description text for scoring")


class ResumeTool(BaseTool):
    name: str = "Resume Parser Tool"
    description: str = (
        "Reads the candidate's base resume. Actions: "
        "'get_text' returns raw text, "
        "'get_structured' returns parsed JSON, "
        "'score_jd' scores resume vs a job description (requires jd_text)."
    )
    args_schema: type[BaseModel] = ResumeParserInput

    def _run(self, action: str, jd_text: Optional[str] = None) -> str:
        if action == "get_text":
            return get_resume_text()
        elif action == "get_structured":
            import json
            return json.dumps(get_structured_resume(), indent=2)
        elif action == "score_jd":
            if not jd_text:
                return "Error: jd_text is required for score_jd action"
            score = score_resume_vs_jd(get_resume_text(), jd_text)
            return str(score)
        return f"Unknown action: {action}"


class TailorResumeInput(BaseModel):
    job_description: str = Field(description="Full job description text")
    company: str = Field(description="Company name")
    role: str = Field(description="Job role/title")


class TailorResumeTool(BaseTool):
    name: str = "Resume Tailor Tool"
    description: str = (
        "Takes a job description, company name, and role. "
        "Tailors the base resume to match the JD and saves the file. "
        "Returns the path to the saved tailored resume."
    )
    args_schema: type[BaseModel] = TailorResumeInput

    def _run(self, job_description: str, company: str, role: str) -> str:
        base_text = get_resume_text()
        tailored = tailor_resume_text(base_text, job_description, company, role)
        path = save_tailored_resume_as_text(tailored, company, role)
        return str(path)
