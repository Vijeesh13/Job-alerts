#!/usr/bin/env python3

import requests
from datetime import datetime, timedelta, timezone
import os
import re

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL")
HOURS_WINDOW = 48  # only include jobs posted in last n hours

ROLE_KEYWORDS = [
    "aws cloud engineer", "aws cloud associate", "cloud engineer",
    "cloud associate", "devops engineer", "entry level devops",
    "cloud support associate", "cloud operations engineer",
    "infrastructure engineer"
]

LOCATIONS = ["remote", "india", "bengaluru", "bangalore", "mysore", "chennai",
             "coimbatore", "kochi", "calicut", "kozhikode"]

EXP_KEYWORDS = ["entry", "junior", "fresher", "0-1", "0 to 1", "1 year"]

LINKEDIN_KEYWORDS = [
    "AWS Cloud Engineer associate",
    "DevOps Engineer",
    "Cloud Support Associate",
    "Cloud Operations Engineer associate",
    "Infrastructure Engineer Associate"
]

NAUKRI_KEYWORDS = LINKEDIN_KEYWORDS[:]  # same as LinkedIn

# -------------------------------------------------------------------
# FILTER HELPERS
# -------------------------------------------------------------------

def matches_role(title, desc):
    text = (title + " " + (desc or "")).lower()
    return any(k in text for k in ROLE_KEYWORDS)

def matches_location(loc):
    if not loc:
        return False
    loc = loc.lower()
    if "remote" in loc:
        return True
    return any(x in loc for x in LOCATIONS)

def matches_exp(text):
    if not text:
        return False
    text = text.lower()
    return any(k in text for k in EXP_KEYWORDS)

def within_hours(dt_str):
    if not dt_str:
        return False
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt) <= timedelta(hours=HOURS_WINDOW)
    except:
        return False

# -------------------------------------------------------------------
# SLACK SENDERS (BLOCK KIT + PAGINATION + THREADING)
# -------------------------------------------------------------------

def slack_post(payload):
    r = requests.post(SLACK_WEBHOOK, json=payload)
    if r.status_code != 200:
        print("Slack error:", r.text)
    return r

def send_blockkit_paginated(blocks, chunk_size=8):
    """Send Block Kit messages in a Slack thread with pagination."""
    header = {"text": "*🌤️ Daily Cloud & DevOps Job Alerts*\nJobs posted in last 48 hours."}
    r = slack_post({"text": header["text"]})

    if r.status_code != 200:
        print("Failed to send header")
        return

    thread_ts = r.json().get("ts")

    for i in range(0, len(blocks), chunk_size):
        page_blocks = blocks[i:i + chunk_size]
        payload = {"thread_ts": thread_ts, "blocks": page_blocks}
        slack_post(payload)

# -------------------------------------------------------------------
# BLOCK KIT JOB CARD TEMPLATE
# -------------------------------------------------------------------

def build_job_block(job):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{job['title']}* — `{job['company']}`\n"
                    f"*Location:* {job['location']} | *Type:* {job['type']}\n"
                    f"*Experience:* {job['experience']}\n"
                    f"*Skills:* {job['skills']}"
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Job"},
                    "url": job["url"]
                }
            ]
        },
        {"type": "divider"}
    ]

# -------------------------------------------------------------------
# JOB SOURCE 1 — REMOTIVE API
# -------------------------------------------------------------------

def search_remotive():
    results = []
    try:
        data = requests.get("https://remotive.com/api/remote-jobs", timeout=15).json().get("jobs", [])
        for job in data:
            title, desc = job.get("title", ""), job.get("description", "")
            loc = job.get("candidate_required_location", "")
            date = job.get("publication_date")

            if not (matches_role(title, desc) and matches_location(loc) and within_hours(date)):
                continue

            results.append({
                "title": title,
                "company": job.get("company_name"),
                "location": loc,
                "type": "Remote",
                "experience": "Entry",
                "skills": ", ".join(job.get("tags", [])),
                "url": job.get("url"),
                "source": "Remotive"
            })
    except:
        pass
    return results

# -------------------------------------------------------------------
# JOB SOURCE 2 — ARBEITNOW
# -------------------------------------------------------------------

def search_arbeitnow():
    results = []
    try:
        data = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=15).json().get("data", [])
        for job in data:
            title, desc, loc = job.get("title", ""), job.get("description", ""), job.get("location", "")
            date = job.get("created_at")

            if not (matches_role(title, desc) and matches_location(loc) and within_hours(date)):
                continue

            results.append({
                "title": title,
                "company": job.get("company_name"),
                "location": loc,
                "type": "Remote" if job.get("remote") else "Hybrid/On-site",
                "experience": job.get("experience_level") or "Entry",
                "skills": ", ".join(job.get("tags", [])),
                "url": job.get("url"),
                "source": "ArbeitNow"
            })
    except:
        pass
    return results

# -------------------------------------------------------------------
# JOB SOURCE 3 — LEVER ATS
# -------------------------------------------------------------------

