"""
tools/playwright_scraper.py — Browser automation for job discovery & LinkedIn outreach
"""

import asyncio
import random
import re
from typing import Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from config import (
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD,
    NAUKRI_EMAIL, NAUKRI_PASSWORD,
    PLAYWRIGHT_HEADLESS, PLAYWRIGHT_SLOW_MO, PLAYWRIGHT_TIMEOUT,
    MIN_DELAY_SECONDS, MAX_DELAY_SECONDS,
    LINKEDIN_BASE_URL, NAUKRI_BASE_URL, INDEED_BASE_URL,
    load_preferences,
)


# ── Utilities ──────────────────────────────────────────────────────────────────

async def human_delay(page: Page, min_s: float = None, max_s: float = None):
    """Pause for a random duration to mimic human behaviour."""
    low = min_s or MIN_DELAY_SECONDS
    high = max_s or MAX_DELAY_SECONDS
    await asyncio.sleep(random.uniform(low, high))
    await page.wait_for_load_state("networkidle", timeout=PLAYWRIGHT_TIMEOUT)


async def safe_text(page: Page, selector: str, default: str = "") -> str:
    try:
        el = await page.query_selector(selector)
        return (await el.inner_text()).strip() if el else default
    except Exception:
        return default


async def safe_attr(page: Page, selector: str, attr: str, default: str = "") -> str:
    try:
        el = await page.query_selector(selector)
        return (await el.get_attribute(attr)) or default if el else default
    except Exception:
        return default


# ── Browser Factory ────────────────────────────────────────────────────────────

