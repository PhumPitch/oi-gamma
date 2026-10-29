"""Fetch delayed option chains from CBOE and turn them into a DataFrame."""
import pandas as pd
import requests

URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
INDICES = {"SPX", "NDX", "RUT", "VIX", "XSP", "DJX"}


def cboe_symbol(ticker: str) -> str:
    """CBOE uses an underscore prefix for indices: SPX -> _SPX."""
    t = ticker.strip().upper().lstrip("_^")
    return f"_{t}" if t in INDICES else t


def fetch_chain(ticker: str) -> tuple[dict, pd.DataFrame]:
    """Return (quote info, option chain DataFrame)."""
    resp = requests.get(
        URL.format(symbol=cboe_symbol(ticker)),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    quote = {k: v for k, v in data.items() if k != "options"}
    return quote, parse_options(data["options"])


def parse_options(options: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(options)
    # OCC symbol: ROOT + YYMMDD + C/P + strike*1000 (8 digits), e.g. NBIS261030C00095000
    parts = df["option"].str.extract(r"^(?P<root>.+?)(?P<date>\d{6})(?P<type>[CP])(?P<strike>\d{8})$")
    df["expiry"] = pd.to_datetime(parts["date"], format="%y%m%d")
    df["type"] = parts["type"]
    df["strike"] = parts["strike"].astype(int) / 1000
    cols = ["option", "expiry", "type", "strike", "open_interest", "volume",
            "iv", "delta", "gamma", "bid", "ask", "last_trade_price"]
    return df[cols]
