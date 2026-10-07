from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.falling_knife_trade_selection import (
    EASTERN,
    TradeSelectionError,
    is_regular_market_open,
    main,
    parse_top_decliners,
    report_session_candidates,
    select_trade_request,
    select_trade_request_from_report,
    write_trade_request,
    write_order_outcome,
)


def report(
    session: str,
    rows: str,
    *,
    price_basis: str = "completed",
    run_timestamp: str | None = None,
) -> str:
    timestamp_line = f"**Run timestamp:** {run_timestamp}\n" if run_timestamp else ""
    return f"""# Falling Knife Report

{timestamp_line}**Analysis session:** {session} {price_basis} regular session
**Price basis:** {price_basis}

## Top decliners

| Rank | Ticker | Final score | Research label |
| ---: | --- | ---: | --- |
{rows}

## Detail
"""


class TradeSelectionTests(unittest.TestCase):
    def test_parser_selects_highest_scores_and_breaks_ties_by_report_rank(self) -> None:
        source = report(
            "2026-08-03",
            "| 1 | LOW | 5.0 | Investigate |\n"
            "| 2 | FIRST | 7.2 | Watchlist |\n"
            "| 3 | SECOND | 7.2 | Watchlist |\n"
            "| 4 | THIRD | 6.1 | Watchlist |",
        )
        session, candidates = parse_top_decliners(source)
        self.assertEqual(session, date(2026, 8, 3))
        self.assertEqual(candidates[1].final_score, Decimal("7.2"))

        with TemporaryDirectory() as directory:
            reports_dir = Path(directory) / "reports"
            reports_dir.mkdir()
            (reports_dir / "2026-08-04-001928-ET.md").write_text(source, encoding="utf-8")
            request = select_trade_request(
                reports_dir, datetime(2026, 8, 4, 10, 0, tzinfo=EASTERN)
            )
        self.assertEqual([order.symbol for order in request.orders], ["FIRST", "SECOND"])
        self.assertEqual([order.dollar_amount for order in request.orders], ["5.00", "5.00"])
        self.assertEqual(request.total_dollar_amount, "10.00")

    def test_date_resolution_prefers_closed_session_then_falls_back_to_prior_report(self) -> None:
        self.assertEqual(
            report_session_candidates(datetime(2026, 8, 4, 10, 0, tzinfo=EASTERN)),
            (date(2026, 8, 3),),
        )
        self.assertEqual(
            report_session_candidates(datetime(2026, 8, 4, 16, 1, tzinfo=EASTERN)),
            (date(2026, 8, 4), date(2026, 8, 3)),
        )

    def test_market_open_only_inside_regular_session_and_respects_early_close(self) -> None:
        self.assertFalse(is_regular_market_open(datetime(2026, 8, 4, 9, 29, tzinfo=EASTERN)))
        self.assertTrue(is_regular_market_open(datetime(2026, 8, 4, 9, 30, tzinfo=EASTERN)))
        self.assertFalse(is_regular_market_open(datetime(2026, 8, 4, 16, 0, tzinfo=EASTERN)))
        self.assertTrue(is_regular_market_open(datetime(2026, 11, 27, 12, 59, tzinfo=EASTERN)))
        self.assertFalse(is_regular_market_open(datetime(2026, 11, 27, 13, 0, tzinfo=EASTERN)))
        self.assertFalse(is_regular_market_open(datetime(2026, 7, 3, 12, 0, tzinfo=EASTERN)))

    def test_rejects_invalid_or_incomplete_reports(self) -> None:
        with TemporaryDirectory() as directory:
            reports_dir = Path(directory) / "reports"
            reports_dir.mkdir()
            (reports_dir / "report.md").write_text(
                report("2026-08-03", "| 1 | ONLY | 7.0 | Watchlist |"),
                encoding="utf-8",
            )
            with self.assertRaises(TradeSelectionError):
                select_trade_request(reports_dir, datetime(2026, 8, 4, 10, 0, tzinfo=EASTERN))

        with self.assertRaises(TradeSelectionError):
            parse_top_decliners("## Top decliners\n")

    def test_request_write_is_idempotent_and_rejects_conflicting_same_day_output(self) -> None:
        source = report("2026-08-03", "| 1 | AAA | 7.0 | Watchlist |\n| 2 | BBB | 6.0 | Investigate |")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports_dir = root / "reports"
            reports_dir.mkdir()
            (reports_dir / "report.md").write_text(source, encoding="utf-8")
            request = select_trade_request(reports_dir, datetime(2026, 8, 4, 10, 0, tzinfo=EASTERN))
            output = write_trade_request(request, root / "trades")
            self.assertEqual(write_trade_request(request, root / "trades"), output)
            output.write_text("conflict", encoding="utf-8")
            with self.assertRaises(TradeSelectionError):
                write_trade_request(request, root / "trades")

    def test_cli_ignores_purchase_workflow_when_market_is_closed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                main(
                    [
                        "--reports-dir",
                        str(root / "reports"),
                        "--trades-dir",
                        str(root / "trades"),
                        "--now",
                        "2026-08-04T09:29:00-04:00",
                    ]
                ),
                0,
            )
            self.assertFalse((root / "trades").exists())

    def test_direct_in_market_handoff_uses_the_just_generated_intraday_report(self) -> None:
        source = report(
            "2026-08-04",
            "| 1 | FIRST | 7.0 | Watchlist |\n"
            "| 2 | SECOND | 8.5 | Strong Research Candidate |\n"
            "| 3 | THIRD | 8.5 | Strong Research Candidate |",
            price_basis="intraday",
            run_timestamp="2026-08-04T13:00:00-04:00",
        )
        with TemporaryDirectory() as directory:
            report_path = Path(directory) / "fresh-report.md"
            report_path.write_text(source, encoding="utf-8")
            request = select_trade_request_from_report(
                report_path, datetime(2026, 8, 4, 13, 5, tzinfo=EASTERN)
            )
        self.assertEqual([order.symbol for order in request.orders], ["SECOND", "THIRD"])

    def test_direct_in_market_handoff_accepts_a_fresh_completed_session_report(self) -> None:
        source = report(
            "2026-08-03",
            "| 1 | AAA | 6.0 | Investigate |\n| 2 | BBB | 7.0 | Watchlist |",
            price_basis="completed",
            run_timestamp="2026-08-04T13:00:00-04:00",
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "fresh-report.md"
            report_path.write_text(source, encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "--report-path",
                        str(report_path),
                        "--trades-dir",
                        str(root / "trades"),
                        "--now",
                        "2026-08-04T13:05:00-04:00",
                    ]
                ),
                0,
            )
            self.assertTrue(
                (root / "trades" / "2026-08-04-falling-knife-trade-request.json").exists()
            )

    def test_direct_handoff_rejects_out_of_hours_or_stale_or_unstructured_reports(self) -> None:
        source = report(
            "2026-08-04",
            "| 1 | AAA | 8.0 | Watchlist |\n| 2 | BBB | 7.0 | Watchlist |",
            price_basis="intraday",
            run_timestamp="2026-08-04T10:00:00-04:00",
        )
        with TemporaryDirectory() as directory:
            report_path = Path(directory) / "fresh-report.md"
            report_path.write_text(source, encoding="utf-8")
            with self.assertRaises(TradeSelectionError):
                select_trade_request_from_report(
                    report_path, datetime(2026, 8, 4, 16, 0, tzinfo=EASTERN)
                )

            stale = source.replace("2026-08-04T10:00:00-04:00", "2026-08-03T10:00:00-04:00")
            report_path.write_text(stale, encoding="utf-8")
            with self.assertRaises(TradeSelectionError):
                select_trade_request_from_report(
                    report_path, datetime(2026, 8, 4, 13, 0, tzinfo=EASTERN)
                )

            report_path.write_text(
                report("2026-08-04", "| 1 | AAA | 8.0 | Watchlist |\n| 2 | BBB | 7.0 | Watchlist |"),
                encoding="utf-8",
            )
            with self.assertRaises(TradeSelectionError):
                select_trade_request_from_report(
                    report_path, datetime(2026, 8, 4, 13, 0, tzinfo=EASTERN)
                )

    def test_order_outcome_is_immutable_and_must_match_the_requested_order(self) -> None:
        source = report("2026-08-03", "| 1 | AAA | 7.0 | Watchlist |\n| 2 | BBB | 6.0 | Investigate |")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports_dir = root / "reports"
            reports_dir.mkdir()
            (reports_dir / "report.md").write_text(source, encoding="utf-8")
            request = select_trade_request(reports_dir, datetime(2026, 8, 4, 10, 0, tzinfo=EASTERN))
            request_path = write_trade_request(request, root / "trades")
            outcome = write_order_outcome(request, request_path, "AAA", "order-1", "queued")
            self.assertEqual(write_order_outcome(request, request_path, "AAA", "order-1", "queued"), outcome)
            failed_outcome = write_order_outcome(request, request_path, "BBB", "", "failed")
            self.assertIn('"order_id": null', failed_outcome.read_text(encoding="utf-8"))
            with self.assertRaises(TradeSelectionError):
                write_order_outcome(request, request_path, "CCC", "order-2", "queued")
            with self.assertRaises(TradeSelectionError):
                write_order_outcome(request, request_path, "AAA", "order-1", "not-a-state")
            with self.assertRaises(TradeSelectionError):
                write_order_outcome(request, request_path, "BBB", "", "queued")


if __name__ == "__main__":
    unittest.main()
