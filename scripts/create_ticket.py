"""
Create Jira ticket(s) via API — triggers the webhook automatically,
no manual GUI entry needed.

Usage:
    Single ticket:
        python -m scripts.create_ticket --subject "How do I export CSV?" --email "alex.chen@bluthco.com" --body "I need to export my data as CSV." --priority Low

    Batch of 30 (default, weighted toward auto-respond):
        python -m scripts.create_ticket --batch
"""

import os
import sys
import time
import argparse
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

JIRA_API = f"{JIRA_BASE_URL}/rest/api/3/issue"
AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def create_ticket(subject: str, email: str, body: str, priority: str = "Medium", labels=None):
    description_text = f"Customer: {email}\n\n{body}"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": subject,
            "description": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description_text}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority},
            "labels": labels or ["support-ticket"],
        }
    }

    response = requests.post(JIRA_API, headers=HEADERS, auth=AUTH, json=payload)

    if response.status_code == 201:
        data = response.json()
        key = data.get("key")
        print(f"Created: {key}")
        print(f"URL: {JIRA_BASE_URL}/browse/{key}")
        return key
    else:
        print(f"Error ({response.status_code}): {response.text}")
        return None


# ─── Batch ticket set: ~22 auto-respond, ~5 human-review, ~3 escalate ──

BATCH_TICKETS = [
    # AUTO_RESPOND candidates
    ("How do I export my data as CSV?", "alex.chen@bluthco.com",
     "I need to download my project data as a CSV file for a report.", "Low"),
    ("How many dashboards can I create on Starter?", "nina.patel@initech.co",
     "I'm on the Starter plan and want to know the dashboard limit.", "Low"),
    ("When is my next invoice date?", "dev.kumar@globex.com",
     "I signed up mid-month and want to know exactly when I'll be billed next.", "Low"),
    ("How do I invite my team members?", "sam.wilson@northwind.io",
     "I just created my CloudDash account and need to add 4 people from my team.", "Low"),
    ("My dashboard is loading slowly", "alex.chen@contoso.dev",
     "My main dashboard with lots of widgets takes 10-15 seconds to load. Is there a fix?", "Medium"),
    ("Does CloudDash support SSO with Okta?", "sam.wilson@piedpiper.io",
     "We use Okta for internal tools. Does CloudDash support SAML SSO?", "Low"),
    ("How do I update my payment method?", "nina.patel@initech.co",
     "My card expired and I need to update it before the next billing cycle.", "Medium"),
    ("What's included in the Pro plan?", "dev.kumar@globex.com",
     "Considering upgrading from Starter. What extra features come with Pro?", "Low"),
    ("How do I reset my password?", "alex.chen@bluthco.com",
     "I forgot my password and the reset link isn't arriving. Can you help?", "Medium"),
    ("How do I export a dashboard as PDF?", "sam.wilson@northwind.io",
     "Need to email a weekly PDF report to my manager. Where's that option?", "Low"),
    ("Is there an API rate limit?", "dev.kumar@contoso.dev",
     "Building an integration and want to know the API rate limits on Pro.", "Low"),
    ("How do I connect Google Sheets?", "nina.patel@piedpiper.io",
     "I want to pull data from a Google Sheet into a dashboard. How do I set that up?", "Low"),
    ("Can I schedule automatic report emails?", "alex.chen@contoso.dev",
     "I'd like a weekly PDF sent to my email automatically. Is that possible?", "Low"),
    ("How do I change user roles on my team?", "sam.wilson@piedpiper.io",
     "One of my teammates needs Editor access instead of Viewer. How do I change that?", "Low"),
    ("What happens if my payment fails?", "dev.kumar@globex.com",
     "My card was declined this month. What happens to my account now?", "Medium"),
    ("How do I cancel my subscription?", "nina.patel@initech.co",
     "I need to cancel our plan. Will I lose my data right away?", "Medium"),
    ("Salesforce sync keeps failing", "alex.chen@contoso.dev",
     "Our Salesforce integration fails about 1 in 10 syncs with a timeout error.", "Medium"),
    ("PDF export just spins and never finishes", "sam.wilson@northwind.io",
     "Clicking Export > PDF causes the spinner to run forever on Chrome.", "High"),
    ("How do I get an invoice for last month?", "dev.kumar@globex.com",
     "Need a downloadable invoice PDF for our accounting team.", "Low"),
    ("What's your uptime SLA?", "nina.patel@piedpiper.io",
     "Evaluating CloudDash for our team — what uptime guarantee do you offer?", "Low"),
    ("Is CloudDash SOC 2 certified?", "alex.chen@bluthco.com",
     "Our security team wants to know if you have SOC 2 Type II certification.", "Low"),
    ("Locked out after failed login attempts", "sam.wilson@piedpiper.io",
     "Tried logging in too many times and now it says my account is locked.", "High"),

    # HUMAN_REVIEW candidates
    ("I was charged twice this month", "priya.sharma@acmecorp.com",
     "Two charges of $49.99 on my August invoice. This is a duplicate charge.", "High"),
    ("Charged after cancellation", "priya.sharma@hooli.xyz",
     "Cancelled two weeks ago but got charged again today. Please refund.", "High"),
    ("Request for refund - unused subscription", "priya.sharma@starkindustries.com",
     "Signed up 5 days ago, haven't used it, want a full refund.", "Medium"),
    ("Billing question from our finance team", "priya.sharma@acmecorp.com",
     "Our finance team needs a breakdown of last quarter's charges.", "Medium"),
    ("Dashboard data looks wrong after timezone change", "priya.sharma@hooli.xyz",
     "Changed timezone and now historical totals don't match what they showed before.", "High"),

    # ESCALATE candidates
    ("Delete my account and all data", "alex.chen@contoso.dev",
     "I want to completely delete my CloudDash account. This is a GDPR request.", "High"),
    ("Data breach concern - need immediate response", "priya.sharma@hooli.xyz",
     "Found another company's data in one of our shared dashboards. Possible breach.", "Highest"),
    ("Considering legal action over data loss", "priya.sharma@starkindustries.com",
     "We lost a week of data and our legal team is reviewing the SLA for damages.", "Highest"),
]


def run_batch():
    print(f"Creating {len(BATCH_TICKETS)} tickets...\n")

    created = 0
    failed = 0

    for i, (subject, email, body, priority) in enumerate(BATCH_TICKETS, 1):
        print(f"[{i}/{len(BATCH_TICKETS)}] {subject}")
        key = create_ticket(subject, email, body, priority)

        if key:
            created += 1
        else:
            failed += 1

        time.sleep(2)

    print(f"\nDone. Created: {created}, Failed: {failed}")
    print("Watch your worker terminal — tickets will process as the queue drains.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="How do I export my data as CSV?")
    parser.add_argument("--email", default="alex.chen@bluthco.com")
    parser.add_argument("--body", default="I need to download my project data as a CSV file for a report.")
    parser.add_argument("--priority", default="Low")
    parser.add_argument("--batch", action="store_true", help="Create all 30 batch tickets instead of a single one")
    args = parser.parse_args()

    if args.batch:
        run_batch()
    else:
        create_ticket(args.subject, args.email, args.body, args.priority)