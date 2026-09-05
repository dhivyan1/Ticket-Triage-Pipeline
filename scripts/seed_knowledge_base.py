"""
Generate CloudDash help center articles.

Run once: python -m scripts.seed_knowledge_base

Creates markdown files in knowledge_base/docs/ that serve as
the RAG source of truth. These are the docs the Retrieve node
searches when a ticket comes in.
"""

import os

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "docs")

ARTICLES = {

    # ─── Billing ──────────────────────────────────────────

    "billing-plans.md": """# CloudDash pricing plans

CloudDash offers four pricing tiers:

## Free plan
- Up to 3 users
- 2 projects
- Basic dashboard templates
- Community support only
- 1 GB storage

## Starter plan — $19/month per user
- Up to 10 users
- 10 projects
- Custom dashboards
- Email support (24-hour response time)
- 10 GB storage
- CSV export

## Pro plan — $49/month per user
- Unlimited users
- Unlimited projects
- Advanced analytics and custom formulas
- Priority email support (4-hour response time)
- 100 GB storage
- PDF and CSV export
- API access
- SSO integration

## Enterprise plan — $299/month per user
- Everything in Pro
- Dedicated account manager
- 99.9 percent uptime SLA
- Custom integrations
- Unlimited storage
- Phone support
- Audit logs
- Data residency options
""",

    "billing-faq.md": """# Billing frequently asked questions

## When am I billed?
CloudDash bills on the 1st of every month. Your first bill is prorated based on your signup date.

## How do I update my payment method?
Go to Settings > Billing > Payment Method. Click "Update card" and enter your new details. Changes apply to the next billing cycle.

## Can I switch plans?
Yes. Go to Settings > Billing > Change Plan. Upgrades take effect immediately and are prorated. Downgrades take effect at the start of the next billing cycle.

## What happens if my payment fails?
We retry the charge 3 times over 7 days. After the third failure, your account is downgraded to the Free plan. No data is deleted — upgrade again to restore access.

## How do I get an invoice?
Go to Settings > Billing > Invoice History. You can download PDF invoices for any past month.

## How do I cancel my subscription?
Go to Settings > Billing > Cancel Subscription. Your access continues until the end of the current billing period. After cancellation, your account reverts to the Free plan. No data is deleted for 90 days.
""",

    "billing-refund-policy.md": """# Refund policy

## Standard refunds
CloudDash offers full refunds within 14 days of any charge. After 14 days, refunds are prorated based on remaining days in the billing cycle.

## Duplicate charges
If you were charged twice for the same billing period, contact support. We will refund the duplicate charge within 5-7 business days.

## How to request a refund
Contact support with your account email and the charge date. Include the transaction ID from your invoice if possible. Our billing team will process eligible refunds within 5-7 business days.

## Non-refundable items
- Custom integration development fees
- Enterprise onboarding fees
- Charges older than 90 days
""",

    # ─── Account & Authentication ─────────────────────────

    "account-getting-started.md": """# Getting started with CloudDash

## Creating your account
1. Visit app.clouddash.io/signup
2. Enter your work email and create a password
3. Verify your email via the confirmation link
4. Complete your profile (name, company, role)
5. Create your first project or use a template

## Inviting team members
Go to Settings > Team > Invite. Enter their email addresses. They will receive an invitation link. New members default to the Viewer role — you can change this in Settings > Team > Roles.

## Roles and permissions
- **Viewer**: Can view dashboards and reports. Cannot edit.
- **Editor**: Can create and edit dashboards, add data sources.
- **Admin**: Full access including billing, team management, and integrations.
- **Owner**: Account owner. Can transfer ownership and delete the account.
""",

    "account-password-reset.md": """# Password reset and login issues

## Forgot your password
1. Go to app.clouddash.io/login
2. Click "Forgot password?"
3. Enter your account email
4. Check your inbox for the reset link (arrives within 2 minutes)
5. Click the link and set a new password

## Reset link not arriving
- Check your spam/junk folder
- Make sure you are entering the same email used to create the account
- If using a company email, check with your IT team — some firewalls block automated emails
- Try requesting the link again after 5 minutes

## Account locked
After 5 failed login attempts, your account is locked for 15 minutes. Wait 15 minutes and try again. If you still cannot log in, reset your password.

## Two-factor authentication (2FA)
If you have 2FA enabled and lost access to your authenticator app, contact support with your account email. We will verify your identity and disable 2FA so you can log in and re-enable it.
""",

    "account-sso.md": """# Single sign-on (SSO) setup

SSO is available on the Pro and Enterprise plans.

## Supported providers
- Okta
- Azure Active Directory
- Google Workspace
- OneLogin
- Any SAML 2.0 compatible provider

## Setup steps
1. Go to Settings > Security > SSO
2. Select your identity provider
3. Enter your SSO metadata URL or upload the metadata XML
4. Map the required attributes (email, first name, last name)
5. Test the connection with a test user
6. Enable SSO for your organization

## Enforcing SSO
Once SSO is configured, admins can enforce it for all users under Settings > Security > Require SSO. When enforced, password login is disabled for all non-owner accounts.

## Troubleshooting
- "SSO configuration error": Verify your metadata URL is accessible and the certificate has not expired
- "User not found": The email in your identity provider must match the CloudDash account email exactly
- "SAML response invalid": Check that the clock on your identity provider server is synchronized (within 5 minutes of UTC)
""",

    # ─── Features ─────────────────────────────────────────

    "feature-dashboards.md": """# Creating and managing dashboards

## Creating a new dashboard
1. Click "+ New Dashboard" from the sidebar
2. Choose a blank canvas or select a template
3. Add widgets by clicking "+ Add Widget"
4. Configure each widget's data source and visualization type

## Available widget types
- Line chart, bar chart, pie chart, area chart
- KPI number card
- Data table
- Text/markdown block
- Embedded iframe

## Sharing dashboards
- **Internal sharing**: Click "Share" and add team members by email. Set permissions to View or Edit.
- **Public link**: Click "Share" > "Create public link". Anyone with the link can view the dashboard. Public links do not require a CloudDash account.
- **Scheduled reports**: Click "Share" > "Schedule". Set frequency (daily, weekly, monthly) and recipients. Reports are delivered as PDF attachments.

## Dashboard limits
- Free: 5 dashboards
- Starter: 20 dashboards
- Pro: Unlimited
- Enterprise: Unlimited
""",

    "feature-export.md": """# Exporting data and reports

## Export formats
- **CSV**: Available on all plans. Exports raw data from any widget or data table.
- **PDF**: Available on Starter and above. Exports the full dashboard as a formatted PDF.
- **PNG**: Available on all plans. Exports individual widgets as images.

## How to export
1. Open the dashboard you want to export
2. Click the "Export" button in the top-right corner
3. Select your format (CSV, PDF, or PNG)
4. For CSV: choose which widgets to include
5. Click "Download"

## Scheduled exports
Pro and Enterprise users can schedule automatic exports:
1. Go to the dashboard > Export > Schedule
2. Set frequency and format
3. Add recipient email addresses
4. Exports are sent as email attachments

## Troubleshooting export issues
- **PDF export hangs or spins**: Clear your browser cache and retry. If the issue persists, try a different browser. This is a known issue with Chrome when the dashboard has more than 20 widgets.
- **CSV export is empty**: Make sure the dashboard has loaded all data before exporting. Refresh the page and wait for all widgets to display data.
- **Export file is too large**: For dashboards with large datasets, use filters to narrow the date range before exporting.
""",

    "feature-api.md": """# CloudDash API

The CloudDash API is available on Pro and Enterprise plans.

## Authentication
All API requests require a bearer token. Generate one at Settings > API > Create Token. Tokens do not expire but can be revoked at any time.

```
Authorization: Bearer your-api-token
```

## Base URL
```
https://api.clouddash.io/v1
```

## Rate limits
- Pro: 100 requests per minute
- Enterprise: 500 requests per minute
- Exceeding the limit returns HTTP 429. Retry after the number of seconds in the Retry-After header.

## Common endpoints
- GET /projects — list all projects
- GET /dashboards — list all dashboards
- GET /dashboards/{id}/data — get dashboard data as JSON
- POST /data-sources — create a new data source
- GET /users — list team members

## Error codes
- 400: Bad request — check your request body
- 401: Unauthorized — check your API token
- 403: Forbidden — your plan does not include API access
- 404: Not found — the resource does not exist
- 429: Rate limited — slow down and retry
- 500: Server error — contact support
""",

    "feature-integrations.md": """# Integrations

## Supported data source integrations
CloudDash connects to the following data sources:
- PostgreSQL, MySQL, Microsoft SQL Server
- Google Sheets, Google Analytics
- Salesforce
- Stripe
- HubSpot
- REST API (custom)
- CSV file upload

## Setting up an integration
1. Go to Settings > Integrations > Add New
2. Select the data source type
3. Enter connection credentials (host, port, database, username, password)
4. Test the connection
5. Select which tables or endpoints to sync
6. Set sync frequency (hourly, daily, or real-time for supported sources)

## Troubleshooting integrations
- **Connection failed**: Verify credentials and ensure your database allows connections from CloudDash IP ranges (listed in Settings > Integrations > IP Allowlist)
- **Sync stalled**: Check Settings > Integrations > Sync History for error details. Common cause: the source schema changed (new columns, renamed tables)
- **Data mismatch**: CloudDash caches data between syncs. Click "Force Sync" to pull the latest data immediately
""",

    # ─── Known Issues & Troubleshooting ───────────────────

    "known-issues.md": """# Known issues

## PDF export timeout on Chrome (reported August 2026)
**Status**: Fix in progress, expected within 48 hours.
**Affected**: Chrome browser on all operating systems.
**Symptoms**: Clicking "Export as PDF" causes the spinner to run indefinitely. The export never completes.
**Workaround**: Clear your browser cache (Settings > Privacy > Clear browsing data), then retry. Alternatively, use Firefox or Safari, which are not affected.

## Dashboard loading slow with 50+ widgets (reported July 2026)
**Status**: Optimization scheduled for next release.
**Symptoms**: Dashboards with more than 50 widgets take 10-15 seconds to load.
**Workaround**: Split large dashboards into multiple smaller ones. Use the "Dashboard Group" feature to organize them.

## Salesforce sync intermittent failures (reported August 2026)
**Status**: Under investigation.
**Symptoms**: Salesforce data source sync fails approximately 10% of the time with a timeout error.
**Workaround**: Click "Force Sync" to retry. If the issue persists, disconnect and reconnect the Salesforce integration.

## Google Sheets real-time sync delay
**Status**: By design.
**Symptoms**: Changes in Google Sheets take up to 5 minutes to appear in CloudDash.
**Explanation**: Google Sheets API has rate limits. CloudDash polls every 5 minutes to stay within limits. For faster updates, use the "Force Sync" button.
""",

    "troubleshooting-general.md": """# General troubleshooting

## Dashboard not loading
1. Check your internet connection
2. Try a hard refresh (Ctrl+Shift+R on Windows, Cmd+Shift+R on Mac)
3. Clear your browser cache
4. Try a different browser
5. Check status.clouddash.io for any ongoing outages
6. If the issue persists, contact support with your browser version and a screenshot of any error messages

## Data not updating
1. Go to Settings > Integrations and check the sync status of your data source
2. If the last sync shows an error, click "View Details" for the specific error message
3. Click "Force Sync" to trigger an immediate data pull
4. If using Google Sheets, wait up to 5 minutes for changes to propagate

## Widget showing "No data"
- Verify the data source is connected and syncing successfully
- Check if filters on the widget are too restrictive
- Ensure the date range includes data — try expanding to "Last 30 days"
- If the data source schema changed, you may need to re-map the widget's columns

## Performance issues
- Reduce the number of widgets per dashboard (recommended: under 30)
- Use date filters to limit the data range
- For large datasets (1M+ rows), use aggregated views instead of raw data
- Check if other browser extensions are interfering — try incognito mode

## Email notifications not arriving
- Check your spam/junk folder
- Add notifications@clouddash.io to your email allowlist
- Go to Settings > Notifications and verify your email preferences
- If using a company email, ask your IT team to allowlist the CloudDash domain
""",

    # ─── Policies ─────────────────────────────────────────

    "sla-policy.md": """# Service level agreement (SLA)

## Uptime guarantees
- Free and Starter plans: No uptime guarantee (best effort)
- Pro plan: 99.5% monthly uptime
- Enterprise plan: 99.9% monthly uptime

## Uptime calculation
Uptime is calculated as total minutes in the month minus downtime minutes, divided by total minutes in the month. Scheduled maintenance windows (announced 48 hours in advance) are excluded from downtime calculations.

## Support response times
- Free: Community forum only, no guaranteed response time
- Starter: Email support, 24-hour response time during business hours
- Pro: Priority email support, 4-hour response time during business hours
- Enterprise: Phone and email support, 1-hour response time, 24/7 coverage

## Credits for downtime
Enterprise customers are eligible for service credits if the monthly uptime falls below the guaranteed level:
- Below 99.9% but above 99.0%: 10% credit on monthly bill
- Below 99.0% but above 95.0%: 25% credit
- Below 95.0%: 50% credit

Credits must be requested within 30 days of the affected month.
""",

    "data-security.md": """# Data security and privacy

## Data encryption
- All data is encrypted in transit using TLS 1.3
- All data is encrypted at rest using AES-256
- API tokens are hashed and never stored in plain text

## Data residency
Enterprise customers can choose their data region:
- United States (default)
- European Union
- Asia Pacific (Singapore)

## Data retention
- Active accounts: Data is retained as long as the account is active
- Cancelled accounts: Data is retained for 90 days after cancellation, then permanently deleted
- Deleted projects: Project data is soft-deleted and recoverable for 30 days, then permanently deleted

## Compliance
CloudDash is SOC 2 Type II certified and GDPR compliant. Enterprise customers can request our latest audit report by contacting their account manager.

## Reporting security issues
If you discover a security vulnerability, please report it to security@clouddash.io. We respond to all security reports within 24 hours.
""",
}


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    for filename, content in ARTICLES.items():
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"Created: {filepath}")

    print(f"\nDone. {len(ARTICLES)} articles written to {DOCS_DIR}")


if __name__ == "__main__":
    main()