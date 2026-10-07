---
name: falling-knife-report
description: Generates today's Falling Knife report for software equities and handles reviewed purchase execution.
triggers:
  - "Run today's Falling Knife report"
  - "run falling knife report"
---


## Playbook: Run Today's Falling Knife Report

**Trigger:** Run this workflow when the user says a normalized variation of `Run today's Falling Knife report`, including case variations and straight or curly apostrophes. Normalize whitespace, case, and apostrophes before matching.

**Purpose:** Produce a Markdown report on the largest daily decliners among U.S.-based companies in Robinhood's curated Software universe. Never treat a price decline as an investment opportunity by itself. When the report is successfully completed during regular market hours, immediately hand its exact output to the separate reviewed-purchase steps below.

**Research safety boundary:** During research and report generation, do not place, review, preview, cancel, replace, exercise, or otherwise manage any equity or option order. Do not access accounts, positions, tax lots, P&L, or portfolio data. The only exception is the post-report handoff to the dedicated reviewed-purchase workflow, which must follow every restriction in that playbook. Do not create, follow, modify, or remove a watchlist. For Robinhood research, use only these read-only tools:

- `get_popular_watchlists`
- `get_watchlist_items`
- `get_equity_fundamentals`
- `get_equity_quotes`
- `get_equity_historicals`

Use only `get_company_profile`, `list_filings`, `get_filing_section`, and `get_financial_statements` from SEC EDGAR. Use public web research only for the decline catalyst and cite direct sources.

### Output and session rules

- Use US Eastern Time for the run timestamp, session date, and filename. The report header must include these machine-readable lines exactly: `**Run timestamp:** <ISO-8601 timestamp with UTC offset>`, `**Analysis session:** <YYYY-MM-DD> <intraday|completed> regular session`, and `**Price basis:** <intraday|completed>`.
- Save every run as `reports/YYYY-MM-DD-HHmmss-ET.md`. If that name already exists, append `-2`, `-3`, and so on; never overwrite a prior report.
- Support intraday execution. During regular hours, compare the latest regular-market trade price with the adjusted previous regular close. Outside regular hours, or when the current session has no regular trade, use the two latest completed regular-session closes from split-adjusted daily history.
- For weekends, holidays, or before a usable current-session trade, analyze the most recent completed US trading day.
- Apply split-adjusted prices. Exclude and flag any symbol whose relevant split, spin-off, or distribution adjustment cannot be validated.

### 1. Build the candidate list

1. Call `get_popular_watchlists` and find the curated list whose `display_name` equals `Software` case-insensitively. This list is the complete software universe; do not replace it with another sector, industry, or custom ticker list.
2. If the Software list cannot be retrieved, create the timestamped report with a clear failure note and stop. Do not substitute a universe.
3. Call `get_watchlist_items`, retain instruments with usable equity symbols, and call `get_equity_fundamentals` in batches of at most 10 symbols using regular-session data.
4. Retain companies with current market capitalization of at least $2.0B, inclusive, **and** a U.S. headquarters. Use the Robinhood fundamentals `headquarters_state` field and retain only the 50 U.S. states or the District of Columbia. Exclude foreign issuers, ADRs, and companies with an unavailable or non-U.S. headquarters state from ranking; list their count in the screening-data-gaps section as `non-U.S headquarters` or `headquarters unavailable`.
5. Retrieve price data in the relevant MCP batch limits. Calculate:

   ```text
   daily decline % = ((latest regular-market price - previous regular-session close)
                      / previous regular-session close) * 100
   ```

6. Exclude from ranking any company without a valid market cap, current/latest-session price, or previous close. List each exclusion and its missing field in a screening-data-gaps section; do not assign it a neutral score.
7. Rank eligible companies by the most negative decline percentage. Select the top five, or every eligible company when fewer than five qualify.
8. If no candidate qualifies, still save a report containing the session details, universe count, filtering results, and data gaps, then stop.

### 2. Research each selected company

For every selected company, preserve the ticker, current market cap, prior close, latest regular-market price, decline percentage, and price-session basis.

**Reason for the decline**

