import pandas as pd

from scripts import snapshot
from src import history


def fake_fetch(ticker):
    if ticker == "BAD":
        raise ConnectionError("CBOE down")
    quote = {"current_price": 100.0, "last_trade_time": "2026-10-28T16:15:00"}
    chain = pd.DataFrame({
        "expiry": [pd.Timestamp("2099-01-16")] * 2, "type": ["C", "P"], "strike": [100.0, 100.0],
        "open_interest": [10, 5], "iv": [0.2, 0.2], "gamma": [0.05, 0.05],
    })
    return quote, chain


def test_one_bad_ticker_does_not_stop_the_rest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(snapshot.cboe, "fetch_chain", fake_fetch)
    for t in ["BAD", "SPY"]:
        history.add_ticker(t)

    snapshot.main()

    assert "failed: ['BAD']" in capsys.readouterr().out
    prev_date, prev = history.previous_snapshot("SPY", "2026-10-29")
    assert prev_date == "2026-10-28" and len(prev) == 1
