---
name: earnings-sankey
description: Use this workflow whenever the user wants a quarterly or annual income-statement earnings Sankey, especially in the polished Amazon/Alphabet editorial style.
---
# Earnings Graphic Studio

## Required flow
1. Research the latest **released** quarter from company IR, SEC/regulator, and Quartr when available. Do not invent undisclosed segments, release dates or line items. The renderer **does not fetch financial data**.
2. Create a reconciled JSON ledger using `references/ledger-format.md`. Include full-precision values and data provenance. Treat IFRS/GAAP differences faithfully; gross profit/operating profit may not be reported for financial services. If unsupported, explain rather than invent.
3. If the `earnings-renderer-local` MCP tools are actually connected and working, call `validate_earnings_ledger` before `render_earnings_sankey`. **Do not bypass the renderer** to create a generic Plotly or default Sankey. If unavailable, explain that the plugin's local MCP service is not connected in this host; use an explicitly supported alternate renderer, but never claim the plugin ran.
4. Use the `amazon_editorial_v1` layout, derived from the user's original Amazon and Alphabet visual benchmarks. Do not copy the publishers' watermarks or attribution.
5. Keep a single canvas with horizontal source ribbons → revenue → gross profit → operating profit → pretax → net. Branch cost of revenue and operating expenses from the correct stages. For signed negative income, use a clearly labeled loss adjustment, not a fake positive conservation flow.
6. Display financial amounts using **at most two decimals**, preserving full precision for ribbon geometry. Put a verified, short quarterly insight in the header rather than generic “How revenue became profit.” Include YoY where supported, and percentage-point margin movements where appropriate.
7. Inspect the **actual generated PNG/SVG** visually against the available Amazon reference. Financial checks passing does not imply design approval. QA must explicitly check label overlap, clipping, curved ribbon continuity, hierarchy, readable labels, wordmark placement, monetary formatting, and meaningful relative widths.
8. If QA fails, correct and rerender; do not assert final approval based merely on the MCP tool succeeding. Deliver a verified graphic link with primary-source citations, a short takeaway, and caveats.

## What this plugin is
The server bundled in this plugin is a **local stdio MCP renderer**. It is not hosted. Portable account installation alone does not start the server on ChatGPT web/mobile. Use it only in a client that executes local MCP servers or after a real hosted MCP endpoint has been deployed and connected. Do not substitute an invented remote endpoint.

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