- Research the window from the prior completed regular-market close through the run timestamp. This includes intervening weekends and holidays.
- Prioritize company press releases, relevant SEC 8-K filings, and established publicly accessible financial news outlets.
- Distinguish confirmed facts from interpretation. Cite every news source as a Markdown link with its source title.
- Classify the decline cause before assigning its score:
  - **Unconfirmed — `5.0`:** Assign exactly `5.0` when the available evidence does not establish a credible connection between a specific event and the stock decline. Do not score above or below neutral based only on timing, correlation, speculation, background risks, or incomplete information.
  - **Temporary or limited — `6.0–10.0`:** Assign a score above `5.0` only when credible evidence connects the decline to a temporary, market-wide, technical, or otherwise limited event whose expected long-term fundamental impact is modest.
  - **Fundamental — `0.0–4.0`:** Assign a score below `5.0` only when credible evidence connects the decline to adverse changes in revenue, growth, margins, cash flow, liquidity, competitive position, governance, or another material business fundamental.
- Before assigning any Decline Cause score other than `5.0`, the report must identify the specific catalyst, cite a credible source supporting the connection, explain the expected business impact, and justify why the impact is temporary/limited or fundamental.
- If those evidence requirements are not satisfied, classify the cause as `Unconfirmed` and assign exactly `5.0`.
- Before finalizing the report, verify that the narrative classification, evidence, and numerical Decline Cause score are consistent. Do not describe a cause as unconfirmed while assigning a non-neutral score.

**Financial strength and disclosed risks**

1. Call `get_company_profile`.
2. Call `list_filings` to find the latest relevant annual filing. Use a relevant 10-K/A instead of its original 10-K when it revises the required information; never double count both filings.
3. Call `get_filing_section` by annual-filing accession number with `section_name: "Item 1A"`.
4. Call `get_financial_statements` to evaluate liquidity versus short-term obligations, debt/leverage, cash-flow generation, and recent revenue/profitability direction with equal consideration.
5. Assess the severity of disclosed risks, including when relevant customer concentration, refinancing pressure, litigation/regulation, competition, dilution, and going-concern language.
6. Cite each SEC-based conclusion with filing type, reporting period, and accession number.

**TTM earnings quality**

1. Use `list_filings` to collect the relevant 10-Q/10-Q/A and 10-K/10-K/A filings across the current and prior fiscal year. Identify the latest four completed sequential fiscal quarters; do not use the four latest 10-Q filings because that omits Q4. Use a relevant amendment instead of the original filing.
2. Call `get_financial_statements` by accession number for every filing needed to form those four quarters, including the annual filing and matching nine-month 10-Q needed to derive Q4.
3. Extract standalone quarterly Revenue and Net Income from the income statements. Extract standalone OCF and capex from cash-flow statements: Q1 is the three-month amount, Q2 is six-month YTD minus Q1, Q3 is nine-month YTD minus six-month YTD, and Q4 is annual minus nine-month YTD. Never add year-to-date amounts as independent quarters.
4. Perform a derivation only when fiscal periods, units, accounting scope, and statement concepts match. Otherwise, treat only the affected metric as unavailable and state the exact missing or non-comparable input.
5. Calculate only when four comparable quarters exist:

   ```text
   TTM Net Income = sum of latest 4 comparable quarterly Net Income values
   TTM Operating Cash Flow = sum of latest 4 comparable quarterly OCF values
   TTM Revenue = sum of latest 4 comparable quarterly Revenue values
   TTM Capex = sum of latest 4 comparable quarterly capex values
   TTM Free Cash Flow = TTM Operating Cash Flow - absolute value of TTM Capex
   TTM Quality of Earnings Ratio = TTM Operating Cash Flow / TTM Net Income
   ```

6. Show a source table with fiscal end, filing type, accession number, Revenue, Net Income, OCF, capex, and reported-versus-derived status for each quarter.
7. When TTM Net Income is zero or negative, state that the ratio is not meaningful. When required TTM data is unavailable or non-comparable, assign the Earnings Quality subscore `5.0` and explain the data gap.
8. Analyze the four-quarter trend plus available working-capital changes (including accounts receivable and inventory) and material non-cash drivers.

**Valuation metrics**

