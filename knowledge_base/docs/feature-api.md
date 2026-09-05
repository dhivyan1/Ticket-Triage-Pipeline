# CloudDash API

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
