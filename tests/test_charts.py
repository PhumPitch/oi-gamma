import numpy as np
import pandas as pd

from src import charts


def _grid():
    cols = pd.to_datetime(["2026-11-06", "2026-11-13"])
    return pd.DataFrame([[1e6, -2e5], [-4e6, 0.0], [3e5, 5e4]], index=[110.0, 100.0, 90.0], columns=cols)


def test_heatmap_html_rows_and_spot():
    g = _grid()
    pct = pd.DataFrame(np.full(g.shape, 12.0), index=g.index, columns=g.columns)
    html = charts.heatmap_html(g, spot=101, pct=pct)
    assert html.count("<tr") == 1 + len(g)          # header + one row per strike
    assert html.count("id='hm-spot'") == 1          # spot row marked once
    assert "<th>2026-11-06</th>" in html
    assert "class='up'>▲12%" in html                # badge rendered as a pill
    assert "★" in html                              # biggest cell starred


def test_text_color_contrast():
    assert charts._text_color("rgb(253, 231, 37)") == "#000"   # yellow -> black text
    assert charts._text_color("rgb(59, 15, 94)") == "#fff"     # purple -> white text
