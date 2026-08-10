"""Deterministic, offline selection for reviewed Falling Knife purchases.

This module reads a completed Falling Knife Markdown report and produces a
two-order request.  It deliberately has no Robinhood credentials, MCP calls, or
order-placement code.  A separate agent must review the request with the user
and use the Robinhood MCP only after current-conversation confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError



class _USEasternFallback(tzinfo):
    """US Eastern time for Windows Python installations without IANA tzdata."""

    @staticmethod
    def _dst_bounds(year: int) -> Tuple[datetime, datetime]:
        march_eighth = date(year, 3, 8)
        start_day = march_eighth + timedelta(days=(6 - march_eighth.weekday()) % 7)
        november_first = date(year, 11, 1)
        end_day = november_first + timedelta(days=(6 - november_first.weekday()) % 7)
        return (
            datetime.combine(start_day, time(2, 0)),
            datetime.combine(end_day, time(2, 0)),
        )

    def dst(self, value: Optional[datetime]) -> timedelta:
        if value is None:
            return timedelta(0)
        naive = value.replace(tzinfo=None)
        start, end = self._dst_bounds(naive.year)
        return timedelta(hours=1) if start <= naive < end else timedelta(0)

    def utcoffset(self, value: Optional[datetime]) -> timedelta:
        return timedelta(hours=-5) + self.dst(value)

    def tzname(self, value: Optional[datetime]) -> str:
        return "EDT" if self.dst(value) else "EST"

    def fromutc(self, value: datetime) -> datetime:
        standard_local = (value + timedelta(hours=-5)).replace(tzinfo=self)
        return standard_local + self.dst(standard_local)


try:
    EASTERN = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:
    EASTERN = _USEasternFallback()
ORDER_NOTIONAL = Decimal("5.00")
DAILY_NOTIONAL_CAP = Decimal("10.00")
_ORDER_STATES = frozenset(
    {
        "new",
        "queued",
        "confirmed",
        "unconfirmed",
        "partially_filled",
        "filled",
        "cancelled",
        "rejected",
        "failed",
        "voided",
        "pending_cancelled",
        "partially_filled_rest_cancelled",
    }
)
_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
_ANALYSIS_SESSION_PATTERN = re.compile(
    r"^\*\*Analysis session:\*\*\s*(\d{4}-\d{2}-\d{2})\s*(.*)$",
    re.IGNORECASE,
)
_PRICE_BASIS_PATTERN = re.compile(
    r"^\*\*Price basis:\*\*\s*(intraday|completed)\s*$", re.IGNORECASE
)
_RUN_TIMESTAMP_PATTERN = re.compile(r"^\*\*Run timestamp:\*\*\s*(\S+)\s*$", re.IGNORECASE)


class TradeSelectionError(ValueError):
    """Raised when a report cannot safely produce the fixed trade request."""


@dataclass(frozen=True)
class TradeCandidate:
    rank: int
    ticker: str
    final_score: Decimal


@dataclass(frozen=True)
class ReportMetadata:
    analysis_session: date
    price_basis: Optional[str]
    run_timestamp: Optional[datetime]


@dataclass(frozen=True)
class TradeOrder:
    symbol: str
    dollar_amount: str
    ref_id: str


@dataclass(frozen=True)
class TradeRequest:
    execution_date: str
    report_session_date: str
    report_path: str
    report_sha256: str
    total_dollar_amount: str
    orders: Tuple[TradeOrder, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def easter_date(year: int) -> date:
    """Return Gregorian Easter using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(holiday: date) -> date:
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    result = date(year, month, 1)
    while result.weekday() != weekday:
        result += timedelta(days=1)
    return result + timedelta(days=7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        result = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        result = date(year, month + 1, 1) - timedelta(days=1)
    while result.weekday() != weekday:
        result -= timedelta(days=1)
    return result


def nyse_holidays(year: int) -> frozenset[date]:
    """Return the recurring full NYSE holiday calendar used by this workflow.

    One-off exchange closures are intentionally not guessed.  Add them here with
    a test before relying on the executor for an affected date.
    """
    holidays = set()
    for new_year in (date(year - 1, 1, 1), date(year, 1, 1), date(year + 1, 1, 1)):
        observed = _observed(new_year)
        if observed.year == year:
            holidays.add(observed)
    holidays.update(
        {
            _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
            _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
            easter_date(year) - timedelta(days=2),  # Good Friday
            _last_weekday(year, 5, 0),  # Memorial Day
            _observed(date(year, 6, 19)),  # Juneteenth
            _observed(date(year, 7, 4)),  # Independence Day
            _nth_weekday(year, 9, 0, 1),  # Labor Day
            _nth_weekday(year, 11, 3, 4),  # Thanksgiving
            _observed(date(year, 12, 25)),  # Christmas
        }
    )
    return frozenset(holidays)


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in nyse_holidays(day.year)


def previous_trading_day(day: date) -> date:
    candidate = day - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def _early_close_days(year: int) -> frozenset[date]:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    early = {thanksgiving + timedelta(days=1)}
    christmas_eve = date(year, 12, 24)
    if is_trading_day(christmas_eve):
        early.add(christmas_eve)

    independence_observed = _observed(date(year, 7, 4))
    candidate = independence_observed - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    early.add(candidate)
    return frozenset(early)


def session_bounds(day: date) -> Optional[Tuple[datetime, datetime]]:
    """Return regular-session ET bounds, including recurring 1 PM early closes."""
    if not is_trading_day(day):
        return None
    close = time(13, 0) if day in _early_close_days(day.year) else time(16, 0)
    return (
        datetime.combine(day, time(9, 30), tzinfo=EASTERN),
        datetime.combine(day, close, tzinfo=EASTERN),
    )


def is_regular_market_open(now: datetime) -> bool:
    """Return true only for the regular US equity session, never at its close."""
    eastern_now = now.astimezone(EASTERN)
    bounds = session_bounds(eastern_now.date())
    return bounds is not None and bounds[0] <= eastern_now < bounds[1]


def report_session_candidates(now: datetime) -> Tuple[date, ...]:
    """Resolve the completed session(s) valid for a run at ``now`` in ET.

    After today's close the workflow prefers today's completed-session report, but
    callers may use the prior completed session when today's report is not yet
    available.  Before/within the session and on non-trading days, only the prior
    completed session is valid.
    """
    eastern_now = now.astimezone(EASTERN)
    bounds = session_bounds(eastern_now.date())
    if bounds is not None and eastern_now >= bounds[1]:
        return (eastern_now.date(), previous_trading_day(eastern_now.date()))
    return (previous_trading_day(eastern_now.date()),)


def parse_report_metadata(report_text: str) -> ReportMetadata:
    """Read report metadata; direct handoff requires both basis and timestamp."""
    analysis_session: Optional[date] = None
    price_basis: Optional[str] = None
    run_timestamp: Optional[datetime] = None
    for line in report_text.splitlines():
        stripped = line.strip()
        analysis_match = _ANALYSIS_SESSION_PATTERN.match(stripped)
        if analysis_match:
            analysis_session = date.fromisoformat(analysis_match.group(1))
            if "completed" in analysis_match.group(2).lower() and price_basis is None:
                price_basis = "completed"
            continue
        basis_match = _PRICE_BASIS_PATTERN.match(stripped)
        if basis_match:
            price_basis = basis_match.group(1).lower()
            continue
        timestamp_match = _RUN_TIMESTAMP_PATTERN.match(stripped)
        if timestamp_match:
            try:
                run_timestamp = datetime.fromisoformat(timestamp_match.group(1))
            except ValueError as error:
                raise TradeSelectionError("report Run timestamp is not ISO 8601") from error
            if run_timestamp.tzinfo is None:
                raise TradeSelectionError("report Run timestamp has no timezone")
    if analysis_session is None:
        raise TradeSelectionError("report has no Analysis session header")
    return ReportMetadata(analysis_session, price_basis, run_timestamp)


def _parse_analysis_session(lines: Iterable[str]) -> date:
    for line in lines:
        match = _ANALYSIS_SESSION_PATTERN.match(line.strip())
        if match:
            return date.fromisoformat(match.group(1))
    raise TradeSelectionError("report has no Analysis session header")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_top_decliners(report_text: str) -> Tuple[date, Tuple[TradeCandidate, ...]]:
    """Extract a report session and validated scored candidates from Markdown."""
    lines = report_text.splitlines()
    analysis_session = _parse_analysis_session(lines)
    heading_index = next(
        (index for index, line in enumerate(lines) if line.strip().lower() == "## top decliners"),
        None,
    )
    if heading_index is None:
        raise TradeSelectionError("report has no Top decliners section")

    header_index = next(
        (
            index
            for index in range(heading_index + 1, len(lines))
            if lines[index].lstrip().startswith("|")
            and "ticker" in {cell.lower() for cell in _cells(lines[index])}
        ),
        None,
    )
    if header_index is None:
        raise TradeSelectionError("Top decliners table header is missing")

    header = [cell.lower() for cell in _cells(lines[header_index])]
    required_columns = ("rank", "ticker", "final score")
    if any(column not in header for column in required_columns):
        raise TradeSelectionError("Top decliners table lacks rank, ticker, or Final score")
    indexes = {column: header.index(column) for column in required_columns}

    candidates = []
    for line in lines[header_index + 2 :]:
        if not line.lstrip().startswith("|"):
            break
        row = _cells(line)
        if len(row) != len(header):
            raise TradeSelectionError("Top decliners row does not match its header")
        try:
            rank = int(row[indexes["rank"]])
            score = Decimal(row[indexes["final score"]])
        except (InvalidOperation, ValueError) as error:
            raise TradeSelectionError("Top decliners rank or Final score is invalid") from error
        ticker = row[indexes["ticker"]].upper()
        if rank <= 0 or score < 0 or score > 10 or not _TICKER_PATTERN.fullmatch(ticker):
            raise TradeSelectionError("Top decliners contains an invalid rank, ticker, or score")
        candidates.append(TradeCandidate(rank=rank, ticker=ticker, final_score=score))

    if not candidates:
        raise TradeSelectionError("Top decliners table has no candidates")
    if len({candidate.rank for candidate in candidates}) != len(candidates):
        raise TradeSelectionError("Top decliners table has duplicate ranks")
    if len({candidate.ticker for candidate in candidates}) != len(candidates):
        raise TradeSelectionError("Top decliners table has duplicate tickers")
    return analysis_session, tuple(candidates)


def _matching_reports(reports_dir: Path, session: date) -> list[Path]:
    matches = []
    for path in reports_dir.glob("*.md"):
        try:
            report_session, _ = parse_top_decliners(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TradeSelectionError):
            continue
        if report_session == session:
            matches.append(path)
    return sorted(matches, key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)


def _build_trade_request(selected_path: Path, report_bytes: bytes, now: datetime) -> TradeRequest:
    """Build the fixed two-order request from one already-validated report path."""
    eastern_now = now.astimezone(EASTERN)
    try:
        report_text = report_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TradeSelectionError("report is not UTF-8") from error
    report_session, candidates = parse_top_decliners(report_text)
    selected = sorted(candidates, key=lambda candidate: (-candidate.final_score, candidate.rank))[:2]
    if len(selected) != 2:
        raise TradeSelectionError("report has fewer than two scored candidates")
    report_hash = hashlib.sha256(report_bytes).hexdigest()
    orders = tuple(
        TradeOrder(
            symbol=candidate.ticker,
            dollar_amount=f"{ORDER_NOTIONAL:.2f}",
            ref_id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"falling-knife:{eastern_now.date().isoformat()}:{candidate.ticker}:{report_hash}",
                )
            ),
        )
        for candidate in selected
    )
    if sum((Decimal(order.dollar_amount) for order in orders), Decimal("0")) > DAILY_NOTIONAL_CAP:
        raise TradeSelectionError("trade request exceeds the daily notional cap")
    return TradeRequest(
        execution_date=eastern_now.date().isoformat(),
        report_session_date=report_session.isoformat(),
        report_path=str(selected_path),
        report_sha256=report_hash,
        total_dollar_amount=f"{sum((Decimal(order.dollar_amount) for order in orders), Decimal('0')):.2f}",
        orders=orders,
    )


