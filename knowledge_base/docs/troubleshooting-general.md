# General troubleshooting

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
