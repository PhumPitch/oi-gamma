"""Daily job: save a snapshot for every watchlist ticker, then drop old ones.

Run by GitHub Actions after the US close (see .github/workflows/snapshot.yml).
Needs DATABASE_URL (env var or .streamlit/secrets.toml); without it, writes to local SQLite.

Run from the project folder: python -m scripts.snapshot
"""
import sys

from src import cboe, exposure, history

KEEP_DAYS = 30


def snapshot(ticker: str) -> int:
    """Fetch one ticker and save today's snapshot. Returns rows saved."""
    quote, chain = cboe.fetch_chain(ticker)
    date = (quote.get("last_trade_time") or "")[:10]  # same date key as app.py
    if not date:
        raise ValueError("no last_trade_time in quote")
    df = exposure.add_exposures(chain, quote["current_price"])
    history.save_snapshot(ticker, date, df)
    return len(df)


def main() -> None:
    tickers = history.get_watchlist()
    print(f"DB: {history.database_url().split('@')[-1]}")  # host only, no password
    failed = []
    for t in tickers:
        try:
            print(f"{t:6} ok  {snapshot(t):>6} contracts")
        except Exception as e:  # one bad ticker must not stop the rest
            failed.append(t)
            print(f"{t:6} ERROR {type(e).__name__}: {e}")

    print(f"Pruned {history.prune(KEEP_DAYS)} rows older than {KEEP_DAYS} days")
    print(f"Done: {len(tickers) - len(failed)}/{len(tickers)} ok" + (f", failed: {failed}" if failed else ""))
    if failed and len(failed) == len(tickers):
        sys.exit(1)  # everything failed -> mark the Actions run red


if __name__ == "__main__":
    main()
