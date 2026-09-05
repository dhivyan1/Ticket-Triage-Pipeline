# Known issues

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
