#!/usr/bin/env python3

import requests
from datetime import datetime, timedelta, timezone
import os

# ---------------- Slack Webhook ----------------
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL")

def send_to_slack(text):
    if not SLACK_WEBHOOK:
        print("Slack webhook missing")
        return
    payload = {"text": text}
    try:
        r = requests.post(SLACK_WEBHOOK, json=payload, timeout=10)
        r.raise_for_status()
        print("Sent to Slack")
    except Exception as e:
        print("Slack error:", e)

# ---------------- Filters ----------------------

ROLE_KEYWORDS = [
    "aws cloud engineer", "cloud engineer", "devops engineer",
    "cloud support", "cloud operations", "infrastructure engineer",
    "cloud associate", "aws associate"
]

LOCATIONS = ["remote", "bengaluru", "bangalore", "mysore", "chennai",
             "coimbatore", "kochi", "calicut", "kozhikode"]

EXP_KEYWORDS = ["0-1", "entry", "junior", "fresher", "0 years", "1 year", "0 to 1"]

HOURS_WINDOW = 48

# ---------------- Helpers ----------------------

def matches_role(title, description):
    text = (title + " " + (description or "")).lower()
    return any(k in text for k in ROLE_KEYWORDS)

def matches_location(location):
    if not location:
        return False
    location = location.lower()
    if "remote" in location:
        return True
    return any(loc in location for loc in LOCATIONS)

def matches_exp(text):
    if not text:
        return False
    text = text.lower()
    return any(k in text for k in EXP_KEYWORDS)

def within_hours(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except:
        return False
    return (datetime.now(timezone.utc) - dt) <= timedelta(hours=HOURS_WINDOW)

# ---------------- Job API 1: Remotive ----------------------

def search_remotive():
    url = "https://remotive.com/api/remote-jobs"
    results = []
    try:
        data = requests.get(url, timeout=20).json().get("jobs", [])
        for job in data:
            title = job.get("title", "")
            desc = job.get("description", "")
            loc = job.get("candidate_required_location", "")
            date = job.get("publication_date")

            if not (matches_role(title, desc) and matches_location(loc) and within_hours(date)):
                continue

            results.append({
                "title": title,
                "company": job.get("company_name"),
                "location": loc,
                "type": "Remote",
                "experience": "Entry-level (filtered)",
                "skills": ", ".join(job.get("tags", [])),
                "desc": desc[:300].replace("\n", " "),
                "url": job.get("url"),
                "source": "Remotive"
            })
    except Exception as e:
        print("Remotive error:", e)
    return results

# ---------------- Job API 2: ArbeitNow ----------------------

def search_arbeitnow():
    url = "https://www.arbeitnow.com/api/job-board-api"
    results = []
    try:
        data = requests.get(url, timeout=20).json().get("data", [])
        for job in data:
            title = job.get("title", "")
            desc = job.get("description", "")
            loc = job.get("location", "")
            date = job.get("created_at")

            if not (matches_role(title, desc) and matches_location(loc) and within_hours(date)):
                continue

            results.append({
                "title": title,
                "company": job.get("company_name"),
                "location": loc,
                "type": "Remote" if job.get("remote") else "On-site/Hybrid",
                "experience": job.get("experience_level") or "Not specified",
                "skills": ", ".join(job.get("tags", [])),
                "desc": desc[:300].replace("\n", " "),
                "url": job.get("url"),
                "source": "ArbeitNow"
            })
    except Exception as e:
        print("ArbeitNow error:", e)
    return results

# ---------------- Main ----------------------

def main():
    jobs = search_remotive() + search_arbeitnow()
    if not jobs:
        send_to_slack("No matching Cloud/DevOps jobs posted in last 48 hours.")
        return

    msg = "*🌤️ Daily Cloud / DevOps Job Alerts (Last 48 Hours)*\n"
    msg += f"Found *{len(jobs)}* matching jobs.\n\n"

    for j in jobs[:40]:  # limit Slack overflow
        msg += f"*{j['title']}* — `{j['company']}`\n"
        msg += f"📍 *Location:* {j['location']} | {j['type']}\n"
        msg += f"⭐ *Skills:* {j['skills']}\n"
        msg += f"🧪 *Experience:* {j['experience']}\n"
        msg += f"🔗 <{j['url']}>\n"
        msg += f"_{j['source']}_\n\n"

    send_to_slack(msg)

if __name__ == "__main__":
    main()
