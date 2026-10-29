"""Plotly charts: exposure heatmap and OI / volume bars."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go


def fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e9:
        return f"{sign}${x / 1e9:,.2f}B"
    if x >= 1e6:
        return f"{sign}${x / 1e6:,.2f}M"
    return f"{sign}${x / 1e3:,.1f}K"


def _badge(p: float) -> str:
    if pd.isna(p) or abs(p) < 1:
        return ""
    return f"{'▲' if p > 0 else '▼'}{abs(p):.0f}% "


def _spot_row(strikes: pd.Index, spot: float) -> int:
    return int(np.argmin(abs(strikes.values - spot)))


def heatmap(grid: pd.DataFrame, spot: float, title: str, pct: pd.DataFrame | None = None) -> go.Figure:
    """Strike (rows) x expiry (cols). Badges show % change vs the previous day."""
    z = grid.values
    ys = [f"{s:g}" for s in grid.index]
    xs = [c.strftime("%Y-%m-%d") for c in grid.columns]

    # Badges only on cells that matter (>= 5% of the biggest cell), to keep it readable
    big = np.abs(z) >= 0.05 * np.abs(z).max() if z.size else z
    text = [[(_badge(pct.iat[i, j]) if pct is not None and big[i, j] else "") + fmt_money(z[i, j])
             for j in range(z.shape[1])] for i in range(z.shape[0])]
    if z.size:
        i, j = np.unravel_index(np.abs(z).argmax(), z.shape)
        text[i][j] += " ★"

    # Clip the color range so one huge strike doesn't wash out everything else
    lim = np.percentile(np.abs(z), 98) if z.size else 1
    fig = go.Figure(go.Heatmap(
        z=z, x=xs, y=ys, text=text, texttemplate="%{text}", textfont={"size": 11},
        colorscale="Viridis", zmid=0, zmin=-lim, zmax=lim, xgap=1, ygap=1,
        hovertemplate="Strike %{y}<br>Expiry %{x}<br>%{text}<extra></extra>",
        colorbar={"title": "$"},
    ))
    r = _spot_row(grid.index, spot)
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=r - 0.5, y1=r + 0.5,
                  line={"color": "white", "width": 2})
    fig.add_annotation(xref="paper", x=0, y=ys[r], text=f"spot {spot:g} ▶", showarrow=False,
                       xanchor="right", xshift=-40, font={"color": "orange"})
    # Fixed view centered on the spot row: same number of rows above and below.
    # Range is in row-index units; [bottom, top] with top < bottom puts high strikes on top.
    k = max(r, len(ys) - 1 - r)
    fig.update_layout(
        title=title, height=max(400, 24 * (2 * k + 1) + 120), margin={"l": 120, "r": 20, "t": 50, "b": 40},
        yaxis={"type": "category", "title": "Strike", "range": [r + k + 0.5, r - k - 0.5], "fixedrange": True},
        xaxis={"type": "category", "side": "top", "fixedrange": True},
    )
    return fig


# Only keep "download as PNG" in the toolbar, so zoom / autoscale can't move the view
LOCKED = {"modeBarButtons": [["toImage"]], "displaylogo": False}


def oi_bars(df: pd.DataFrame, spot: float, value: str = "open_interest") -> go.Figure:
    """Calls to the right, puts to the left, by strike."""
    by = df.pivot_table(index="strike", columns="type", values=value, aggfunc="sum", fill_value=0)
    by = by.reindex(columns=["C", "P"], fill_value=0)
    fig = go.Figure([
        go.Bar(y=by.index, x=by["C"], orientation="h", name="Calls", marker_color="#2ca02c"),
        go.Bar(y=by.index, x=-by["P"], orientation="h", name="Puts", marker_color="#d62728",
               customdata=by["P"], hovertemplate="%{customdata:,.0f}"),
    ])
    fig.add_hline(y=spot, line_dash="dash", line_color="orange", annotation_text=f"spot {spot:g}")
    label = value.replace("_", " ").title()
    fig.update_layout(barmode="relative", height=max(400, 14 * len(by) + 120),
                      xaxis_title=f"{label} (puts shown negative)", yaxis_title="Strike")
    return fig
