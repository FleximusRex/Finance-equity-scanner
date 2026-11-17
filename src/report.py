"""Single-stock factor report.

Run: python -m src.report AAPL [--universe {sp500,test50}]
"""
from __future__ import annotations

import sys
from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go

from src import cli, config
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
                 prices: pd.DataFrame | None = None) -> dict:
    """Factor profile for one ticker: summary row, metrics table, text and two figures."""
    rank = (rankings if rankings is not None else _load_rankings()).set_index("Ticker")
    if ticker not in rank.index:
        raise ValueError(f"{ticker} not in rankings")
    row = rank.loc[ticker]
    peers = rank[rank["Sector"] == row["Sector"]]
    sec_rank = None
    if pd.notna(row["Composite"]):
        sec_rank = int(peers["Composite"].rank(ascending=False)[ticker])

    metrics = pd.DataFrame(
        {ticker: row[METRICS], "SectorMedian": peers[METRICS].median()}
    ).astype(float)
    cats = row[CATEGORIES].astype(float).dropna()
    strong, weak = (cats.idxmax(), cats.idxmin()) if len(cats) else ("n/a", "n/a")
    pct = row["Percentile"]
    n_scored = rank["Composite"].notna().sum()
    text = (
        f"{ticker} ranks in the {_ordinal(round(pct))} percentile of the {n_scored}-stock "
        f"universe (quintile {row['Quintile']}) and #{sec_rank} of {len(peers)} in "
        f"{row['Sector']}. Its strongest factor is {strong} "
        f"(z = {cats.get(strong, float('nan')):+.2f}) and its weakest is {weak} "
        f"(z = {cats.get(weak, float('nan')):+.2f}). This is a descriptive factor profile, "
        f"not a recommendation."
    )
    lines = [
        f"{ticker} - {row['Company']} ({row['Sector']})",
        f"Composite {row['Composite']:+.2f} | percentile {pct:.0f} | quintile {row['Quintile']} "
        f"| sector rank {sec_rank}/{len(peers)}",
        "Category z-scores: "
        + "  ".join(f"{c} {row[c]:+.2f}" for c in CATEGORIES if pd.notna(row[c])),
        metrics.round(3).to_string(),
        text,
    ]

    # Radar uses category percentiles (0-100) so axes share a scale.
    cat_pct = rank[CATEGORIES].rank(pct=True) * 100
    theta = CATEGORIES + CATEGORIES[:1]
    radar = go.Figure()
    sector_median = cat_pct.loc[peers.index].median()
    for name, vals, color in [(ticker, cat_pct.loc[ticker], BLUE),
                              (f"{row['Sector']} median", sector_median, MUTED)]:
        r = vals.reindex(CATEGORIES).tolist()
        radar.add_trace(go.Scatterpolar(r=r + r[:1], theta=theta, name=name, fill="toself",
                                        line={"color": color, "width": 2}, opacity=0.75))
    radar.update_layout(title=f"{ticker} factor percentiles", template="simple_white",
                        polar={"radialaxis": {"range": [0, 100]}}, height=420)

    px = (prices if prices is not None else load_prices([ticker]))
    s = px[ticker].dropna().iloc[-252:] if ticker in px.columns else pd.Series(dtype=float)
    price_fig = go.Figure(go.Scatter(x=s.index, y=s, line={"color": BLUE, "width": 2}, name=ticker))
    price_fig.update_layout(title=f"{ticker} adjusted price, last 1Y", template="simple_white",
                            yaxis_title="Price", height=380, showlegend=False)
    return {"summary": row, "metrics": metrics, "text": text, "profile": "\n".join(lines),
            "radar": radar, "price": price_fig}


def show_report(report: dict) -> None:
    """Print the text profile and open the two figures."""
    print(report["profile"])
    report["radar"].show()
    report["price"].show()


def main(argv: Sequence[str] | None = None) -> int:
    args = cli.parse_args("Print a factor profile for one ticker.", argv, ticker=True)
    cli.setup_logging()
    try:
        show_report(stock_report(args.ticker.upper()))
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
