from datetime import date

import pandas as pd
import pytest

from src import history


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file (DATABASE_URL wins over secrets.toml)."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")


def chain(gex: float) -> pd.DataFrame:
    # two rows on the same (expiry, strike) -> save_snapshot must sum them
    return pd.DataFrame({
        "expiry": [pd.Timestamp("2099-01-16")] * 2, "strike": [100.0, 100.0],
        "gex": [gex / 2, gex / 2], "vex": [1.0, 1.0], "open_interest": [5, 5],
    })


def test_save_and_previous_snapshot():
    history.save_snapshot("SPY", "2026-10-27", chain(100))
    history.save_snapshot("SPY", "2026-10-28", chain(150))
    prev_date, prev = history.previous_snapshot("SPY", "2026-10-29")
    assert prev_date == "2026-10-28"
    assert prev["gex"].item() == 150 and prev["open_interest"].item() == 10
    assert prev["expiry"].item() == pd.Timestamp("2099-01-16")
    assert history.previous_snapshot("SPY", "2026-10-27")[0] is None


def test_same_day_is_replaced():
    history.save_snapshot("SPY", "2026-10-28", chain(100))
    history.save_snapshot("SPY", "2026-10-28", chain(300))
    _, prev = history.previous_snapshot("SPY", "2026-10-29")
    assert len(prev) == 1 and prev["gex"].item() == 300


def test_pct_change():
    history.save_snapshot("SPY", "2026-10-28", chain(100))
    _, prev = history.previous_snapshot("SPY", "2026-10-29")
    now = pd.DataFrame({pd.Timestamp("2099-01-16"): [150.0, 7.0]}, index=[100.0, 105.0])
    pct = history.pct_change(now, prev, "gex")
    assert pct.loc[100.0].item() == pytest.approx(50)
    assert pd.isna(pct.loc[105.0].item())  # no previous value for this strike


def test_prune():
    history.save_snapshot("SPY", "2026-09-01", chain(100))
    history.save_snapshot("SPY", "2026-10-28", chain(100))
    assert history.prune(30, today=date(2026, 10, 29)) == 1
    assert history.previous_snapshot("SPY", "2026-10-28")[0] is None


def test_watchlist():
    for t in ["spx", "SPY ", "NBIS", "SPX"]:  # lower case, spaces and duplicates
        history.add_ticker(t)
    assert history.get_watchlist() == ["SPX", "SPY", "NBIS"]
    history.remove_ticker("spy")
    history.add_ticker("SPY")  # goes to the end again
    assert history.get_watchlist() == ["SPX", "NBIS", "SPY"]
