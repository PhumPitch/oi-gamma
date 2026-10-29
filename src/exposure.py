"""Dealer exposure (GEX / VEX) per contract, grids and key levels.

Convention: dealers are long calls and short puts, so calls count + and puts count -.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src import greeks

CONTRACT = 100
MIN_T = 1 / (365 * 24)  # 1 hour, avoids divide-by-zero on expiry day


def years_to_expiry(expiry: pd.Series, now: datetime | None = None) -> pd.Series:
    """Expiry is at ~16:00 New York = 20:00 UTC (ignores daylight saving, ~1h error)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    close = expiry + pd.Timedelta(hours=20)
    return ((close - now).dt.total_seconds() / (365 * 24 * 3600)).clip(lower=MIN_T)


def add_exposures(chain: pd.DataFrame, spot: float) -> pd.DataFrame:
    """Add T, sign, gex and vex columns. Rows with no IV or expired are dropped."""
    df = chain[chain["iv"] > 0].copy()
    df["T"] = years_to_expiry(df["expiry"])
    df["sign"] = np.where(df["type"] == "C", 1, -1)
    oi = df["open_interest"] * CONTRACT * df["sign"]
    # $ delta change for a 1% move in the underlying
    df["gex"] = df["gamma"] * oi * spot**2 * 0.01
    # $ delta change for a 1 vol-point change in IV
    df["vanna"] = greeks.vanna(spot, df["strike"], df["T"], df["iv"])
    df["vex"] = df["vanna"] * oi * spot * 0.01
    return df


def grid(df: pd.DataFrame, value: str) -> pd.DataFrame:
    """Strike x expiry table (strikes high -> low, like the reference app)."""
    g = df.pivot_table(index="strike", columns="expiry", values=value, aggfunc="sum", fill_value=0)
    return g.sort_index(ascending=False)


def strikes_near(strikes: pd.Series, spot: float, n: int) -> np.ndarray:
    """The n strikes above and n strikes below spot (keeps the heatmap a readable size)."""
    s = np.sort(strikes.unique())
    i = np.searchsorted(s, spot)
    return s[max(0, i - n): i + n]


def gex_at_spots(df: pd.DataFrame, spots: np.ndarray) -> np.ndarray:
    """Total GEX if the underlying were at each price in `spots` (re-priced with BS gamma)."""
    S = spots[:, None]
    g = greeks.gamma(S, df["strike"].values, df["T"].values, df["iv"].values)
    oi = (df["open_interest"] * CONTRACT * df["sign"]).values
    return (g * oi * S**2 * 0.01).sum(axis=1)


def gamma_flip(df: pd.DataFrame, spot: float, width: float = 0.25) -> float | None:
    """Price where total GEX crosses zero, closest to spot. None if no crossing."""
    spots = np.linspace(spot * (1 - width), spot * (1 + width), 201)
    total = gex_at_spots(df, spots)
    cross = np.where(np.diff(np.sign(total)) != 0)[0]
    if len(cross) == 0:
        return None
    # linear interpolation between the two grid points around each crossing
    flips = spots[cross] - total[cross] * (spots[cross + 1] - spots[cross]) / (total[cross + 1] - total[cross])
    return float(flips[np.argmin(abs(flips - spot))])


def key_levels(df: pd.DataFrame, spot: float) -> dict:
    by_strike = df.groupby(["type", "strike"])["gex"].sum()
    calls, puts = by_strike.get("C", pd.Series(dtype=float)), by_strike.get("P", pd.Series(dtype=float))
    return {
        "net_gex": df["gex"].sum(),
        "net_vex": df["vex"].sum(),
        "call_wall": calls.idxmax() if len(calls) else None,
        "put_wall": puts.idxmin() if len(puts) else None,
        "gamma_flip": gamma_flip(df, spot),
    }
