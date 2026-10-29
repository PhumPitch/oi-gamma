"""Daily snapshots (for the % change badges) and the ticker watchlist.

Uses Postgres (Neon) when DATABASE_URL is set (env var or st.secrets),
otherwise the local SQLite file data/history.db.
"""
import functools
import os
from datetime import date as Date, timedelta
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"
COLS = ["expiry", "strike", "gex", "vex", "open_interest"]

META = sa.MetaData()
SNAPSHOTS = sa.Table(
    "snapshots", META,
    sa.Column("ticker", sa.String), sa.Column("date", sa.String),  # date = "YYYY-MM-DD"
    sa.Column("expiry", sa.String), sa.Column("strike", sa.Float),
    sa.Column("gex", sa.Float), sa.Column("vex", sa.Float), sa.Column("open_interest", sa.Float),
)
SNAP_IDX = sa.Index("ix_snapshots_ticker_date", SNAPSHOTS.c.ticker, SNAPSHOTS.c.date)
WATCHLIST = sa.Table(
    "watchlist", META,
    sa.Column("ticker", sa.String, primary_key=True),
    sa.Column("position", sa.Integer, nullable=False),  # order used by the ◀ ▶ buttons
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:  # no secrets.toml, or streamlit not installed
            url = None
    if not url:
        DB_PATH.parent.mkdir(exist_ok=True)
        return f"sqlite:///{DB_PATH}"
    return url.replace("postgres://", "postgresql://", 1)  # SQLAlchemy needs the long name


@functools.cache  # one engine (connection pool) per URL for the whole process
def _make_engine(url: str) -> sa.Engine:
    engine = sa.create_engine(url, pool_pre_ping=True)  # Neon closes idle connections
    META.create_all(engine)
    SNAP_IDX.create(engine, checkfirst=True)  # also adds the index to old SQLite files
    return engine


def engine() -> sa.Engine:
    return _make_engine(database_url())


# ---------- Snapshots ----------
def save_snapshot(ticker: str, date: str, df: pd.DataFrame) -> None:
    """Replace this day's snapshot, so we always keep the last one of each day."""
    snap = df.groupby(["expiry", "strike"], as_index=False)[["gex", "vex", "open_interest"]].sum()
    snap["expiry"] = pd.to_datetime(snap["expiry"]).dt.strftime("%Y-%m-%d")
    snap.insert(0, "date", date)
    snap.insert(0, "ticker", ticker)
    write_rows(ticker, date, snap)


def write_rows(ticker: str, date: str, rows: pd.DataFrame) -> None:
    """Delete + insert in one transaction (also used by the SQLite -> Neon copy script)."""
    with engine().begin() as con:
        con.execute(SNAPSHOTS.delete().where(SNAPSHOTS.c.ticker == ticker, SNAPSHOTS.c.date == date))
        rows.to_sql("snapshots", con, if_exists="append", index=False, chunksize=5000)


def previous_snapshot(ticker: str, date: str) -> tuple[str | None, pd.DataFrame]:
    """Most recent snapshot from before `date` -> (its date, DataFrame)."""
    s = SNAPSHOTS.c
    with engine().connect() as con:
        prev_date = con.execute(
            sa.select(sa.func.max(s.date)).where(s.ticker == ticker, s.date < date)
        ).scalar()
        if prev_date is None:
            return None, pd.DataFrame(columns=COLS)
        prev = pd.read_sql(
            sa.select(*(s[c] for c in COLS)).where(s.ticker == ticker, s.date == prev_date), con
        )
    prev["expiry"] = pd.to_datetime(prev["expiry"])
    return prev_date, prev


def prune(days: int = 30, today: Date | None = None) -> int:
    """Delete snapshots older than `days` calendar days. Returns rows deleted."""
    cutoff = ((today or Date.today()) - timedelta(days=days)).isoformat()
    with engine().begin() as con:
        return con.execute(SNAPSHOTS.delete().where(SNAPSHOTS.c.date < cutoff)).rowcount


def pct_change(now_grid: pd.DataFrame, prev: pd.DataFrame, value: str) -> pd.DataFrame:
    """% change per cell, aligned to `now_grid`. NaN where there is no previous value."""
    if prev.empty:
        return pd.DataFrame(index=now_grid.index, columns=now_grid.columns, dtype=float)
    prev_grid = prev.pivot_table(index="strike", columns="expiry", values=value, aggfunc="sum")
    prev_grid = prev_grid.reindex(index=now_grid.index, columns=now_grid.columns)
    return (now_grid - prev_grid) / prev_grid.abs().where(prev_grid != 0) * 100


# ---------- Watchlist ----------
def get_watchlist() -> list[str]:
    with engine().connect() as con:
        return list(con.execute(
            sa.select(WATCHLIST.c.ticker).order_by(WATCHLIST.c.position, WATCHLIST.c.ticker)
        ).scalars())


def add_ticker(ticker: str) -> None:
    """Add to the end of the watchlist (does nothing if it is already there)."""
    ticker = ticker.strip().upper()
    w = WATCHLIST.c
    with engine().begin() as con:
        if not ticker or con.execute(sa.select(w.ticker).where(w.ticker == ticker)).first():
            return
        last = con.execute(sa.select(sa.func.max(w.position))).scalar()
        con.execute(WATCHLIST.insert().values(ticker=ticker, position=(last or 0) + 1))


def remove_ticker(ticker: str) -> None:
    with engine().begin() as con:
        con.execute(WATCHLIST.delete().where(WATCHLIST.c.ticker == ticker.strip().upper()))
