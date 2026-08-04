# Falling Knife Investing - V1 Plan

## Goal

Create a Codex-driven, manually invoked workflow that responds to **"Run today's Falling Knife report."** It identifies the top five software-stock decliners for the applicable US trading session, performs SEC- and news-backed research, and saves a separate Markdown investment-research report for each run.

The workflow is research only. It must not place trades, make portfolio-allocation decisions, or present its output as personalized investment advice.

## Scope and trigger

- Use the connected Robinhood and SEC EDGAR MCP tools, plus publicly accessible web sources for news research.
- Treat Robinhood's curated **Software** watchlist as the software universe; do not build a separate industry classifier or exclude otherwise eligible listed equities.
- Start only when the user says: **"Run today's Falling Knife report."**
- Support intraday use. When there is no current regular-market session, use the most recent completed US trading day.
- Use US Eastern Time for the as-of date, session status, report timestamp, and filenames.
- Save every run separately as `reports/YYYY-MM-DD-HHmm-ET.md`; do not overwrite an earlier same-day report.

## Screening workflow

1. Call `get_popular_watchlists`, locate the curated list named `Software`, then call `get_watchlist_items` with its list ID.
2. Retain equity instruments with usable ticker symbols. Retrieve Robinhood fundamentals in batches of at most 10 symbols, using `bounds: "regular"`, and retain companies with current market capitalization of at least $2.0B (inclusive).
3. Retrieve regular-session price data in batches. Use split-adjusted prices and calculate:

   ```text
   daily decline % = ((latest regular-market price - previous regular-session close)
                      / previous regular-session close) * 100
   ```

   - During a live regular session, use the latest available regular-market trade price and the adjusted prior regular close.
   - For a completed or non-trading session, use the two most recent completed regular-session closes from split-adjusted daily history.
   - Exclude a symbol from ranking only when a required price or market-cap input is unavailable; list it under screening data gaps.
4. Rank eligible companies by the most negative daily decline percentage and select the top five. If fewer than five qualify, analyze every qualifier and state the shortfall.
5. Preserve the raw screening values for every ranked company: ticker, market cap, prior close, latest regular price, decline percentage, and price-date/session basis.

## Per-company research workflow

Run the following research for each selected company. Keep confirmed facts separate from interpretation.

### Decline cause

- Search only the prior two calendar days, using public sources.
- Prioritize company press releases, SEC 8-K filings, and established financial-news coverage.
- Identify whether the evidence supports a temporary/market-wide catalyst or a company-specific deterioration such as an earnings miss, guidance cut, accounting concern, or material event.
- Cite every source as a direct link. If no credible explanation is found, label the cause **Unconfirmed** and assign a neutral `5.0/10` decline-cause subscore.

### Financial strength and disclosed risks

- Call `get_company_profile` and use `list_filings` to identify the latest relevant annual filing.
- Call `get_filing_section` with that annual filing's accession number and `section_name: "Item 1A"`.
- Call `get_financial_statements` for the latest financial position and cash-flow data.
- Evaluate liquidity versus short-term obligations, debt/leverage, cash-flow generation, and recent revenue/profitability trend with equal consideration for the financial-strength subscore.
- Evaluate the severity of current risks disclosed in Item 1A, including where applicable customer concentration, refinancing pressure, litigation/regulation, competition, dilution, and going-concern language.
- Cite filing type, period, and accession number for every SEC-based conclusion.

### TTM earnings quality

1. Call `list_filings` to identify the filings required to form the latest four reported fiscal quarters.
2. Call `get_financial_statements` by accession number for those 10-Q and 10-K filings.
3. Extract quarterly Net Income and Operating Cash Flow (OCF) using only comparable reporting periods. Do not add year-to-date figures as though they were standalone quarters.
4. When Q4 is not separately reported, derive it only as annual full-year value minus the matching first three fiscal quarters. If comparable periods are incomplete or unavailable, do not manufacture a TTM value; mark the data gap and assign a neutral `5.0/10` earnings-quality subscore.
5. Calculate:

   ```text
   TTM Net Income = sum of the latest 4 comparable quarters of Net Income
   TTM Operating Cash Flow = sum of the latest 4 comparable quarters of OCF
   TTM Quality of Earnings Ratio = TTM Operating Cash Flow / TTM Net Income
   ```

