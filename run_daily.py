"""Daily runner / historical backfill for the NSE-BSE EOD pipeline.

Usage:
  python run_daily.py                       # today
  python run_daily.py --date 2026-11-07    # one specific date
  python run_daily.py --from 2024-01-01 --to 2026-11-07   # backfill range

Schedule daily (cron, 7 PM IST after market close):
  0 19 * * 1-5 cd /path/to/nifty_pipeline && python run_daily.py >> logs/run.log 2>&1
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from nse_pipeline import download, process


def run_for(d: date) -> None:
    print(f"=== {d.isoformat()} ===")
    idx = download.fetch_nse_indices(d)
    cm = download.fetch_nse_cm(d)
    fo = download.fetch_nse_fo(d)
    bse = download.fetch_bse_cm(d)

    if not any([idx, cm, fo]):
        print("  no files published (holiday/weekend) - skipped")
        return
    if idx:
        process.process_indices(idx, d)
    if cm:
        process.process_stocks(cm, d)
    if fo:
        process.process_fo(fo, d)
    if bse:
        print(f"  [ok] BSE bhavcopy saved: {bse.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--from", dest="start", help="backfill start YYYY-MM-DD")
    ap.add_argument("--to", dest="end", help="backfill end YYYY-MM-DD")
    args = ap.parse_args()

    if args.start and args.end:
        d = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
        while d <= end:
            if d.weekday() < 5:  # Mon-Fri
                try:
                    run_for(d)
                except Exception as exc:  # keep backfill moving
                    print(f"  [error] {d}: {exc}")
            d += timedelta(days=1)
    else:
        d = (
            datetime.strptime(args.date, "%Y-%m-%d").date()
            if args.date
            else date.today()
        )
        run_for(d)


if __name__ == "__main__":
    main()
