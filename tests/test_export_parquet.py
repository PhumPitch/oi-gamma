import pandas as pd

from scripts import export_parquet
from src import history


def chain() -> pd.DataFrame:
    return pd.DataFrame({
        "expiry": [pd.Timestamp("2099-01-16")], "strike": [100.0],
        "gex": [1.0], "vex": [2.0], "open_interest": [5],
    })


def test_one_file_per_day_and_skip_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    out = tmp_path / "chains"
    history.save_snapshot("SPY", "2026-10-27", chain())
    history.save_snapshot("QQQ", "2026-10-27", chain())
    history.save_snapshot("SPY", "2026-10-28", chain())

    assert export_parquet.export(out) == ["2026-10-27", "2026-10-28"]
    assert set(pd.read_parquet(out / "2026-10-27.parquet")["ticker"]) == {"SPY", "QQQ"}

    assert export_parquet.export(out) == []  # nothing new
    assert export_parquet.export(out, force=True) == ["2026-10-27", "2026-10-28"]