def select_trade_request(reports_dir: Path, now: datetime) -> TradeRequest:
    """Select exactly two $5 orders from the applicable completed-session report."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    eastern_now = now.astimezone(EASTERN)
    selected_path: Optional[Path] = None
    expected_session: Optional[date] = None
    for candidate_session in report_session_candidates(eastern_now):
        matches = _matching_reports(reports_dir, candidate_session)
        if matches:
            selected_path = matches[0]
            expected_session = candidate_session
            break
    if selected_path is None or expected_session is None:
        raise TradeSelectionError("no completed report exists for an applicable session")
    report_bytes = selected_path.read_bytes()
    try:
        metadata = parse_report_metadata(report_bytes.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise TradeSelectionError("report is not UTF-8") from error
    if metadata.analysis_session != expected_session or metadata.price_basis != "completed":
        raise TradeSelectionError("selected report is not the expected completed session")
    return _build_trade_request(selected_path, report_bytes, eastern_now)


def select_trade_request_from_report(report_path: Path, now: datetime) -> TradeRequest:
    """Select from the report just produced by an in-market report run.

    The direct path is intentionally strict: it accepts only explicit, ISO-dated
    metadata from today's report and supports both `intraday` and `completed`
    price bases.  It never falls back to another report.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    eastern_now = now.astimezone(EASTERN)
    if not is_regular_market_open(eastern_now):
        raise TradeSelectionError("regular US equity market is closed")
    report_bytes = report_path.read_bytes()
    try:
        metadata = parse_report_metadata(report_bytes.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise TradeSelectionError("report is not UTF-8") from error
    if metadata.price_basis not in {"intraday", "completed"} or metadata.run_timestamp is None:
        raise TradeSelectionError("direct report handoff requires Price basis and Run timestamp metadata")
    if metadata.run_timestamp.astimezone(EASTERN).date() != eastern_now.date():
        raise TradeSelectionError("direct report handoff requires a report generated today")
    if metadata.price_basis == "intraday" and metadata.analysis_session != eastern_now.date():
        raise TradeSelectionError("intraday report session does not match today")
    return _build_trade_request(report_path, report_bytes, eastern_now)


def write_trade_request(request: TradeRequest, trades_dir: Path) -> Path:
    """Persist an idempotent request; conflicting same-day output fails closed."""
    trades_dir.mkdir(parents=True, exist_ok=True)
    path = trades_dir / f"{request.execution_date}-falling-knife-trade-request.json"
    contents = request.to_json()
    if path.exists():
        if path.read_text(encoding="utf-8") != contents:
            raise TradeSelectionError("a conflicting trade request already exists for today")
        return path
    path.write_text(contents, encoding="utf-8")
    return path


def read_trade_request(path: Path) -> TradeRequest:
    """Load and validate an existing two-order request before recording an outcome."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        orders = tuple(
            TradeOrder(
                symbol=str(order["symbol"]),
                dollar_amount=str(order["dollar_amount"]),
                ref_id=str(order["ref_id"]),
            )
            for order in data["orders"]
        )
        request = TradeRequest(
            execution_date=str(data["execution_date"]),
            report_session_date=str(data["report_session_date"]),
            report_path=str(data["report_path"]),
            report_sha256=str(data["report_sha256"]),
            total_dollar_amount=str(data["total_dollar_amount"]),
            orders=orders,
        )
    except (KeyError, TypeError, json.JSONDecodeError, OSError) as error:
        raise TradeSelectionError("trade request is invalid") from error
    if (
        len(request.orders) != 2
        or request.total_dollar_amount != "10.00"
        or any(
            order.dollar_amount != "5.00"
            or not _TICKER_PATTERN.fullmatch(order.symbol)
            for order in request.orders
        )
    ):
        raise TradeSelectionError("trade request does not contain two fixed $5.00 orders")
    return request


def write_order_outcome(
    request: TradeRequest, request_path: Path, symbol: str, order_id: str, state: str
) -> Path:
    """Write one immutable, idempotent broker outcome for a requested symbol."""
    normalized_symbol = symbol.strip().upper()
    normalized_state = state.strip().lower()
    normalized_order_id = order_id.strip()
    matching_order = next(
        (order for order in request.orders if order.symbol == normalized_symbol), None
    )
    if matching_order is None or normalized_state not in _ORDER_STATES:
        raise TradeSelectionError("order outcome does not match the trade request")
    if not normalized_order_id and normalized_state not in {"failed", "rejected"}:
        raise TradeSelectionError("a broker order ID is required unless submission failed or was rejected")
    path = request_path.parent / (
        f"{request.execution_date}-falling-knife-{normalized_symbol}-order-outcome.json"
    )
    contents = json.dumps(
        {
            "dollar_amount": matching_order.dollar_amount,
            "execution_date": request.execution_date,
            "order_id": normalized_order_id or None,
            "ref_id": matching_order.ref_id,
            "report_sha256": request.report_sha256,
            "state": normalized_state,
            "symbol": normalized_symbol,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != contents:
        raise TradeSelectionError("a conflicting order outcome already exists")
    if not path.exists():
        path.write_text(contents, encoding="utf-8")
    return path


def _parse_outcome(value: str) -> Tuple[str, str, str]:
    parts = value.split("|", 2)
    if len(parts) != 3:
        raise TradeSelectionError("--record-order-outcome must be SYMBOL|ORDER_ID|STATE")
    return parts[0], parts[1], parts[2]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a reviewed Falling Knife trade request.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--trades-dir", type=Path, default=Path("trades"))
    parser.add_argument(
        "--report-path",
        type=Path,
        help="The report just generated by an in-market Falling Knife run.",
    )
    parser.add_argument(
        "--now",
        help="Timezone-aware ISO timestamp for deterministic operation/testing; defaults to now in ET.",
    )
    parser.add_argument(
        "--request-path",
        type=Path,
        help="Existing request to use with --record-order-outcome.",
    )
    parser.add_argument(
        "--record-order-outcome",
        metavar="SYMBOL|ORDER_ID|STATE",
        help="Write one immutable Robinhood result after the agent submits an order.",
    )
    args = parser.parse_args(argv)
    if bool(args.request_path) != bool(args.record_order_outcome):
        parser.error("--request-path and --record-order-outcome must be used together")
    if args.request_path:
        try:
            request = read_trade_request(args.request_path)
            symbol, order_id, state = _parse_outcome(args.record_order_outcome)
            print(write_order_outcome(request, args.request_path, symbol, order_id, state))
        except (OSError, TradeSelectionError, ValueError) as error:
            print(f"Order outcome not recorded: {error}", file=sys.stderr)
            return 1
        return 0
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(EASTERN)
    if now.tzinfo is None:
        parser.error("--now must include a UTC offset or timezone")
    try:
        if not is_regular_market_open(now):
            print("Purchase workflow ignored because the regular market is closed.")
            return 0
        request = (
            select_trade_request_from_report(args.report_path, now)
            if args.report_path
            else select_trade_request(args.reports_dir, now)
        )
        path = write_trade_request(request, args.trades_dir)
    except (OSError, TradeSelectionError, ValueError) as error:
        print(f"Trade request not created: {error}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
