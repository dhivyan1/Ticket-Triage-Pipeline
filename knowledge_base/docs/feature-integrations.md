# Integrations

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