def search_lever():
    results = []
    companies = ["netflix", "shopify", "datadog", "dropbox", "snyk"]

    for c in companies:
        try:
            url = f"https://api.lever.co/v0/postings/{c}?mode=json"
            postings = requests.get(url, timeout=15).json()

            for job in postings:
                title = job.get("text", "")
                desc = job.get("description", "")
                loc = job.get("categories", {}).get("location", "Remote")

                if not (matches_role(title, desc) and matches_location(loc)):
                    continue

                results.append({
                    "title": title,
                    "company": c.capitalize(),
                    "location": loc,
                    "type": "Unknown",
                    "experience": "Not specified",
                    "skills": "N/A",
                    "url": job.get("hostedUrl"),
                    "source": "Lever"
                })
        except:
            pass

    return results

# -------------------------------------------------------------------
# JOB SOURCE 4 — GREENHOUSE ATS
# -------------------------------------------------------------------

def search_greenhouse():
    results = []
    companies = ["cloudflare", "airbnb", "twilio"]  # extendable

    for c in companies:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{c}/jobs"
            data = requests.get(url, timeout=15).json().get("jobs", [])

            for job in data:
                title = job.get("title", "")
                loc = job.get("location", {}).get("name", "")
                desc = job.get("content", "")

                if not (matches_role(title, desc) and matches_location(loc)):
                    continue

                results.append({
                    "title": title,
                    "company": c.capitalize(),
                    "location": loc,
                    "type": "Unknown",
                    "experience": "Not specified",
                    "skills": "N/A",
                    "url": job.get("absolute_url"),
                    "source": "Greenhouse"
                })
        except:
            pass

    return results

# -------------------------------------------------------------------
# JOB SOURCE 5 — LINKEDIN SCRAPER (JSON LOAD)
# -------------------------------------------------------------------

def search_linkedin():
    results = []
    for keyword in LINKEDIN_KEYWORDS:
        try:
            url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={keyword.replace(' ', '%20')}&location=India&f_TPR=r86400"
            )
            html = requests.get(url, timeout=15).text
            postings = re.findall(r'/jobs/view/(\d+)', html)

            for job_id in postings:
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                title = keyword
                loc = "India"

                results.append({
                    "title": title,
                    "company": "LinkedIn Listing",
                    "location": loc,
                    "type": "Unknown",
                    "experience": "Entry",
                    "skills": "N/A",
                    "url": job_url,
                    "source": "LinkedIn"
                })
        except:
            pass

    return results

# -------------------------------------------------------------------
# JOB SOURCE 6 — INDEED (India)
# -------------------------------------------------------------------

def search_indeed():
    results = []
    base_url = "https://in.indeed.com/jobs?q={}&fromage=1"

    for keyword in LINKEDIN_KEYWORDS:
        try:
            url = base_url.format(keyword.replace(" ", "+"))
            html = requests.get(url, timeout=15).text

            titles = re.findall(r'jobTitle":"(.*?)"', html)
            companies = re.findall(r'companyName":"(.*?)"', html)
            locations = re.findall(r'formattedLocation":"(.*?)"', html)
            ids = re.findall(r'"jobkey":"(.*?)"', html)

            for i in range(min(len(titles), len(companies), len(ids))):
                if not matches_role(titles[i], titles[i]):
                    continue
                loc = locations[i] if i < len(locations) else "India"

                results.append({
                    "title": titles[i],
                    "company": companies[i],
                    "location": loc,
                    "type": "Unknown",
                    "experience": "Entry",
                    "skills": "N/A",
                    "url": f"https://in.indeed.com/viewjob?jk={ids[i]}",
                    "source": "Indeed"
                })
        except:
            pass

    return results

# -------------------------------------------------------------------
# JOB SOURCE 7 — NAUKRI SCRAPER
# -------------------------------------------------------------------

def search_naukri():
    results = []
    for keyword in NAUKRI_KEYWORDS:
        try:
            url = f"https://www.naukri.com/{keyword.replace(' ', '-')}-jobs?k={keyword.replace(' ', '%20')}"
            html = requests.get(url, timeout=15).text

            titles = re.findall(r'title="(.*?)"', html)
            companies = re.findall(r'{"name":"(.*?)"', html)
            links = re.findall(r'href="(https://www.naukri.com/.*?)"', html)

            for i in range(min(len(titles), len(companies), len(links))):
                if not matches_role(titles[i], titles[i]):
                    continue
                results.append({
                    "title": titles[i],
                    "company": companies[i],
                    "location": "India",
                    "type": "Unknown",
                    "experience": "Entry",
                    "skills": "N/A",
                    "url": links[i],
                    "source": "Naukri"
                })
        except:
            pass
    return results

# -------------------------------------------------------------------
# MAIN AGGREGATOR
# -------------------------------------------------------------------

def main():
    jobs = (
        search_remotive()
        + search_arbeitnow()
        + search_lever()
        + search_greenhouse()
        + search_linkedin()
        + search_indeed()
        + search_naukri()
    )

    if not jobs:
        slack_post({"text": "No matching jobs found in last 48 hours."})
        return

    # Convert to Block Kit cards
    blocks = []
    for job in jobs:
        blocks += build_job_block(job)

    send_blockkit_paginated(blocks, chunk_size=8)

# -------------------------------------------------------------------

if __name__ == "__main__":
    main()