1. For each selected company, apply the `Calculate Valuation Metrics` playbook using the TTM Revenue, OCF, capex, and free-cash-flow values already built in the four-quarter source table.
2. Retrieve the latest comparable balance sheet by accession number for cash, short-term investments, and debt classification; use the market capitalization already preserved during screening.
3. Calculate EV/Revenue and FCF Yield before assigning their respective subscores.
4. If either metric cannot be calculated, apply the relevant missing-data scoring rule and explain the exact unavailable or non-comparable input.

### 3. Score and label

Score Financial Strength, Earnings Quality, Decline Cause, Disclosed Risks, EV/Revenue, and FCF Yield independently from `0.0` to `10.0`, round each to one decimal place, and calculate:

```text
Final score =
  (Financial Strength * 20%)
+ (Earnings Quality * 20%)
+ (Decline Cause * 20%)
+ (Disclosed Risks * 20%)
+ (EV/Revenue * 10%)
+ (FCF Yield * 10%)
```

- Use common score bands: `0-2` severe, `3-4` weak, `5-6` mixed/neutral, `7-8` strong, `9-10` exceptional.
- Financial Strength: higher scores require strong liquidity, manageable leverage, positive cash generation, and stable/improving operations; strained liquidity, high leverage, persistent negative cash flow, or deterioration lower the score.
- Earnings Quality base bands from TTM OCF / TTM Net Income: `>=1.2` is `9-10`; `1.0-1.19` is `7-8`; `0.8-0.99` is `5-6`; `0.5-0.79` is `3-4`; `<0.5` is `0-2`. Deduct 2.0 points, floored at `0.0`, only for a persistently worsening four-quarter earnings-quality trend.
- Decline Cause: apply the evidence and scoring rules in the **Reason for the decline** section. Evidence-backed temporary or limited causes score `6.0–10.0`; evidence-backed fundamental causes score `0.0–4.0`; and unconfirmed causes score exactly `5.0`.
- Disclosed Risks: fewer and less severe current risks score higher; material concentration, liquidity/refinancing, legal/regulatory, competition, dilution, or going-concern risks score lower.
- A missing required data category receives `5.0` with an explicit limitation. There are no automatic disqualifiers or score caps.
- EV/Revenue valuation subscore bands are: `<=2.0x` = `10.0`; `>2.0x-4.0x` = `8.0`; `>4.0x-6.0x` = `6.0`; `>6.0x-10.0x` = `4.0`; and `>10.0x` = `2.0`.
- FCF Yield valuation subscore bands are: `>=10.0%` = `10.0`; `7.5%-<10.0%` = `8.0`; `5.0%-<7.5%` = `6.0`; `2.5%-<5.0%` = `4.0`; `>0%-<2.5%` = `2.0`; and `<=0%` = `0.0`.
- When FCF Yield cannot be calculated because required data is unavailable or non-comparable, assign `5.0` and explain the limitation. Missing data is not the same as negative FCF.
- The four original factors each carry `20%` of the final score; EV/Revenue and FCF Yield each carry `10%`.
- Round the final score to one decimal place and label it: `0.0-3.0 High Risk`, `3.1-6.0 Investigate`, `6.1-8.0 Watchlist`, or `8.1-10.0 Strong Research Candidate`.

### 4. Required report structure

1. **Header:** Eastern-time run timestamp, analysis session date, intraday/completed-session basis, software-universe count, eligible count, and analyzed count.
2. **Top Decliners:** A Markdown table with rank, ticker, market cap, prior close, latest regular-market price, daily decline percentage, final score, and research label.
3. **Detailed thesis for each selected company:** decline snapshot and cause; raw screening inputs; financial-strength review; Item 1A risk audit; four-quarter TTM table and calculations; valuation inputs and EV/Revenue/FCF Yield calculations; six subscores; weighted score calculation and label; concise opportunity thesis; and principal failure risk.
4. **Sources and limitations:** Direct Markdown links for public news, SEC filing type/period/accession numbers, unconfirmed-catalyst status, data gaps, methodology, and a research-only disclaimer.

### Deterministic calculation helpers

After validating source data and accounting comparability, use `scripts/falling_knife_calculations.py` for repeatable screening, period derivation, TTM, valuation, score-band, weighted-score, rounding, and label calculations. The module is offline and pure: it does not retrieve data, assess comparability, determine qualitative scores, select sources, write reports, or perform any trading action.

