"""
agents/resume_tailor.py — Agent 2: Tailors resume for each job, logs to Airtable
"""

import json
from crewai import Agent, Task
from config import LLM_MODEL
from tools.resume_parser import ResumeTool, TailorResumeTool
from tools.airtable_tool import AirtableLogTool

# ── Tool instances ─────────────────────────────────────────────────────────────
resume_tool = ResumeTool()
tailor_tool = TailorResumeTool()
airtable_log_tool = AirtableLogTool()


# ── Agent ──────────────────────────────────────────────────────────────────────

def build_resume_tailor_agent() -> Agent:
    return Agent(
        role="ATS Resume Optimizer",
        goal=(
            "For each qualified job, produce a tailored version of the candidate's resume "
            "that maximizes keyword alignment with the JD while maintaining 100% factual accuracy. "
            "Log every application to Airtable."
        ),
        backstory=(
            "You are an expert resume consultant and ATS specialist who has helped 500+ engineers "
            "land roles at FAANG and top startups. You understand exactly what ATS systems scan for "
            "and how to surface the right keywords without fabricating anything. "
            "Your cardinal rule: never lie, never fabricate — only reframe."
        ),
        tools=[resume_tool, tailor_tool, airtable_log_tool],
        llm=LLM_MODEL,
        verbose=True,
        memory=True,
        max_iter=10,
    )


# ── Task ───────────────────────────────────────────────────────────────────────

def build_tailor_task(agent: Agent) -> Task:
    return Task(
        description="""
You will receive a JSON object called 'scout_output' from the previous agent.
It contains a list of jobs under the key "jobs".

For EACH job in the list, do ALL of the following steps in order:

STEP 1 — CHECK DUPLICATE
Use the Airtable Application Logger tool. If it returns {"status": "duplicate"}, 
SKIP this job entirely and move to the next.

STEP 2 — TAILOR RESUME
Use the Resume Tailor Tool with:
  - job_description = job["jd_text"]
  - company = job["company"]
  - role = job["title"]
This saves a tailored .txt resume and returns its file path.

STEP 3 — SCORE THE TAILORED RESUME
Use Resume Parser Tool with:
  - action = "score_jd"
  - jd_text = job["jd_text"]
Record the score for logging.

STEP 4 — LOG TO AIRTABLE
Use Airtable Application Logger with:
  - company = job["company"]
  - role = job["title"]
  - platform = job["platform"]
  - jd_url = job["apply_url"]
  - relevance_score = job["relevance_score"]
  - resume_path = (path returned from Step 2)
Save the returned record_id — you MUST pass this to the outreach agent.

STRICT RULES FOR TAILORING (enforce these via your instructions to the tool):
- NEVER add skills, tools, or certifications not in the original resume
- NEVER change job titles, company names, or employment dates
- ONLY rephrase existing bullets using JD vocabulary
- ONLY reorder the skills section to front-load matching skills
- Ensure every keyword added genuinely reflects the candidate's experience

OUTPUT FORMAT (return this exact JSON):
{
  "tailored_jobs": [
    {
      "company": "...",
      "role": "...",
      "platform": "...",
      "apply_url": "...",
      "jd_text": "...",
      "resume_path": "...",
      "airtable_record_id": "...",
      "relevance_score": 8,
      "status": "tailored"  // or "duplicate" / "skipped"
    }
  ]
}
""",
        agent=agent,
        expected_output=(
            "JSON object with 'tailored_jobs' array — each job entry includes "
            "company, role, resume_path, airtable_record_id, and status"
        ),
        context=[],   # Will be populated with scout_task output by crew.py
    )
