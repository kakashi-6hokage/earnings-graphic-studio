# Earnings Graphic Studio — OAuth 2.1 hosted MCP

The Earnings Graphic Studio MCP service is deployed to Render Free at `https://earnings-graphic-studio.onrender.com/mcp`.

The owner-only login uses OAuth authorization code with PKCE S256, discovery metadata, constrained DCR, a protected resource identifier, and short-lived bearer access tokens. ChatGPT will display a **Connect / Authorize** flow when its MCP server connection is available. The owner enters a long private access code in the HTTPS sign-in page on the Render service, **not in chat**. The code is held in Render Environment as `MCP_OWNER_ACCESS_CODE` or (for migration) existing `MCP_BEARER_TOKEN`.

This custom one-owner authentication is intended solely for a public-data earnings rendering utility, **not** an audited identity provider or multi-user identity system. Do not use it with sensitive customer data. Continue to check access logs and rotate credentials if needed.

Source repository: https://github.com/kakashi-6hokage/earnings-graphic-studio
