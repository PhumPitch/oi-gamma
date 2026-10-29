"""Daily snapshots in SQLite, used for the % change badges."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"
COLS = ["expiry", "strike", "gex", "vex", "open_interest"]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS snapshots ("
        "ticker TEXT, date TEXT, expiry TEXT, strike REAL, gex REAL, vex REAL, open_interest REAL)"
    )
    return con


def save_snapshot(ticker: str, date: str, df: pd.DataFrame) -> None:
    """Replace today's snapshot, so we always keep the last one of each day."""
    snap = df.groupby(["expiry", "strike"], as_index=False)[["gex", "vex", "open_interest"]].sum()
    snap["expiry"] = snap["expiry"].dt.strftime("%Y-%m-%d")
    snap.insert(0, "date", date)
    snap.insert(0, "ticker", ticker)
    with _connect() as con:
        con.execute("DELETE FROM snapshots WHERE ticker = ? AND date = ?", (ticker, date))
        snap.to_sql("snapshots", con, if_exists="append", index=False)


def previous_snapshot(ticker: str, date: str) -> tuple[str | None, pd.DataFrame]:
    """Most recent snapshot from before `date` -> (its date, DataFrame)."""
    with _connect() as con:
        row = con.execute(
            "SELECT MAX(date) FROM snapshots WHERE ticker = ? AND date < ?", (ticker, date)
        ).fetchone()
        if row[0] is None:
            return None, pd.DataFrame(columns=COLS)
        prev = pd.read_sql(
            "SELECT expiry, strike, gex, vex, open_interest FROM snapshots WHERE ticker = ? AND date = ?",
            con, params=(ticker, row[0]),
        )
    prev["expiry"] = pd.to_datetime(prev["expiry"])
    return row[0], prev


def pct_change(now_grid: pd.DataFrame, prev: pd.DataFrame, value: str) -> pd.DataFrame:
    """% change per cell, aligned to `now_grid`. NaN where there is no previous value."""
    if prev.empty:
        return pd.DataFrame(index=now_grid.index, columns=now_grid.columns, dtype=float)
    prev_grid = prev.pivot_table(index="strike", columns="expiry", values=value, aggfunc="sum")
    prev_grid = prev_grid.reindex(index=now_grid.index, columns=now_grid.columns)
    return (now_grid - prev_grid) / prev_grid.abs().where(prev_grid != 0) * 100
