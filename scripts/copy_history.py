"""One-off: copy local data/history.db into the cloud DB and seed the watchlist.

Needs DATABASE_URL (env var or .streamlit/secrets.toml). Safe to run twice:
each (ticker, date) is replaced, not duplicated.

Run from the project folder: python -m scripts.copy_history
"""
import sqlite3

import pandas as pd

from src import history

FIRST = ["SPX", "SPY"]  # indices first in the watchlist, then A-Z


def main() -> None:
    if history.database_url().startswith("sqlite"):
        raise SystemExit("DATABASE_URL is not set -> nothing to copy to.")
    with sqlite3.connect(history.DB_PATH) as src:
        local = pd.read_sql("SELECT * FROM snapshots", src)

    for (ticker, date), rows in local.groupby(["ticker", "date"]):
        history.write_rows(ticker, date, rows)
        print(f"{ticker:6} {date}  {len(rows):>6} rows")

    found = set(local["ticker"])
    for t in [t for t in FIRST if t in found] + sorted(found - set(FIRST)):
        history.add_ticker(t)
    print(f"Done: {len(local)} rows, watchlist = {history.get_watchlist()}")


if __name__ == "__main__":
    main()
