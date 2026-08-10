# Falling Knife Investing

This project defines a research workflow for finding the largest daily decliners in Robinhood’s curated **Software** universe and producing a research-only Markdown report for the top candidates.

The workflow:

1. Screens the curated Software watchlist.
2. Filters for U.S.-headquartered companies with market capitalization of at least $2 billion.
3. Ranks the largest regular-session decliners.
4. Researches decline catalysts, financial strength, disclosed risks, earnings quality, and valuation.
5. Saves a timestamped report in [`reports/`](reports/).

The output is informational research, not personalized investment advice. The workflow does not place trades, manage orders, access portfolio data, or modify watchlists.

For V3, a report that finishes during regular market hours immediately hands its own top two scores to the reviewed execution playbook. That playbook can submit two `$5.00` Robinhood equity orders only after the user confirms that day's two order previews. A report that finishes outside regular market hours does not start, queue, or defer the purchase workflow.

## What `AGENTS.md` does

[`AGENTS.md`](AGENTS.md) is the project’s operating playbook. It tells the agent:

- Which data sources and read-only tools may be used.
- How to build the Software candidate universe.
- How to handle trading sessions, split-adjusted prices, and missing data.
- Which SEC filings and financial statements to review.
- How to calculate earnings quality and valuation metrics.
- How to classify decline causes and assign scores.
- What structure and limitations each report must include.

It also defines the research boundaries and the narrowly scoped, confirmation-gated reviewed-purchase handoff.

## MCPs and data sources

### Robinhood

Used for read-only market and universe data:

- Curated watchlists and watchlist items.
- Market capitalization and basic equity fundamentals.
- Current regular-session prices and prior settled closes.
- Historical split-adjusted price data when needed.

### SEC EDGAR

The SEC filing MCP used by this project is the author-developed [`MakAcp/sec-insight-mcp`](https://github.com/MakAcp/sec-insight-mcp) server.

Used for company filings and reported financial information:

- Company profiles.
- Filing lists and accession numbers.
- Filing sections such as business and risk disclosures.
- Structured balance sheets, income statements, and cash-flow statements.

### Public web research

Used only to investigate decline catalysts and current company news. Sources are cited directly in each report. The agent distinguishes confirmed evidence from interpretation and labels unsupported causes as unconfirmed.

## Reports

Reports are saved as timestamped Markdown files under [`reports/`](reports/), using Eastern Time in the filename. Each report includes screening results, detailed company theses, scores, sources, and data limitations.

## Project files

- [`scripts/falling_knife_trade_selection.py`](scripts/falling_knife_trade_selection.py) â€” offline selector for the reviewed V3 purchase request; it never calls Robinhood or holds credentials.

- [`AGENTS.md`](AGENTS.md) — detailed workflow and safety instructions.
- [`Plan.md`](Plan.md) — project planning and implementation notes.
- [`reports/`](reports/) — generated research reports.
