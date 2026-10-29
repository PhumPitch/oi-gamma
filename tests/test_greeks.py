import numpy as np
import pandas as pd

from src import exposure, greeks
from src.cboe import cboe_symbol, parse_options


def test_gamma_textbook():
    # S=K=100, T=1, sigma=20%, r=q=0 -> gamma ~ 0.019848
    assert np.isclose(greeks.gamma(100, 100, 1, 0.2), 0.019848, atol=1e-5)


def test_vanna_matches_finite_difference():
    S, K, T, s, h = 100, 110, 0.5, 0.3, 1e-5
    def delta(sig):
        d1, _ = greeks.d1_d2(S, K, T, sig)
        from scipy.stats import norm
        return norm.cdf(d1)
    fd = (delta(s + h) - delta(s - h)) / (2 * h)
    assert np.isclose(greeks.vanna(S, K, T, s), fd, rtol=1e-4)


def test_parse_occ_and_symbol():
    df = parse_options([{"option": "NBIS260717C00182500", "open_interest": 1, "volume": 0, "iv": 0.5,
                         "delta": 0.5, "gamma": 0.01, "bid": 1, "ask": 1.1, "last_trade_price": 1}])
    assert df.loc[0, "strike"] == 182.5 and df.loc[0, "type"] == "C"
    assert df.loc[0, "expiry"] == pd.Timestamp("2026-07-17")
    assert cboe_symbol("spx") == "_SPX" and cboe_symbol("nbis") == "NBIS"


def test_gex_sign_call_positive_put_negative():
    chain = pd.DataFrame({
        "expiry": [pd.Timestamp("2099-01-01")] * 2, "type": ["C", "P"], "strike": [100.0, 100.0],
        "open_interest": [10, 10], "iv": [0.3, 0.3], "gamma": [0.02, 0.02],
    })
    df = exposure.add_exposures(chain, 100)
    assert df.loc[df["type"] == "C", "gex"].item() > 0
    assert df.loc[df["type"] == "P", "gex"].item() < 0
    # 0.02 * 10 * 100 * 100^2 * 0.01 = 2000
    assert np.isclose(df["gex"].abs().iloc[0], 2000)
