"""Plotly charts: exposure heatmap and OI / volume bars."""
import numpy as np
import pandas as pd
import plotly.colors as pcolors
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


# Colors close to the reference app. Zero sits in the middle (0.5) because zmid=0.
# GEX: purple (negative) -> lime green (~0) -> yellow (positive), Viridis-like.
GEX_SCALE = [[0, "#3b0f5e"], [0.2, "#46327e"], [0.35, "#277f8e"], [0.5, "#7ad151"],
             [0.75, "#b5de2b"], [1, "#fde725"]]
# VEX: purple (negative) -> slate blue (~0) -> teal -> yellow (largest positive).
VEX_SCALE = [[0, "#3a0f5e"], [0.3, "#4b2a7b"], [0.5, "#3e4a8c"], [0.7, "#2c6f8f"],
             [0.9, "#25a0a0"], [1, "#fde725"]]


def _spot_row(strikes: pd.Index, spot: float) -> int:
    return int(np.argmin(abs(strikes.values - spot)))


def _cell_text(z: np.ndarray, pct: pd.DataFrame | None) -> list[list[str]]:
    """'▲12% $1.2M' per cell. Badges only on cells >= 5% of the biggest one, star on the biggest."""
    big = np.abs(z) >= 0.05 * np.abs(z).max() if z.size else z
    text = [[(_badge(pct.iat[i, j]) if pct is not None and big[i, j] else "") + fmt_money(z[i, j])
             for j in range(z.shape[1])] for i in range(z.shape[0])]
    if z.size:
        i, j = np.unravel_index(np.abs(z).argmax(), z.shape)
        text[i][j] += " ★"
    return text


def _color_limit(z: np.ndarray) -> float:
    """Clip the color range so one huge strike doesn't wash out everything else."""
    return float(np.percentile(np.abs(z), 98)) if z.size else 1.0


def heatmap(grid: pd.DataFrame, spot: float, title: str, pct: pd.DataFrame | None = None,
            colorscale=GEX_SCALE) -> go.Figure:
    """Desktop: Plotly heatmap, strike (rows) x expiry (cols). Badges = % change vs the previous day."""
    z = grid.values
    r = _spot_row(grid.index, spot)
    # Spot strike is highlighted in the axis label itself (no extra space needed on the left)
    ys = [f"<b><span style='color:orange'>▶ {s:g}</span></b>" if i == r else f"{s:g}"
          for i, s in enumerate(grid.index)]
    xs = [c.strftime("%Y-%m-%d") for c in grid.columns]
    lim = _color_limit(z)
    fig = go.Figure(go.Heatmap(
        z=z, x=xs, y=ys, text=_cell_text(z, pct), texttemplate="%{text}", textfont={"size": 11},
        colorscale=colorscale, zmid=0, zmin=-lim, zmax=lim, xgap=1, ygap=1,
        hovertemplate="Strike %{y}<br>Expiry %{x}<br>%{text}<extra></extra>",
        colorbar={"title": "$"},
    ))
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=r - 0.5, y1=r + 0.5,
                  line={"color": "white", "width": 2})
    # Fixed view centered on the spot row: same number of rows above and below.
    # Range is in row-index units; [bottom, top] with top < bottom puts high strikes on top.
    k = max(r, len(ys) - 1 - r)
    fig.update_layout(
        title=title, height=max(400, 24 * (2 * k + 1) + 100),
        margin={"l": 0, "r": 20, "t": 60, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"type": "category", "title": "Strike", "range": [r + k + 0.5, r - k - 0.5], "fixedrange": True},
        xaxis={"type": "category", "side": "top", "fixedrange": True},
    )
    return fig


# CSS for the phone table. Scroll box in both directions; strike column + date row stay fixed (sticky).
TABLE_CSS = """<style>
.hm {max-height: 70vh; overflow: auto; border-radius: .5rem;}
.hm table {width: max-content; border-collapse: separate; border-spacing: 1px; font: 12px monospace; white-space: nowrap;}
.hm th {position: sticky; background: #0b0d12; color: #e6e8ee; padding: 4px 8px; z-index: 1;}
.hm thead th {top: 0; z-index: 2;}
.hm tbody th {left: 0; text-align: right;}
.hm thead th:first-child {left: 0; z-index: 3;}
.hm td {padding: 4px 10px; text-align: right; min-width: 110px;}
.hm tr.spot th {background: #fff; color: #000; border-radius: 4px;}
.hm tr.spot td {box-shadow: inset 0 1px #fff, inset 0 -1px #fff;}
.hm .up, .hm .dn {font-size: 10px; padding: 0 4px; border-radius: 6px; background: #000; margin-right: 4px;}
.hm .up {color: #4ade80;} .hm .dn {color: #f87171;}
</style>"""


def _text_color(rgb: str) -> str:
    """Black text on bright cells, white on dark ones (rgb = 'rgb(r, g, b)')."""
    r, g, b = (int(float(v)) for v in rgb[4:-1].split(","))
    return "#000" if 0.299 * r + 0.587 * g + 0.114 * b > 140 else "#fff"


def heatmap_html(grid: pd.DataFrame, spot: float, pct: pd.DataFrame | None = None,
                 colorscale=GEX_SCALE) -> str:
    """Phone: same heatmap as an HTML table, so it can scroll sideways with a readable font."""
    z = grid.values
    r = _spot_row(grid.index, spot)
    lim = _color_limit(z) or 1.0
    # Same color mapping as Plotly with zmid=0: -lim -> 0, 0 -> 0.5, +lim -> 1
    t = np.clip((z + lim) / (2 * lim), 0, 1)
    colors = [pcolors.sample_colorscale(colorscale, list(row)) for row in t] if z.size else []
    text = _cell_text(z, pct)

    head = "".join(f"<th>{c.strftime('%Y-%m-%d')}</th>" for c in grid.columns)
    rows = []
    for i, strike in enumerate(grid.index):
        cells = []
        for j in range(z.shape[1]):
            label = text[i][j]
            if label[:1] in "▲▼":  # badge -> small pill, green up / red down
                badge, label = label.split(" ", 1)
                label = f"<span class='{'up' if badge[0] == '▲' else 'dn'}'>{badge}</span>{label}"
            bg = colors[i][j]
            cells.append(f"<td style='background:{bg};color:{_text_color(bg)}'>{label}</td>")
        cls = " class='spot' id='hm-spot'" if i == r else ""
        rows.append(f"<tr{cls}><th>{strike:g}</th>{''.join(cells)}</tr>")
    # Small script: scroll the box so the spot row starts in the middle
    js = ("<script>const s=document.getElementById('hm-spot');"
          "if(s){const b=s.closest('.hm');b.scrollTop=s.offsetTop-b.clientHeight/2;}</script>")
    return (f"{TABLE_CSS}<div class='hm'><table><thead><tr><th>Strike</th>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>{js}")


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
