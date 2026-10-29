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


# ---------- Sidebar ----------
with st.sidebar:
    st.title("OI Gamma")
    ticker = st.text_input("Ticker", "SPY").strip().upper()
    n_exp = st.slider("Number of expiries", 1, 12, 4)
    n_strikes = st.slider("Strikes above / below spot", 5, 60, 15)
    if st.button("Refresh data"):
        load.clear()
    st.caption("Data: CBOE, delayed ~15 min. Dealers assumed long calls / short puts.")

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

# ---------- Top bar ----------
c = st.columns(6)
c[0].metric(ticker, f"{spot:,.2f}", f"{quote.get('price_change_percent', 0):.2f}%")
c[1].metric("Net GEX", charts.fmt_money(levels["net_gex"]))
c[2].metric("Net VEX", charts.fmt_money(levels["net_vex"]))
c[3].metric("Gamma flip", f"{levels['gamma_flip']:,.2f}" if levels["gamma_flip"] else "—")
c[4].metric("Call wall", f"{levels['call_wall']:g}" if levels["call_wall"] else "—")
c[5].metric("Put wall", f"{levels['put_wall']:g}" if levels["put_wall"] else "—")
st.caption(f"Last trade: {quote.get('last_trade_time')} (New York time) · "
           f"% badges vs {prev_date or 'no earlier snapshot yet'} · stats use the {n_exp} expiries shown")

if df.empty:
    st.warning("No options found for this ticker.")
    st.stop()

# ---------- Tabs ----------
tab_gex, tab_vex, tab_oi = st.tabs(["⚡ GEX", "〰 VEX", "OI / Volume"])

for tab, col, name in [(tab_gex, "gex", "Gamma exposure ($ per 1% move)"),
                       (tab_vex, "vex", "Vanna exposure ($ per 1 vol point)")]:
    with tab:
        g = exposure.grid(df, col)
        pct = history.pct_change(g, prev, col)
        st.plotly_chart(charts.heatmap(g, spot, name, pct), width="stretch", config=charts.LOCKED)

with tab_oi:
    value = st.radio("Show", ["open_interest", "volume"], horizontal=True,
                     format_func=lambda v: v.replace("_", " ").title())
    st.plotly_chart(charts.oi_bars(df, spot, value), width="stretch")
    st.dataframe(
        df[["option", "expiry", "type", "strike", "open_interest", "volume", "iv", "gamma", "gex", "vex"]]
        .sort_values(["expiry", "strike"]),
        width="stretch", hide_index=True,
    )
