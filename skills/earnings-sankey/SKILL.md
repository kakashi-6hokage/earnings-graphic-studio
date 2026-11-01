---
name: earnings-sankey
description: Use this workflow whenever the user wants a quarterly or annual income-statement earnings Sankey, especially in the polished Amazon/Alphabet editorial style.
---
# Earnings Graphic Studio

## Required flow
1. Research the latest **released** quarter from company IR, SEC/regulator, and Quartr when available. Do not invent undisclosed segments, release dates or line items. The vector renderer does not fetch financial data itself, but the hosted MCP exposes Finviz Elite data tools when connected.
2. Create a reconciled JSON ledger using `references/ledger-format.md`. Include full-precision values and data provenance. Treat IFRS/GAAP differences faithfully; gross profit/operating profit may not be reported for financial services. If unsupported, explain rather than invent.
3. Prefer native ChatGPT image generation for the polished static infographic, with the user's latest reference image guiding the composition. Use the connected `validate_earnings_ledger` and `render_earnings_sankey` MCP tools when available to calculate/verify exact financial geometry. Do not claim native AI alone guarantees numerically exact ribbon widths. Never claim a tool ran when it did not.
4. Use the strongest current user reference (Amazon, ZIM, ExxonMobil) as the visual target; `amazon_editorial_v1` is only a fallback. Do not copy publishers' watermarks or attribution.
5. Keep a single wide 16:9 canvas. Revenue ribbons should converge into the central bar from both above and below, with no wasteful lower-left whitespace. Use only the accounting stages actually supported by issuer disclosures, especially for financial services. For signed negative income, clearly label the adjustment rather than drawing fake positive conservation.
6. Display financial amounts using **at most two decimals**, preserving full precision for ribbon geometry. Put a verified, short quarterly insight in the header rather than generic “How revenue became profit.” Include YoY where supported, and percentage-point margin movements where appropriate.
7. Inspect the **actual generated PNG/SVG** visually against the available Amazon reference. Financial checks passing does not imply design approval. QA must explicitly check label overlap, clipping, curved ribbon continuity, hierarchy, readable labels, wordmark placement, monetary formatting, and meaningful relative widths.
8. If QA fails, correct and rerender; do not assert final approval based merely on the MCP tool succeeding. Deliver a verified graphic link with primary-source citations, a short takeaway, and caveats.

## What this plugin is
The repository supports both a local stdio renderer and an existing OAuth-protected hosted MCP server at https://earnings-graphic-studio.onrender.com/mcp. Availability in any ChatGPT session depends on the connector actually being connected. Finviz data tools run only on the hosted service. Never claim a remote tool was used unless it was successfully invoked.

## Design lock
Primary reference `references/amazon-example.png`; secondary `references/alphabet-example.png`; base layout `templates/layout.json`.

The visual contract is an original editorial recreation: wide light background, generous large-format navy headline, prominent central company wordmark, seven-or-fewer revenue rows with tasteful brand treatments, thick soft curved ribbons, blue/gold source flows, green surviving profit, coral costs, pronounced major nodes, right-hand red detailed expense endpoints, tiny clean source footer. Reject sparse technical charts with a narrow center column and excess whitespace.

## QA gates
- Financial: check every subtotal, full precision, parent-child, dates, and comparisons. Reject if it doesn't balance beyond disclosed rounding.
- Rendered text: reject any visible monetary amount with >2 decimals, missing label, truncation or currency mismatch.
- Geometry: parent widths = sum of outgoing widths for positive conservation stages; all sign-changing adjustments explicitly annotated.
- Layout: inspect PNG; reject collisions, out-of-canvas elements, overly small graphics, mechanical default Sankey styling, unapproved templates.
- Authenticity: no generic icon masquerading as a company-owned mark, or implied undisclosed product revenues.

If no independent QA agent is available, run the validations directly and be transparent that independent review was not performed.

## Finviz Elite and native-AI orchestration

1. For US-listed tickers, prefer the connected hosted MCP tools `finviz_connection_status`, `get_finviz_statements` (default quarterly income `IQ`), `get_finviz_filings`, and `get_finviz_earnings_calendar`. For global listings use issuer IR and exchange/regulator filings. Cross-check significant reported numbers against SEC or company primary sources. Never invent disclosures.
2. The Finviz key lives only in Render as environment variable `FINVIZ_API_TOKEN`, read server-side. Do not ask users to paste tokens in chat, save them in memory, put them in the skill, or echo credential-bearing URLs. Without a connected MCP server or configured variable, fall back to public financial filings and say so.
3. Statement selectors `IA/IQ/BA/BQ/CA/CQ`; optional `source=reuters`, `order=newest|oldest`, growth list with `yoy`, `yoy_pct`, `qoq`, `qoq_pct` (QoQ quarterly only). Exact CSV financial values are in full units, and currency may be in its download filename; never assume USD. The service uses fixed HTTPS Finviz endpoints and never returns the token.
4. Build a full-precision, source-attributed ledger first. Native AI controls editorial composition, typography and polished aesthetics, while deterministic ledger arithmetic controls the actual ribbon proportions. Upper sources curve downward and lower sources curve upward into revenue. Reject disconnected ribbons, bad colors, mismatched widths, collisions or incorrect numbers after inspecting the final image.
5. Finviz licensing restricts redistribution of its raw data; publish summary figures corroborated by issuer filings, not raw Finviz exports. Use the existing Readme for Render token setup and offline adapter tests. The newer Elite dashboard states 10 calls per five seconds; if HTTP 429 appears, retry conservatively.
