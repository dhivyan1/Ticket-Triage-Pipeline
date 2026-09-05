# Single sign-on (SSO) setup

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
