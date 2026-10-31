# Earnings Graphic Studio

Deterministic editorial Sankey renderer for verified earnings ledgers. Supports GAAP reconciliation checks and two-decimal financial labels.

Deploy as a **Free Render web service** using the included Dockerfile. Store `MCP_BEARER_TOKEN` securely as a Render environment variable (never commit credentials). `/health` is public; `/mcp` requires a bearer token.

MCP tools: `get_earnings_template`, `validate_earnings_ledger`, `render_earnings_sankey`.

The renderer validates mathematical relationships, not the truth of company earnings filings. Visually inspect exported graphics before publication.