6. When Net Income is zero or negative, state that the ratio is not meaningful, explain the underlying results, and assign the neutral data-gap score unless independent comparable evidence supports a different documented assessment.
7. Analyze the four-quarter direction and available accounts-receivable, inventory, working-capital, and material non-cash drivers.

## Scoring and labels

Score each category from `0.0` to `10.0`, rounded to one decimal place. Assign equal 25% weights and calculate:

```text
Final score = (Financial Strength + Earnings Quality + Decline Cause + Disclosed Risks) / 4
```

Use this common interpretation for all subscores: `0-2` severe, `3-4` weak, `5-6` mixed/neutral, `7-8` strong, `9-10` exceptional.

| Category | Basis |
| --- | --- |
| Financial Strength | Liquidity, debt/leverage, cash-flow generation, and recent revenue/profitability direction. Strong liquidity, manageable leverage, positive cash generation, and stable/improving operations score higher. |
| TTM Earnings Quality | Use the OCF/Net Income ratio: `>=1.2` maps to `9-10`; `1.0-1.19` to `7-8`; `0.8-0.99` to `5-6`; `0.5-0.79` to `3-4`; and `<0.5` to `0-2`. Deduct 2 points, to a floor of 0, for a persistently worsening four-quarter trend. |
| Decline Cause | Temporary or market-wide, evidence-backed causes score higher. Fundamental deterioration, guidance cuts, accounting concerns, or material adverse events score lower. Unconfirmed cause scores `5.0`. |
| Disclosed Risks | Fewer and less severe current risks score higher. Material concentration, liquidity/refinancing, legal/regulatory, competitive, dilution, or going-concern risk lowers the score. |

Assign these non-actionable labels from the final score:

- `0.0-3.0`: High Risk
- `3.1-6.0`: Investigate
- `6.1-8.0`: Watchlist
- `8.1-10.0`: Strong Research Candidate

There are no automatic disqualifiers or score caps. Every missing-data category receives `5.0` and must state why.

## Report format

Each report must contain:

1. **Header** - Eastern-time run timestamp; analysis session date; intraday or completed-session basis; universe size; number eligible; and number analyzed.
2. **Top Decliners table** - Rank, ticker, market cap, prior close, latest regular-market price, daily decline percentage, final score, and research label.
3. **Detailed thesis for each selected company** - Include:
   - Decline snapshot and verified/unconfirmed cause.
   - Raw screening inputs.
   - Financial-strength review.
   - Latest annual Item 1A risk audit.
   - Four-quarter TTM earnings-quality table and calculations.
   - Four category subscores, equal-weight calculation, final score, and label.
   - Concise thesis with both the central opportunity and the principal reason it could fail.
   - SEC accession numbers/periods and direct links for all external news sources.
   - Data gaps and uncertainty notes.
4. **Methodology and limitations** - Explain price-session basis, source window, neutral missing-data scores, and the research-only disclaimer.

## Implementation order

1. Add a `Run today's Falling Knife report` playbook to `AGENTS.md` that follows this plan and explicitly prohibits trading tools.
2. Add the `reports/` output convention (created on first report generation) and ensure every generated report follows the required filename and structure.
3. Validate the screen with deterministic calculation fixtures for split-adjusted price changes, the $2B inclusive cutoff, fewer-than-five results, missing data, and ranking order.
4. Validate score calculation, category weights, ratio bands, two-point deterioration deduction, one-decimal rounding, label boundaries, and neutral-score behavior.
5. Run a manual end-to-end research report and confirm all five selected candidates have source-backed evidence or explicit data-gap disclosures.

## Acceptance criteria

- The exact trigger produces a separate timestamped Markdown report without using order-placement or account-modification tools.
- The screen uses the Robinhood Software list, regular-session split-adjusted prices, and the inclusive $2B market-cap rule.
- The report ranks at most five companies, preserves their raw screening data, and handles fewer qualifying names and non-trading days correctly.
- Every thesis includes the four required subscores, a one-decimal equal-weight final score, the correct label, and an opportunity/failure thesis.
- SEC claims cite the filing period and accession number; news claims cite direct public links; missing data and unconfirmed catalysts are explicit.
