"""
Generate fake CloudDash customers and push to HubSpot CRM.

Run once: python -m scripts.seed_hubspot

Creates ~50 contacts in HubSpot with realistic fields.
The Enrich node will query these by email during pipeline runs.

Emails are deterministic (not random) so they match the reporter
emails in seed_jira.py — otherwise every enrich() call misses.
"""

import os
import sys
import time
import random
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import HUBSPOT_ACCESS_TOKEN

HUBSPOT_API = "https://api.hubapi.com/crm/v3/objects/contacts"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# ─── Deterministic customer data ──────────────────────────
# These emails MUST match what seed_jira.py uses as reporter emails.

COMPANIES = [
    {"name": "Acme Corp", "domain": "acmecorp.com", "tier": "enterprise", "status": "active"},
    {"name": "Northwind Labs", "domain": "northwind.io", "tier": "pro", "status": "active"},
    {"name": "Contoso Ltd", "domain": "contoso.dev", "tier": "pro", "status": "active"},
    {"name": "Initech", "domain": "initech.co", "tier": "starter", "status": "active"},
    {"name": "Globex Inc", "domain": "globex.com", "tier": "starter", "status": "active"},
    {"name": "Pied Piper", "domain": "piedpiper.io", "tier": "pro", "status": "active"},
    {"name": "Hooli", "domain": "hooli.xyz", "tier": "enterprise", "status": "active"},
    {"name": "Bluth Company", "domain": "bluthco.com", "tier": "free", "status": "trial"},
    {"name": "Stark Industries", "domain": "starkindustries.com", "tier": "enterprise", "status": "active"},
    {"name": "Umbrella Corp", "domain": "umbrella.io", "tier": "starter", "status": "churned"},
]

PEOPLE = [
    {"first": "Priya", "last": "Sharma"},
    {"first": "Sam", "last": "Wilson"},
    {"first": "Alex", "last": "Chen"},
    {"first": "Nina", "last": "Patel"},
    {"first": "Dev", "last": "Kumar"},
]

JOB_TITLES = [
    "Product Manager", "Software Engineer", "Data Analyst",
    "Engineering Manager", "CTO", "DevOps Engineer",
    "VP of Engineering", "Marketing Manager", "Founder",
]


def generate_customers() -> list[dict]:
    """Generate deterministic customer list — every company gets every person."""
    customers = []
    rng = random.Random(42)  # fixed seed for reproducibility

    for company in COMPANIES:
        for person in PEOPLE:
            email = f"{person['first'].lower()}.{person['last'].lower()}@{company['domain']}"

            # Past ticket count scales by tier
            ticket_ranges = {
                "free": (0, 3),
                "starter": (1, 6),
                "pro": (2, 12),
                "enterprise": (5, 25),
            }
            min_t, max_t = ticket_ranges[company["tier"]]


            customers.append({
                "email": email,
                "firstname": person["first"],
                "lastname": person["last"],
                "company": company["name"],
                "jobtitle": rng.choice(JOB_TITLES),
                "message": f"Plan: {company['tier']} | Status: {company['status']} | Past tickets: {rng.randint(min_t, max_t)}",
            })

    return customers


def create_contact(customer: dict) -> bool:
    """Push one contact to HubSpot. Returns True if successful."""
    payload = {"properties": customer}
    response = requests.post(HUBSPOT_API, headers=HEADERS, json=payload)

    if response.status_code == 201:
        return True
    elif response.status_code == 409:
        print(f"  Skipped (duplicate): {customer['email']}")
        return False
    else:
        print(f"  Error ({response.status_code}): {response.text[:120]}")
        return False


def main():
    if not HUBSPOT_ACCESS_TOKEN:
        print("Error: HUBSPOT_ACCESS_TOKEN not set in .env")
        return

    customers = generate_customers()
    created = 0
    skipped = 0

    print(f"Generating {len(customers)} fake customers for CloudDash...\n")

    for i, customer in enumerate(customers):
        success = create_contact(customer)

        if success:
            created += 1
            print(f"  [{created}] {customer['firstname']} {customer['lastname']} "
                  f"({customer['email']}) — {customer['company']}")
        else:
            skipped += 1

        # Rate limit: HubSpot free = 100 req/10s
        time.sleep(0.15)

    print(f"\nDone. Created: {created}, Skipped: {skipped}")
    print(f"Total contacts: {len(customers)}")
    print("Verify at: https://app.hubspot.com/contacts/")

    # Print a few sample emails for reference
    print("\n--- Sample emails (use these in seed_jira.py) ---")
    for c in customers[:5]:
        print(f"  {c['email']}")


if __name__ == "__main__":
    main()