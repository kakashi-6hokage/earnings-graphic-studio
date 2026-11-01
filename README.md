# Earnings Graphic Studio — OAuth 2.1 hosted MCP

The Earnings Graphic Studio MCP service is deployed to Render Free at `https://earnings-graphic-studio.onrender.com/mcp`.

The owner-only login uses OAuth authorization code with PKCE S256, discovery metadata, constrained DCR, a protected resource identifier, and short-lived bearer access tokens. ChatGPT will display a **Connect / Authorize** flow when its MCP server connection is available. The owner enters a long private access code in the HTTPS sign-in page on the Render service, **not in chat**. The code is held in Render Environment as `MCP_OWNER_ACCESS_CODE` or (for migration) existing `MCP_BEARER_TOKEN`.

This custom one-owner authentication is intended solely for a public-data earnings rendering utility, **not** an audited identity provider or multi-user identity system. Do not use it with sensitive customer data. Continue to check access logs and rotate credentials if needed.

Source repository: https://github.com/kakashi-6hokage/earnings-graphic-studio

## Finviz Elite API integration (read-only)

The existing authenticated MCP service now offers four tools:

- `finviz_connection_status` — reports whether the credential is configured, never the value.
- `get_finviz_statements` — quarterly/annual income, balance sheet, cash flow (Finviz Elite CSV with original unscaled amounts).
- `get_finviz_filings` — ticker SEC filing index.
- `get_finviz_earnings_calendar` — earnings dates and surprise figures for a date range.

**Credential setup:** Open [Render earnings-graphic-studio](https://dashboard.render.com/web/srv-dbinhufb9u1s73c0out0), select **Environment**, and add `FINVIZ_API_TOKEN` with the Finviz Elite token in Render's protected environment-variable editor. Never paste it into chat, a repository file, or a logging system. The token is added to outbound requests to the fixed HTTPS host `elite.finviz.com` only. Requests require existing ChatGPT OAuth authorization to the MCP service. No public proxy to Finviz is exposed.

Statement selectors: `IA`, `IQ` (default), `BA`, `BQ`, `CA`, `CQ`. Optional growth `yoy`, `yoy_pct`, `qoq`, `qoq_pct` (QoQ for quarters only). Sources: FactSet (default) or Reuters. CSV numbers are **full source-currency units**; do not assume USD. Corroborate financial data against SEC/company filings and respect Finviz subscription redistribution terms.

Rate limit: The newer Elite API dashboard says 10 requests per 5 seconds across endpoints (an older help article differs). The adapter surfaces HTTP 429 and callers should retry conservatively. Test safely with `python tests/test_finviz.py`. The local stdio renderer remains unchanged; Finviz tools are exposed on the hosted MCP server only.
