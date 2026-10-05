"""Static matplotlib charts saved to outputs/<universe>/charts/."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from src import config  # noqa: E402

log = logging.getLogger(__name__)

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
SPY_COLOR = MUTED
# Ordinal quintiles: blue (best) -> gray -> red (worst).
QUINTILE_COLORS = ["#1c5cab", "#86b6ef", "#a9a8a1", "#f0a09f", "#c42f2f"]
DIVERGING = LinearSegmentedColormap.from_list("rb", [RED, "#f0efec", BLUE])
CATEGORIES = ["Value", "Quality", "Momentum", "Growth", "LowVol"]


def _style() -> None:
    """Apply a clean, recessive chart style."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 9, "ytick.labelsize": 9,
        "font.family": "DejaVu Sans", "legend.frameon": False, "legend.fontsize": 9,
        "lines.linewidth": 1.6,
    })


def _save(fig: plt.Figure, name: str) -> Path:
    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CHARTS_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _label_ends(ax: plt.Axes, ends: dict[str, float], colors: dict[str, str]) -> None:
    """Direct-label line ends, nudged apart so labels don't collide."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.045
    x = ax.get_xlim()[1]
    placed: list[float] = []
    for name, y in sorted(ends.items(), key=lambda kv: kv[1]):
        if np.isnan(y):
            continue
        y = max(y, placed[-1] + gap) if placed else y
        placed.append(y)
        ax.annotate(name, (x, y), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=9, color=INK2, annotation_clip=False)
        ax.plot([x], [y], marker="s", ms=5, color=colors[name], clip_on=False)


def _pct_axis(ax: plt.Axes, axis: str = "y") -> None:
    fmt = matplotlib.ticker.PercentFormatter(1.0, decimals=0)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def plot_leaderboard(rank: pd.DataFrame, n: int = 20) -> Path:
    """Horizontal bar chart of the top-n composite scores."""
    top = rank.dropna(subset=["Composite"]).nlargest(n, "Composite").iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(top) + 1.2))
    ax.barh(top["Ticker"], top["Composite"], color=BLUE, height=0.7)
    for y, (v, sec) in enumerate(zip(top["Composite"], top["Sector"].fillna(""))):
        ax.text(v + 0.02, y, f"{v:.2f}  {sec}", va="center", fontsize=8, color=INK2)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(right=top["Composite"].max() * 1.45)
    ax.set_title(f"Top {len(top)} by composite score")
    ax.set_xlabel("Composite score (z)")
    return _save(fig, "01_leaderboard.png")


def plot_factor_heatmap(rank: pd.DataFrame, n: int = 20) -> Path:
    """Category z-scores for the top-n names (blue = strong, red = weak)."""
    top = rank.dropna(subset=["Composite"]).nlargest(n, "Composite").set_index("Ticker")
    data = top[CATEGORIES]
    lim = float(np.nanmax(np.abs(data.to_numpy()))) or 1.0
    fig, ax = plt.subplots(figsize=(6.5, 0.32 * len(data) + 1.5))
    im = ax.imshow(data.to_numpy(dtype=float), cmap=DIVERGING, vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(CATEGORIES)), CATEGORIES)
    ax.set_yticks(range(len(data)), data.index)
    ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    for (i, j), v in np.ndenumerate(data.to_numpy(dtype=float)):
        ax.text(j, i, "–" if np.isnan(v) else f"{v:.1f}", ha="center", va="center",
                fontsize=7.5, color=INK)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).outline.set_visible(False)
    ax.set_title("Factor scores, top names (z-score)")
    return _save(fig, "02_factor_heatmap.png")


def plot_quintile_cumulative(monthly: pd.DataFrame) -> Path:
    """Growth of $1 for each quintile (net of costs)."""
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ends, colors = {}, {}
    for i, c in enumerate(QUINTILE_COLORS, 1):
        cum = (1 + monthly[f"Q{i}_net"].fillna(0)).cumprod()
        ax.plot(cum.index, cum, color=c, label=f"Q{i}")
        ends[f"Q{i}"], colors[f"Q{i}"] = cum.iloc[-1], c
    _label_ends(ax, ends, colors)
    ax.legend(ncol=5, loc="upper left")
    ax.set_title("Quintile portfolios: growth of $1 (net, Q1 = best)")
    ax.set_ylabel("Growth of $1")
    return _save(fig, "03_quintile_cumulative.png")


def plot_strategy_vs_spy(monthly: pd.DataFrame) -> Path:
    """Q1 and long-short vs SPY: cumulative growth with drawdown panel."""
    series = {"Q1": (monthly["Q1_net"], BLUE), "Long-short": (monthly["LS_net"], ORANGE),
              "SPY": (monthly["SPY"], SPY_COLOR)}
    fig, (ax, dd) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True,
                                 gridspec_kw={"height_ratios": [2.3, 1], "hspace": 0.08})
    ends, colors = {}, {}
    for name, (r, c) in series.items():
        cum = (1 + r.fillna(0)).cumprod()
        ax.plot(cum.index, cum, color=c, label=name)
        dd.plot(cum.index, cum / cum.cummax() - 1, color=c, lw=1.2)
        ends[name], colors[name] = cum.iloc[-1], c
    _label_ends(ax, ends, colors)
    ax.legend(loc="upper left", ncol=3)
    ax.set_title("Strategy vs SPY (net of costs)")
    ax.set_ylabel("Growth of $1")
    dd.set_ylabel("Drawdown")
    _pct_axis(dd)
    return _save(fig, "04_strategy_vs_spy.png")


def plot_rolling_sharpe(monthly: pd.DataFrame, window: int = 12) -> Path:
    """Rolling annualized Sharpe ratio (rf = 0)."""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ends, colors = {}, {}
    for name, col, c in [("Q1", "Q1_net", BLUE), ("Long-short", "LS_net", ORANGE),
                         ("SPY", "SPY", SPY_COLOR)]:
        r = monthly[col]
        sh = r.rolling(window).mean() / r.rolling(window).std() * np.sqrt(12)
        ax.plot(sh.index, sh, color=c, label=name)
        ends[name], colors[name] = sh.dropna().iloc[-1] if sh.notna().any() else np.nan, c
    ax.axhline(0, color=AXIS, lw=0.8)
    _label_ends(ax, ends, colors)
    ax.legend(loc="upper left", ncol=3)
    ax.set_title(f"Rolling {window}-month Sharpe ratio")
    return _save(fig, "05_rolling_sharpe.png")


def plot_rank_ic(ic: pd.Series) -> Path:
    """Monthly rank IC bars with the full-period mean."""
    ic = ic.dropna()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(ic.index, ic, width=20, color=np.where(ic >= 0, BLUE, RED))
    ax.axhline(0, color=AXIS, lw=0.8)
    m = ic.mean()
    ax.axhline(m, color=INK, lw=1.2, ls="--")
    ax.annotate(f"mean IC {m:+.3f}", (ic.index[-1], m), xytext=(6, 4),
                textcoords="offset points", fontsize=9, color=INK2, annotation_clip=False)
    ax.set_title("Monthly rank IC (composite vs next-month return)")
    ax.set_ylabel("Spearman IC")
    return _save(fig, "06_rank_ic.png")


def plot_sector_exposure(rank: pd.DataFrame) -> Path:
    """Sector weights of current Q1 vs the equal-weight universe."""
    uni = rank["Sector"].fillna("Unknown").value_counts(normalize=True)
    q1 = rank.loc[rank["Quintile"] == 1, "Sector"].fillna("Unknown").value_counts(normalize=True)
    df = pd.DataFrame({"Q1": q1, "Universe": uni}).fillna(0).sort_values("Universe")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(df) + 1.4))
    ax.barh(y + 0.19, df["Q1"], height=0.36, color=BLUE, label="Q1")
    ax.barh(y - 0.19, df["Universe"], height=0.36, color=AXIS, label="Universe")
    ax.set_yticks(y, df.index)
    ax.grid(axis="y", visible=False)
    _pct_axis(ax, "x")
    ax.legend(loc="lower right")
    ax.set_title("Sector exposure: Q1 vs universe (equal weight)")
    return _save(fig, "07_sector_exposure.png")


def make_all(rank: pd.DataFrame | None = None, monthly: pd.DataFrame | None = None) -> list[Path]:
    """Render every chart from the saved rankings and backtest CSVs."""
    _style()
    if rank is None:
        rank = pd.read_csv(config.RANKINGS_DIR / "rankings.csv")
    if monthly is None:
        monthly = pd.read_csv(config.OUTPUTS_DIR / "backtest_monthly_returns.csv",
                              index_col=0, parse_dates=True)
    jobs = [(plot_leaderboard, rank), (plot_factor_heatmap, rank),
            (plot_quintile_cumulative, monthly), (plot_strategy_vs_spy, monthly),
            (plot_rolling_sharpe, monthly), (plot_rank_ic, monthly["IC"]),
            (plot_sector_exposure, rank)]
    paths = []
    for fn, data in jobs:
        try:
            paths.append(fn(data))
        except Exception as e:  # noqa: BLE001
            log.warning("chart %s failed: %s", fn.__name__, e)
    log.info("saved %d charts -> %s", len(paths), config.CHARTS_DIR)
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    make_all()
