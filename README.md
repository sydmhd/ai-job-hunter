# 🤖 AI Job Hunter

A goal-driven autonomous agent that finds jobs, tailors your resume, sends outreach, and tracks everything — powered by **CrewAI**, **Playwright**, **Gmail API**, and **Airtable**.

---

## 🗂️ Project Structure

```
ai-job-hunter/
├── agents/
│   ├── job_scout.py          # Agent 1: Finds & scores jobs
│   ├── resume_tailor.py      # Agent 2: Tailors resume per JD
│   ├── outreach.py           # Agent 3: Sends InMails & cold emails
│   └── tracker.py            # Agent 4: Tracks replies & follow-ups
├── tools/
│   ├── playwright_scraper.py # Browser automation (LinkedIn, Naukri, Indeed)
│   ├── gmail_tool.py         # Gmail API (send/receive emails)
│   ├── airtable_tool.py      # Airtable ledger (logging & tracking)
│   └── resume_parser.py      # PDF parsing & GPT-4o tailoring
├── scripts/
│   ├── setup_gmail_oauth.py  # One-time Gmail auth setup
│   ├── setup_airtable.py     # Airtable connection test
│   └── scheduler.py          # Local scheduler (alternative to cron)
├── data/
│   ├── base_resume.pdf       # ← PUT YOUR RESUME HERE
│   ├── preferences.yaml      # Your job preferences
│   └── resumes/              # Tailored resumes saved here
├── .github/workflows/
│   └── job_hunt.yml          # GitHub Actions (cloud automation)
├── reports/                  # Daily markdown reports
├── logs/                     # Run logs
├── crew.py                   # 🚀 Main entry point
├── config.py                 # Central config
├── requirements.txt
└── .env                      # Your secrets
```

---

## ⚡ Quick Start

### Step 1 — Clone & Install

```bash
git clone https://github.com/you/ai-job-hunter.git
cd ai-job-hunter
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Step 2 — Configure

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### Step 3 — Add Your Resume

```bash
cp /path/to/your/resume.pdf data/base_resume.pdf
```

### Step 4 — Edit Preferences

```bash
# Edit data/preferences.yaml with your target roles, skills, etc.
nano data/preferences.yaml
```

### Step 5 — Setup Gmail OAuth (one-time)

```bash
# First: download credentials.json from Google Cloud Console → save to data/
python scripts/setup_gmail_oauth.py
# A browser window opens → log in → authorize → done
```

### Step 6 — Setup Airtable

1. Create a free Airtable account at [airtable.com](https://airtable.com)
2. Create a new Base called "Job Hunt"
3. Run the schema helper:

```bash
python scripts/setup_airtable.py
```

4. Create the fields shown in the output in your Airtable table

### Step 7 — Run!

```bash
# Full daily pipeline
python crew.py

# Follow-ups only
python crew.py --mode followups

# Print Airtable schema
python crew.py --mode setup
```

---

## 🔧 Getting API Keys

| Service | How to get |
|---|---|
| OpenAI | [platform.openai.com](https://platform.openai.com) → API Keys |
| Airtable | [airtable.com/create/tokens](https://airtable.com/create/tokens) |
| Gmail | Google Cloud Console → Enable Gmail API → OAuth2 Credentials |
| LinkedIn | Your LinkedIn login credentials |
| Naukri | Your Naukri login credentials |

---

## ☁️ Cloud Automation (GitHub Actions)

1. Push this repo to GitHub (private repository)
2. Go to **Settings → Secrets and variables → Actions**
3. Add all your `.env` variables as secrets
4. For Gmail: also add `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON`
   (paste the file contents as the secret value)
5. The workflow runs automatically every weekday at 9:00 AM IST

---

## ⚙️ Local Scheduling

```bash
# Runs in background — full pipeline at 9AM, follow-ups at 2PM on weekdays
python scripts/scheduler.py
```

Or add to crontab:

```bash
crontab -e
# Add:
0 9 * * 1-5 /path/to/venv/bin/python /path/to/crew.py --mode full
0 14 * * 1-5 /path/to/venv/bin/python /path/to/crew.py --mode followups
```

---

## 🛡️ Rate Limits & Safety

| Platform | Limit | Enforced by |
|---|---|---|
| LinkedIn InMails | 15/day | `preferences.yaml` → `max_inmails_per_day` |
| Cold Emails | 20/day | `preferences.yaml` → `max_cold_emails_per_day` |
| Playwright | 2–8s delays | `config.py` → MIN/MAX_DELAY_SECONDS |
| Duplicates | Auto-checked | Airtable dedup before every apply |

---

## 📋 Daily Report Example

```
📋 Job Hunt Daily Report — 2026-03-09

## Today's Activity
- Jobs Applied: 8
- Resumes Tailored: 8
- LinkedIn InMails Sent: 7
- Cold Emails Sent: 5

## Recruiter Responses
| Company   | Role                  | Response      |
|-----------|-----------------------|---------------|
| Stripe    | Backend Engineer      | ✅ Replied    |
| Razorpay  | Senior SDE            | ⏳ No Reply   |

## Follow-ups Sent
| Company   | Role              | Email Sent To           |
|-----------|-------------------|-------------------------|
| Atlassian | Python Developer  | sarah.k@atlassian.com   |

## 🔔 Action Required
► Stripe — Backend Engineer: Positive reply — schedule call
```

---

## ⚠️ Disclaimer

- This tool automates job hunting for personal use only
- Always review tailored resumes before they're sent — accuracy is your responsibility
- Respect platform terms of service — avoid aggressive scraping
- LinkedIn limits connection requests; stay within their guidelines