async def get_browser_context() -> tuple[Browser, BrowserContext]:
    """Launch a stealth-ish Chromium context."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=PLAYWRIGHT_HEADLESS,
        slow_mo=PLAYWRIGHT_SLOW_MO,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    # Mask webdriver flag
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


# ── LinkedIn ───────────────────────────────────────────────────────────────────

async def linkedin_login(page: Page) -> bool:
    """Login to LinkedIn. Returns True on success."""
    await page.goto(f"{LINKEDIN_BASE_URL}/login", timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 1, 3)
    await page.fill("#username", LINKEDIN_EMAIL)
    await page.fill("#password", LINKEDIN_PASSWORD)
    await page.click('button[type="submit"]')
    await human_delay(page, 2, 4)
    return "feed" in page.url or "mynetwork" in page.url


async def scrape_linkedin_jobs(page: Page, role: str, location: str, limit: int = 10) -> list[dict]:
    """Search and scrape job listings from LinkedIn."""
    jobs = []
    search_url = (
        f"{LINKEDIN_BASE_URL}/jobs/search/"
        f"?keywords={role.replace(' ', '%20')}"
        f"&location={location.replace(' ', '%20')}"
        f"&f_TPR=r86400"   # Last 24 hours
        f"&f_WT=2"          # Remote filter (optional)
        f"&sortBy=DD"        # Date descending
    )
    await page.goto(search_url, timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 2, 5)

    # Scroll to load more results
    for _ in range(3):
        await page.keyboard.press("End")
        await asyncio.sleep(1.5)

    job_cards = await page.query_selector_all(".job-card-container")
    for card in job_cards[:limit]:
        try:
            await card.click()
            await human_delay(page, 1, 3)

            title = await safe_text(page, ".job-details-jobs-unified-top-card__job-title")
            company = await safe_text(page, ".job-details-jobs-unified-top-card__company-name")
            location_text = await safe_text(page, ".job-details-jobs-unified-top-card__bullet")
            jd_text = await safe_text(page, ".jobs-description__content")
            apply_url = page.url

            if title and company and jd_text:
                jobs.append({
                    "platform": "LinkedIn",
                    "title": title,
                    "company": company,
                    "location": location_text,
                    "jd_text": jd_text[:4000],
                    "apply_url": apply_url,
                })
            await human_delay(page, 1, 2)
        except Exception as e:
            print(f"[LinkedIn] Error parsing card: {e}")
            continue
    return jobs


async def linkedin_send_connection_with_note(page: Page, profile_url: str, message: str) -> bool:
    """Visit a recruiter profile and send a connection request with a note."""
    try:
        await page.goto(profile_url, timeout=PLAYWRIGHT_TIMEOUT)
        await human_delay(page, 2, 4)

        # Click Connect button
        connect_btn = await page.query_selector('button:has-text("Connect")')
        if not connect_btn:
            # Try More > Connect
            more_btn = await page.query_selector('button:has-text("More")')
            if more_btn:
                await more_btn.click()
                await asyncio.sleep(1)
                connect_btn = await page.query_selector('li:has-text("Connect")')

        if connect_btn:
            await connect_btn.click()
            await asyncio.sleep(1.5)
            # Click "Add a note"
            add_note_btn = await page.query_selector('button:has-text("Add a note")')
            if add_note_btn:
                await add_note_btn.click()
                await asyncio.sleep(1)
                # Type message (max 300 chars for connection note)
                note_area = await page.query_selector('textarea[name="message"]')
                if note_area:
                    await note_area.fill(message[:300])
                    send_btn = await page.query_selector('button:has-text("Send")')
                    if send_btn:
                        await send_btn.click()
                        await human_delay(page, 1, 2)
                        return True
        return False
    except Exception as e:
        print(f"[LinkedIn] InMail error: {e}")
        return False


async def linkedin_find_recruiters(page: Page, company: str) -> list[dict]:
    """Search LinkedIn for HR/recruiter profiles at a given company."""
    recruiters = []
    search_url = (
        f"{LINKEDIN_BASE_URL}/search/results/people/"
        f"?keywords=HR+recruiter+{company.replace(' ', '+')}"
        f"&origin=GLOBAL_SEARCH_HEADER"
    )
    await page.goto(search_url, timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 2, 4)

    results = await page.query_selector_all(".entity-result__item")
    for r in results[:5]:
        try:
            name_el = await r.query_selector(".entity-result__title-text")
            headline_el = await r.query_selector(".entity-result__primary-subtitle")
            link_el = await r.query_selector("a.app-aware-link")
            name = (await name_el.inner_text()).strip() if name_el else "Unknown"
            headline = (await headline_el.inner_text()).strip() if headline_el else ""
            link = (await link_el.get_attribute("href")) if link_el else ""
            if any(kw in headline.lower() for kw in ["hr", "recruit", "talent", "hiring"]):
                recruiters.append({"name": name, "headline": headline, "profile_url": link})
        except Exception:
            continue
    return recruiters


# ── Naukri ─────────────────────────────────────────────────────────────────────

async def naukri_login(page: Page) -> bool:
    await page.goto(f"{NAUKRI_BASE_URL}/nlogin/login", timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 1, 3)
    await page.fill('input[placeholder="Enter your active Email ID / Username"]', NAUKRI_EMAIL)
    await page.fill('input[placeholder="Enter your password"]', NAUKRI_PASSWORD)
    await page.click('button[type="submit"]')
    await human_delay(page, 2, 4)
    return "myapps" in page.url or "jobs" in page.url


async def scrape_naukri_jobs(page: Page, role: str, location: str, limit: int = 10) -> list[dict]:
    jobs = []
    search_url = (
        f"{NAUKRI_BASE_URL}/{role.lower().replace(' ', '-')}-jobs"
        f"?k={role.replace(' ', '+')}&l={location}"
    )
    await page.goto(search_url, timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 2, 4)

    cards = await page.query_selector_all(".jobTuple")
    for card in cards[:limit]:
        try:
            title = await safe_text(card, ".title")
            company = await safe_text(card, ".companyInfo strong")
            experience = await safe_text(card, ".exp")
            salary = await safe_text(card, ".salary")
            link_el = await card.query_selector("a.title")
            apply_url = (await link_el.get_attribute("href")) if link_el else ""

            # Click to get JD
            if apply_url:
                new_page = await page.context.new_page()
                await new_page.goto(apply_url, timeout=PLAYWRIGHT_TIMEOUT)
                await human_delay(new_page, 1, 3)
                jd_text = await safe_text(new_page, ".job-desc")
                await new_page.close()
            else:
                jd_text = ""

            if title and company:
                jobs.append({
                    "platform": "Naukri",
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": salary,
                    "experience": experience,
                    "jd_text": jd_text[:4000],
                    "apply_url": apply_url,
                })
        except Exception as e:
            print(f"[Naukri] Error: {e}")
            continue
    return jobs


# ── Indeed ─────────────────────────────────────────────────────────────────────

async def scrape_indeed_jobs(page: Page, role: str, location: str, limit: int = 10) -> list[dict]:
    jobs = []
    search_url = (
        f"{INDEED_BASE_URL}/jobs"
        f"?q={role.replace(' ', '+')}&l={location.replace(' ', '+')}"
        f"&fromage=3&sort=date"
    )
    await page.goto(search_url, timeout=PLAYWRIGHT_TIMEOUT)
    await human_delay(page, 2, 4)

    cards = await page.query_selector_all(".job_seen_beacon")
    for card in cards[:limit]:
        try:
            title = await safe_text(card, "h2.jobTitle span")
            company = await safe_text(card, ".companyName")
            loc = await safe_text(card, ".companyLocation")
            link_el = await card.query_selector("a")
            href = (await link_el.get_attribute("href")) if link_el else ""
            apply_url = f"{INDEED_BASE_URL}{href}" if href.startswith("/") else href

            jd_text = ""
            if apply_url:
                new_page = await page.context.new_page()
                try:
                    await new_page.goto(apply_url, timeout=PLAYWRIGHT_TIMEOUT)
                    await human_delay(new_page, 1, 3)
                    jd_text = await safe_text(new_page, "#jobDescriptionText")
                finally:
                    await new_page.close()

            if title and company:
                jobs.append({
                    "platform": "Indeed",
                    "title": title,
                    "company": company,
                    "location": loc,
                    "jd_text": jd_text[:4000],
                    "apply_url": apply_url,
                })
        except Exception as e:
            print(f"[Indeed] Error: {e}")
            continue
    return jobs


# ── Master scraper (sync wrapper for CrewAI) ──────────────────────────────────

def scrape_all_platforms(role: str, location: str, limit_per_platform: int = 5) -> list[dict]:
    """
    Synchronous wrapper that runs the async scraper.
    Scrapes LinkedIn, Naukri, and Indeed for jobs.
    Returns a combined list of job dicts.
    """
    async def _run():
        browser, context = await get_browser_context()
        page = await context.new_page()
        all_jobs = []
        try:
            prefs = load_preferences()

            # ── LinkedIn ──
            if prefs["platforms"].get("linkedin"):
                print(f"[Scout] Scraping LinkedIn: {role} in {location}")
                logged_in = await linkedin_login(page)
                if logged_in:
                    jobs = await scrape_linkedin_jobs(page, role, location, limit_per_platform)
                    all_jobs.extend(jobs)
                    print(f"[Scout] LinkedIn: {len(jobs)} jobs found")

            # ── Naukri ──
            if prefs["platforms"].get("naukri"):
                print(f"[Scout] Scraping Naukri: {role} in {location}")
                try:
                    await naukri_login(page)
                    jobs = await scrape_naukri_jobs(page, role, location, limit_per_platform)
                    all_jobs.extend(jobs)
                    print(f"[Scout] Naukri: {len(jobs)} jobs found")
                except Exception as e:
                    print(f"[Scout] Naukri failed: {e}")

            # ── Indeed ──
            if prefs["platforms"].get("indeed"):
                print(f"[Scout] Scraping Indeed: {role} in {location}")
                try:
                    jobs = await scrape_indeed_jobs(page, role, location, limit_per_platform)
                    all_jobs.extend(jobs)
                    print(f"[Scout] Indeed: {len(jobs)} jobs found")
                except Exception as e:
                    print(f"[Scout] Indeed failed: {e}")

        finally:
            await browser.close()
        return all_jobs

    return asyncio.run(_run())


def send_linkedin_inmail_sync(profile_url: str, message: str) -> bool:
    """Sync wrapper to send a LinkedIn connection + message."""
    async def _run():
        browser, context = await get_browser_context()
        page = await context.new_page()
        try:
            await linkedin_login(page)
            result = await linkedin_send_connection_with_note(page, profile_url, message)
            return result
        finally:
            await browser.close()
    return asyncio.run(_run())


def find_recruiters_sync(company: str) -> list[dict]:
    """Sync wrapper to find recruiters on LinkedIn."""
    async def _run():
        browser, context = await get_browser_context()
        page = await context.new_page()
        try:
            await linkedin_login(page)
            recruiters = await linkedin_find_recruiters(page, company)
            return recruiters
        finally:
            await browser.close()
    return asyncio.run(_run())


# ── CrewAI Tool Wrappers ──────────────────────────────────────────────────────

class JobScraperInput(BaseModel):
    role: str = Field(description="Job title to search for")
    location: str = Field(description="Location to search in")
    limit: int = Field(default=5, description="Max jobs per platform")


class PlaywrightJobScraperTool(BaseTool):
    name: str = "Job Scraper Tool"
    description: str = (
        "Scrapes LinkedIn, Naukri, and Indeed for job listings. "
        "Input: role (job title), location, limit. "
        "Returns a JSON list of job dicts with title, company, jd_text, apply_url, platform."
    )
    args_schema: type[BaseModel] = JobScraperInput

    def _run(self, role: str, location: str, limit: int = 5) -> str:
        import json
        jobs = scrape_all_platforms(role, location, limit)
        return json.dumps(jobs, indent=2)


class RecruiterFinderInput(BaseModel):
    company: str = Field(description="Company name to find recruiters for")


class RecruiterFinderTool(BaseTool):
    name: str = "Recruiter Finder Tool"
    description: str = (
        "Searches LinkedIn for HR/recruiter/talent acquisition professionals at a given company. "
        "Returns a list of {name, headline, profile_url}."
    )
    args_schema: type[BaseModel] = RecruiterFinderInput

    def _run(self, company: str) -> str:
        import json
        recruiters = find_recruiters_sync(company)
        return json.dumps(recruiters, indent=2)


class InMailInput(BaseModel):
    profile_url: str = Field(description="LinkedIn profile URL of the recruiter")
    message: str = Field(description="Personalized message to send (max 300 chars)")


class SendInMailTool(BaseTool):
    name: str = "LinkedIn InMail Tool"
    description: str = (
        "Sends a LinkedIn connection request with a personalized note to a recruiter. "
        "Input: profile_url, message (max 300 chars). Returns 'sent' or 'failed'."
    )
    args_schema: type[BaseModel] = InMailInput

    def _run(self, profile_url: str, message: str) -> str:
        success = send_linkedin_inmail_sync(profile_url, message[:300])
        return "sent" if success else "failed"