- Pass `Decimal` values and treat a `None` result as unavailable or non-computable data. Apply the playbook's explicit neutral-score rule where required; do not infer missing values.
- Validate fiscal periods, units, accounting scope, XBRL concepts, and debt classification before calling the helpers. For enterprise value, supply either both current/long-term debt or one standalone total-debt figure, never both.
- Use the helper's half-up one-decimal score and research label outputs in the report. The helpers implement the existing formulas, thresholds, weights, and fixed valuation score bands without changing this methodology.

## Playbook: Execute Reviewed Falling Knife Purchases

**Trigger:** Invoke this workflow automatically only after `Run Today's Falling Knife Report` has successfully saved its just-generated report and the current regular US equity-market session is still open. Do not invoke it independently, after hours, on a later trading day, or from an older report.

**Purpose:** Have Python choose exactly two candidates from the just-generated completed-session or intraday Falling Knife report, then use Robinhood MCP tools to preview and place two real `$5.00` dollar-based equity buy orders only after the user gives fresh, explicit approval in the current conversation.

**Hard boundaries:**

- Never place, queue, cancel, replace, sell, or otherwise manage an order outside this playbook.
- Before invoking Python, requesting account information, checking tradability, previewing an order, or asking for permission, confirm regular US equity-market hours: an open trading day from 9:30 AM ET until the regular or published early close. Outside those hours, ignore the whole purchase workflow: do not create a request or skip record, make no Robinhood call, ask no permission, and do not defer it to another session.
- Use the account which has `agentic_allowed=true`, active, and not deactivated.
- Do not treat an earlier message, a plan, a scheduler, or a prior-day confirmation as approval. After successful previews, obtain explicit approval that names both tickers and confirms `$5.00` each / `$10.00` total before calling `place_equity_order`.
- Treat a submitted order as submitted, not filled. Do not cancel or replace it. On any validation, market-status, broker-alert, buying-power, tradability, or tool failure, fail closed: place neither order and report the reason.

**Selection and order sequence:**

1. Run `python scripts/falling_knife_trade_selection.py --report-path GENERATED_REPORT_PATH`. It validates the fresh report's current ET run timestamp, its machine-readable `intraday` or `completed` price basis, and its Top decliners table; it does not search for any other report. It selects the two highest Final scores (report rank breaks ties) and writes an idempotent request under `trades/`. It produces only two `$5.00` requests and cannot exceed `$10.00` gross daily notional.
2. Read the generated JSON. Validate that it contains exactly two distinct uppercase equity symbols, each with `dollar_amount: "5.00"`, `total_dollar_amount: "10.00"`, and one UUID `ref_id` per order. Do not alter any field or substitute a symbol.
3. Call `get_accounts`, validate the user-supplied account's `agentic_allowed`, active, and non-deactivated status, then call `get_equity_tradability` for both symbols. Require each symbol to be active, tradeable, regular-hours tradable for that account type, and fractionally tradable.
4. Call `review_equity_order` for each request with the user-supplied account number, `side: "buy"`, `type: "market"`, `market_hours: "regular_hours"`, `time_in_force: "gfd"`, and the request's `$5.00` `dollar_amount`. Present each Robinhood market-data disclosure verbatim. Treat every non-empty order check as a blocker and place neither order.
5. If both previews have empty order checks and the market remains open, ask for one explicit confirmation covering both named `$5.00` orders. Do not call `place_equity_order` until the user confirms.
6. On confirmation, call `place_equity_order` for each unchanged request using its matching `ref_id`, the same order fields used in review, and the user-supplied account number. Immediately persist each returned order ID and state as `trades/YYYY-MM-DD-falling-knife-TICKER-order-outcome.json` by running `python scripts/falling_knife_trade_selection.py --request-path REQUEST_PATH --record-order-outcome "TICKER|ORDER_ID|STATE"`. Retry only a transient transport failure with the same `ref_id`; if the first order succeeds but the second fails, record both outcomes and report the partial submission without cancelling or replacing either order.

**Allowed Robinhood MCP tools for this playbook:** `get_accounts`, `get_equity_tradability`, `review_equity_order`, `place_equity_order`, and `get_equity_orders` only to report the resulting order state.
