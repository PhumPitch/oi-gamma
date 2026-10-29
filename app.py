"""OI Gamma: GEX / VEX heatmaps for US stocks and indices (CBOE delayed data).

Run: streamlit run app.py
"""
import hmac

import pandas as pd
import streamlit as st

from src import charts, cboe, exposure, history

st.set_page_config(page_title="OI Gamma", layout="wide")


# ---------- Password gate ----------
def check_password() -> bool:
    if st.session_state.get("auth_ok"):
        return True
    pw = st.text_input("Password", type="password")
    if pw:
        if hmac.compare_digest(pw, st.secrets["APP_PASSWORD"]):
            st.session_state["auth_ok"] = True
            st.rerun()
        st.error("Wrong password")
    return False


if not check_password():
    st.stop()


@st.cache_data(ttl=300, show_spinner="Loading option chain from CBOE...")
def load(ticker: str):
    return cboe.fetch_chain(ticker)


@st.cache_data(ttl=600, show_spinner=False)  # snapshots change once a day (cron job)
def load_prev(ticker: str, date: str):
    return history.previous_snapshot(ticker, date)


@st.cache_data(ttl=600, show_spinner=False)  # cleared when the watchlist is edited below
def cached_watchlist() -> list[str]:
    return history.get_watchlist()


def load_watchlist() -> list[str]:
    try:
        return cached_watchlist() or ["SPY"]
    except Exception:  # DB down -> still usable with one ticker (errors are not cached)
        return ["SPY"]


def step(delta: int) -> None:
    """◀ ▶ callback: move to the previous / next ticker in the watchlist (wraps around)."""
    tickers = load_watchlist()
    cur = (st.session_state.get("ticker") or "").strip().upper()
    i = tickers.index(cur) if cur in tickers else (-1 if delta > 0 else 0)  # new ticker -> first / last
    st.session_state["ticker"] = tickers[(i + delta) % len(tickers)]


def edit_watchlist(action, ticker: str) -> None:
    action(ticker)
    cached_watchlist.clear()


tickers = load_watchlist()
if st.session_state.get("ticker") is None:  # first visit, or the box was cleared
    st.session_state["ticker"] = tickers[0]
ticker = st.session_state["ticker"] = st.session_state["ticker"].strip().upper()  # typed "msft" -> MSFT

# Layout order on the page: nav bar -> heatmap -> settings (filled first, so sliders exist before use)
nav = st.container()
main = st.container()
settings = st.expander("⚙ Settings", expanded=False)

# ---------- Settings (collapsed, below the chart) ----------
with settings:
    n_exp = st.slider("Number of expiries", 1, 12, 4)
    n_strikes = st.slider("Strikes above / below spot", 5, 60, 15)
    if st.button("Refresh data"):
        load.clear()
    st.caption("Type a new ticker in the box above to view it, then add it here.")
    b = st.container(horizontal=True)
    if ticker not in tickers:
        b.button(f"➕ Add {ticker} to watchlist", on_click=edit_watchlist, args=(history.add_ticker, ticker))
    elif len(tickers) > 1:
        b.button(f"➖ Remove {ticker} from watchlist", on_click=edit_watchlist,
                 args=(history.remove_ticker, ticker))
    st.caption("Watchlist: " + ", ".join(tickers))
    st.caption("Data: CBOE, delayed ~15 min. Dealers assumed long calls / short puts.")

# ---------- Nav bar: ◀ ticker ▶ ----------
with nav:
    row = st.container(horizontal=True, vertical_alignment="center")  # stays one row on phones
    row.button("◀", on_click=step, args=(-1,))
    row.selectbox("Ticker", tickers, key="ticker", accept_new_options=True,
                  label_visibility="collapsed")
    row.button("▶", on_click=step, args=(1,))

try:
    quote, chain = load(ticker)
except Exception as e:  # bad ticker, network error, ...
    st.error(f"Could not load {ticker}: {e}")
    st.stop()

spot = quote["current_price"]
date = (quote.get("last_trade_time") or "")[:10]

# Exposures on the full chain, then filter for display.
# Snapshots are written by the daily cron job only (scripts/snapshot.py), not here.
df_all = exposure.add_exposures(chain, spot)
try:
    prev_date, prev = load_prev(ticker, date)
except Exception as e:  # DB down -> still show the heatmap, just no % badges
    st.warning(f"History DB not reachable, no % badges: {e}")
    prev_date, prev = None, pd.DataFrame(columns=history.COLS)

expiries = sorted(df_all["expiry"].unique())[:n_exp]
df = df_all[df_all["expiry"].isin(expiries)]
df = df[df["strike"].isin(exposure.strikes_near(df["strike"], spot, n_strikes))]
levels = exposure.key_levels(df_all[df_all["expiry"].isin(expiries)], spot)

with nav:
    chg = quote.get("price_change_percent", 0) or 0
    color = "green" if chg >= 0 else "red"
    bar = st.container(horizontal=True, vertical_alignment="center")
    bar.markdown(f"**{ticker}** • {spot:,.2f} &nbsp; :{color}[{chg:+.2f}%]")
    view = bar.segmented_control("View", ["GEX", "VEX", "OI / Volume"], default="GEX",
                                 required=True, label_visibility="collapsed")

# ---------- Main: key levels + chart ----------
with main:
    c = st.columns(5)
    c[0].metric("Net GEX", charts.fmt_money(levels["net_gex"]))
    c[1].metric("Net VEX", charts.fmt_money(levels["net_vex"]))
    c[2].metric("Gamma flip", f"{levels['gamma_flip']:,.2f}" if levels["gamma_flip"] else "—")
    c[3].metric("Call wall", f"{levels['call_wall']:g}" if levels["call_wall"] else "—")
    c[4].metric("Put wall", f"{levels['put_wall']:g}" if levels["put_wall"] else "—")

    if df.empty:
        st.warning("No options found for this ticker.")
        st.stop()

    if view in ("GEX", "VEX"):
        col = view.lower()
        name = {"gex": "Gamma exposure ($ per 1% move)", "vex": "Vanna exposure ($ per 1 vol point)"}[col]
        g = exposure.grid(df, col)
        pct = history.pct_change(g, prev, col)
        st.plotly_chart(charts.heatmap(g, spot, name, pct), width="stretch", config=charts.LOCKED)
    else:
        value = st.radio("Show", ["open_interest", "volume"], horizontal=True,
                         format_func=lambda v: v.replace("_", " ").title())
        st.plotly_chart(charts.oi_bars(df, spot, value), width="stretch")
        st.dataframe(
            df[["option", "expiry", "type", "strike", "open_interest", "volume", "iv", "gamma", "gex", "vex"]]
            .sort_values(["expiry", "strike"]),
            width="stretch", hide_index=True,
        )
    st.caption(f"Last trade: {quote.get('last_trade_time')} (New York time) · "
               f"% badges vs {prev_date or 'no earlier snapshot yet'} · stats use the {n_exp} expiries shown")
