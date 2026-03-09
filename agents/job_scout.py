"""
agents/job_scout.py — Agent 1: Discovers and scores job listings across platforms
"""

import json
from crewai import Agent, Task
from config import LLM_MODEL, load_preferences
from tools.playwright_scraper import PlaywrightJobScraperTool
from tools.resume_parser import ResumeTool

# ── Tool instances ─────────────────────────────────────────────────────────────
job_scraper_tool = PlaywrightJobScraperTool()
resume_tool = ResumeTool()


# ── Agent ──────────────────────────────────────────────────────────────────────

def build_job_scout_agent() -> Agent:
    return Agent(
        role="Senior Job Scout",
        goal=(
            "Find and evaluate the most relevant, high-quality job opportunities "
            "across LinkedIn, Naukri, and Indeed that match the candidate's profile, "
            "skills, and salary expectations."
        ),
        backstory=(
            "You are a seasoned technical recruiter with 10 years of experience "
            "placing engineers at top companies. You know exactly what makes a job "
            "a good fit vs a waste of time. You filter ruthlessly based on role fit, "
            "company quality, and salary alignment. You never send irrelevant postings."
        ),
        tools=[job_scraper_tool, resume_tool],
        llm=LLM_MODEL,
        verbose=True,
        memory=True,
        max_iter=5,
    )


# ── Task ───────────────────────────────────────────────────────────────────────

def build_scout_task(agent: Agent) -> Task:
    prefs = load_preferences()
    roles = prefs["target_roles"]
    locations = prefs["locations"]
    min_score = prefs["limits"]["min_relevance_score"]
    max_jobs = prefs["limits"]["max_jobs_per_run"]
    exclude = prefs.get("exclude_companies", [])
    exclude_kw = prefs.get("exclude_keywords", [])
    skills = prefs["skills"]["primary"]

    return Task(
        description=f"""
You are searching for jobs for a candidate with these preferences:

TARGET ROLES: {roles}
LOCATIONS: {locations}
KEY SKILLS: {skills}
SALARY RANGE: {prefs['salary']['min_lpa']}–{prefs['salary']['max_lpa']} LPA
EXCLUDE COMPANIES: {exclude}
EXCLUDE KEYWORDS: {exclude_kw}
MINIMUM RELEVANCE SCORE: {min_score}/10
MAX JOBS TO RETURN: {max_jobs}

STEP-BY-STEP INSTRUCTIONS:
1. Use the Resume Parser Tool (action='get_text') to retrieve the candidate's resume.
2. For each combination of role and location (prioritize top 2 roles × top 2 locations):
   - Use the Job Scraper Tool to find jobs (limit=5 per platform per combination)
3. For every job found:
   a. Check if the company is in the exclude list → skip if so
   b. Check if the JD contains any excluded keywords → skip if so
   c. Use the Resume Parser Tool (action='score_jd', jd_text=<jd>) to score the match
   d. Only keep jobs with score >= {min_score}
4. Deduplicate by company + role combination
5. Sort by relevance score descending
6. Return the top {max_jobs} jobs

OUTPUT FORMAT (return this exact JSON structure):
{{
  "jobs": [
    {{
      "title": "...",
      "company": "...",
      "platform": "...",
      "location": "...",
      "apply_url": "...",
      "jd_text": "...",
      "relevance_score": 8
    }}
  ],
  "total_searched": 45,
  "total_qualified": 12
}}
""",
        agent=agent,
        expected_output="JSON object with 'jobs' array containing top-scored job listings",
    )
