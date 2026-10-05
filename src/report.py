"""Single-stock factor report: stock_report("AAPL")."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.data_loader import load_prices

CATEGORIES = ["Value", "Quality", "Momentum", "Growth", "LowVol"]
METRICS = ["Ret1M", "Ret6M", "Ret12M", "FCFYield", "EV_EBITDA", "Volatility", "Beta"]
BLUE, MUTED = "#2a78d6", "#898781"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _load_rankings() -> pd.DataFrame:
    path = config.RANKINGS_DIR / "rankings.csv"
    if path.exists():
        return pd.read_csv(path)
    from src.rank import build_rankings
    return build_rankings()


def stock_report(ticker: str, rankings: pd.DataFrame | None = None,
                 prices: pd.DataFrame | None = None, show: bool = True) -> dict:
    """Print a factor profile for one ticker and return its tables, text and figures."""
    rank = (rankings if rankings is not None else _load_rankings()).set_index("Ticker")
    if ticker not in rank.index:
        raise ValueError(f"{ticker} not in rankings")
    row = rank.loc[ticker]
    peers = rank[rank["Sector"] == row["Sector"]]
    sec_rank = int(peers["Composite"].rank(ascending=False)[ticker]) if pd.notna(row["Composite"]) else None

    metrics = pd.DataFrame({ticker: row[METRICS], "SectorMedian": peers[METRICS].median()}).astype(float)
    cats = row[CATEGORIES].astype(float).dropna()
    strong, weak = (cats.idxmax(), cats.idxmin()) if len(cats) else ("n/a", "n/a")
    pct = row["Percentile"]
    text = (
        f"{ticker} ranks in the {_ordinal(int(round(pct)))} percentile of the {rank['Composite'].notna().sum()}-stock "
        f"universe (quintile {row['Quintile']}) and #{sec_rank} of {len(peers)} in {row['Sector']}. "
        f"Its strongest factor is {strong} (z = {cats.get(strong, float('nan')):+.2f}) and its weakest is "
        f"{weak} (z = {cats.get(weak, float('nan')):+.2f}); this is a descriptive factor profile, not a "
        f"recommendation."
    )

    print(f"{ticker} — {row['Company']} ({row['Sector']})")
    print(f"Composite {row['Composite']:+.2f} | percentile {pct:.0f} | quintile {row['Quintile']} | "
          f"sector rank {sec_rank}/{len(peers)}")
    print("Category z-scores: " + "  ".join(f"{c} {row[c]:+.2f}" for c in CATEGORIES if pd.notna(row[c])))
    print(metrics.round(3).to_string())
    print(text)

    # Radar uses category percentiles (0-100) so axes share a scale.
    cat_pct = rank[CATEGORIES].rank(pct=True) * 100
    theta = CATEGORIES + CATEGORIES[:1]
    radar = go.Figure()
    for name, vals, color in [(ticker, cat_pct.loc[ticker], BLUE),
                              (f"{row['Sector']} median", cat_pct.loc[peers.index].median(), MUTED)]:
        r = vals.reindex(CATEGORIES).tolist()
        radar.add_trace(go.Scatterpolar(r=r + r[:1], theta=theta, name=name, fill="toself",
                                        line=dict(color=color, width=2), opacity=0.75))
    radar.update_layout(title=f"{ticker} factor percentiles", template="simple_white",
                        polar=dict(radialaxis=dict(range=[0, 100])), height=420)

    px = (prices if prices is not None else load_prices([ticker]))
    s = px[ticker].dropna().iloc[-252:] if ticker in px.columns else pd.Series(dtype=float)
    price_fig = go.Figure(go.Scatter(x=s.index, y=s, line=dict(color=BLUE, width=2), name=ticker))
    price_fig.update_layout(title=f"{ticker} adjusted price, last 1Y", template="simple_white",
                            yaxis_title="Price", height=380, showlegend=False)
    if show:
        radar.show()
        price_fig.show()
    return {"summary": row, "metrics": metrics, "text": text, "radar": radar, "price": price_fig}
