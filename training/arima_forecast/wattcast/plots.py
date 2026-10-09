"""Charts for the notebook (matplotlib), in the project's chart style: thin marks, recessive axes,
a legend plus direct labels for two series, and usage levels as one blue scale, light to dark.
Colors were checked with the dataviz palette validator (categorical: CVD and contrast; levels: ordinal)."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

SURFACE = "#fcfcfb"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834"]                         # categorical slots 1-2
LEVEL_COLORS = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # idle, light, moderate, heavy
NOT_MEASURED = "#f0efec"
HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21]


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "legend.frameon": False, "lines.linewidth": 2, "font.family": "sans-serif",
    })


def _hour_label(h):
    return f"{(h % 12) or 12}{'a' if h < 12 else 'p'}"


def _hours_axis(ax):
    ax.set_xticks(HOUR_TICKS, [_hour_label(h) for h in HOUR_TICKS])
    ax.set_xlim(-0.5, 23.5)


def weekday_weekend(profile, title, unit):
    """Average by hour of day, weekdays vs weekends (patterns.hour_profile rows)."""
    style()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    hours = [p["hour"] for p in profile]
    for (key, label), color in zip((("weekday", "Weekdays"), ("weekend", "Weekends")), SERIES):
        values = [np.nan if p[key] is None else p[key] for p in profile]
        ax.plot(hours, values, color=color, label=label)
        last = next((i for i in range(23, -1, -1) if not np.isnan(values[i])), None)
        if last is not None:
            ax.annotate(label, (hours[last], values[last]), xytext=(6, 0), textcoords="offset points",
                        color=INK_2, va="center", fontsize=9)
    _hours_axis(ax)
    ax.set_ylabel(unit)
    ax.set_ylim(bottom=0)
    ax.set_title(title)
    ax.legend(loc="upper left", ncols=2)
    fig.tight_layout()
    return fig


def usage_heatmap(level, title="Usage level by hour"):
    """One row per day, one cell per hour, colored by usage level; white-gray where not measured."""
    style()
    days = sorted(set(level.index.date))
    codes = {name: i for i, name in enumerate(("idle", "light", "moderate", "heavy"))}
    grid = np.full((len(days), 24), np.nan)
    row = {d: i for i, d in enumerate(days)}
    for t, name in level.dropna().items():
        grid[row[t.date()], t.hour] = codes[name]
    fig, ax = plt.subplots(figsize=(9, max(2.2, 0.28 * len(days) + 1.2)))
    cmap = ListedColormap(LEVEL_COLORS)
    cmap.set_bad(NOT_MEASURED)
    ax.pcolormesh(np.ma.masked_invalid(grid), cmap=cmap, vmin=-0.5, vmax=3.5, edgecolors=SURFACE, linewidth=1.5)
    ax.set_xticks([h + 0.5 for h in HOUR_TICKS], [_hour_label(h) for h in HOUR_TICKS])
    step = max(1, len(days) // 12)
    ax.set_yticks([i + 0.5 for i in range(0, len(days), step)], [f"{days[i]:%a %b %d}" for i in range(0, len(days), step)])
    ax.invert_yaxis()
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title(title)
    handles = [Patch(color=c, label=n) for n, c in zip(codes, LEVEL_COLORS)] + [
        Patch(facecolor=NOT_MEASURED, edgecolor=AXIS, label="not measured")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.08), ncols=5, fontsize=9)
    fig.tight_layout()
    return fig


def backtest_bars(rows, title="Held-out error (MASE, lower is better)"):
    """rows: [(label, mase, is_baseline)]. Dashed line at 1 = as good as 'same hour yesterday' in training."""
    style()
    rows = [r for r in rows if r[1] is not None]
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.4))
    y = np.arange(len(rows))
    colors = [SERIES[1] if base else SERIES[0] for _, _, base in rows]
    ax.barh(y, [r[1] for r in rows], color=colors, height=0.6, edgecolor=SURFACE, linewidth=2)
    for i, (_, v, _) in enumerate(rows):
        ax.annotate(f"{v:.2f}", (v, i), xytext=(4, 0), textcoords="offset points", va="center", color=INK_2, fontsize=9)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.invert_yaxis()
    ax.axvline(1, color=MUTED, linestyle="--", linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.legend(handles=[Patch(color=SERIES[0], label="ARIMA"), Patch(color=SERIES[1], label="baseline")],
              loc="lower right")
    fig.tight_layout()
    return fig


def forecast_cost(hourly, hours=72, title="Extra bill from AI, per hour"):
    """Median pesos per hour with its 80% range, over the first `hours` forecast hours."""
    style()
    h = hourly.iloc[:hours]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.fill_between(h.index, h["cost_low"], h["cost_high"], color=SERIES[0], alpha=0.18, linewidth=0,
                    label="80% range")
    ax.plot(h.index, h["cost"], color=SERIES[0], label="median")
    ax.set_ylabel("PHP per hour")
    ax.set_ylim(bottom=0)
    ax.set_title(title)
    ax.legend(loc="upper left", ncols=2)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def agent_profiles(agents, title="When each AI agent is used: average power by hour of day"):
    """One small panel per agent (patterns.study_agents rows), weekdays vs weekends. Each panel has
    its own scale, since a local model draws many times what a cloud agent's client does."""
    style()
    cols = 2 if len(agents) > 1 else 1
    rows = -(-len(agents) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(9, 2.6 * rows + 0.6), squeeze=False)
    hours = list(range(24))
    for ax, agent in zip(axes.flat, agents):
        for (key, label), color in zip((("weekday", "Weekdays"), ("weekend", "Weekends")), SERIES):
            ax.plot(hours, [np.nan if p[key] is None else p[key] for p in agent["profile"]], color=color, label=label)
        _hours_axis(ax)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("W")
        share = "" if agent["share_of_energy"] is None else f"  ({agent['share_of_energy']:.0%} of AI energy)"
        ax.set_title(f"{agent['agent']}{share}", fontsize=10)
    for ax in axes.flat[len(agents):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncols=2)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def cost_by_agent(costs, title="AI cost forecast for the rest of the billing cycle, by agent (PHP)"):
    """costs: {agent: pesos}. One hue: the bars are one measure, and the labels name the agents."""
    style()
    items = sorted(costs.items(), key=lambda kv: kv[1], reverse=True)
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(items) + 1.2))
    y = np.arange(len(items))
    ax.barh(y, [v for _, v in items], color=SERIES[0], height=0.6, edgecolor=SURFACE, linewidth=2)
    for i, (_, v) in enumerate(items):
        ax.annotate(f"P{v:,.2f}", (v, i), xytext=(4, 0), textcoords="offset points", va="center", color=INK_2, fontsize=9)
    ax.set_yticks(y, [k for k, _ in items])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.12)
    ax.set_title(title)
    fig.tight_layout()
    return fig
