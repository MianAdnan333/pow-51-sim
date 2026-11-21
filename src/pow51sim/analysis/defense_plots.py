import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

from pow51sim.analysis.style import (
    DEFENSE_ORDER,
    DEFENSE_PALETTE,
    MUTED,
    SERIES,
)
from pow51sim.analysis.tables import prepare_results
from pow51sim.analysis.theory import false_positive_rate

SHARE_LABEL = "Attacker hash share"


def _percent_axis(ax: Axes, axis: str = "x", decimals: int = 0) -> None:
    target = ax.xaxis if axis == "x" else ax.yaxis
    target.set_major_formatter(PercentFormatter(1.0, decimals=decimals))


def _defense_lines(ax: Axes, data: pd.DataFrame, y: str) -> None:
    sns.lineplot(
        data=data,
        x="attacker_share",
        y=y,
        hue="defense_label",
        hue_order=DEFENSE_ORDER,
        palette=DEFENSE_PALETTE,
        marker="o",
        markersize=6,
        errorbar=("ci", 95),
        ax=ax,
    )
    _percent_axis(ax)


def _remove_legend(ax: Axes) -> None:
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()


def _move_legend_to_figure(fig: Figure, ax: Axes, title: str | None = None) -> None:
    handles, labels = ax.get_legend_handles_labels()
    for panel in fig.axes:
        _remove_legend(panel)
    fig.legend(
        handles,
        labels,
        title=title,
        loc="outside lower center",
        ncol=len(labels),
    )


def plot_success_vs_share(results: pd.DataFrame) -> Figure:
    data = prepare_results(results) if "defense" not in results else results
    depths = sorted(data["confirmations"].unique())
    fig, axes = plt.subplots(
        1,
        len(depths),
        figsize=(4.4 * len(depths), 4.4),
        sharey=True,
        squeeze=False,
        layout="constrained",
    )
    for ax, depth in zip(axes[0], depths, strict=True):
        _defense_lines(ax, data[data["confirmations"] == depth], "attack_success")
        ax.set_title(f"{depth} confirmation{'s' if depth != 1 else ''}")
        ax.set_xlabel(SHARE_LABEL)
        ax.set_ylabel("")
        ax.set_ylim(0, 1.02)
        _percent_axis(ax, "y")
    axes[0][0].set_ylabel("Double-spend success rate")
    _move_legend_to_figure(fig, axes[0][0])
    fig.suptitle("Attack success rate vs attacker hash share")
    return fig


def plot_chain_structure(results: pd.DataFrame, threshold: int = 6) -> Figure:
    data = prepare_results(results) if "defense" not in results else results
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), layout="constrained")
    orphan_ax, share_ax, run_ax = axes

    _defense_lines(orphan_ax, data, "orphan_rate")
    orphan_ax.set_title("Orphaned blocks")
    orphan_ax.set_ylabel("Share of published blocks orphaned")
    _percent_axis(orphan_ax, "y")

    _defense_lines(share_ax, data, "attacker_block_share")
    share_ax.plot([0.1, 0.6], [0.1, 0.6], color=MUTED, linestyle="--", linewidth=1.2)
    share_ax.annotate(
        "fair share (= hash share)",
        xy=(0.6, 0.6),
        xytext=(-4, 8),
        textcoords="offset points",
        ha="right",
        color=MUTED,
    )
    share_ax.set_title("Who owns the final chain")
    share_ax.set_ylabel("Attacker share of final-chain blocks")
    _percent_axis(share_ax, "y")

    sns.boxplot(
        data=data,
        x="attacker_share",
        y="max_consecutive_by_one_miner",
        hue="defense_label",
        hue_order=DEFENSE_ORDER,
        palette=DEFENSE_PALETTE,
        width=0.7,
        linewidth=1,
        fliersize=2,
        ax=run_ax,
    )
    run_ax.axhline(threshold, color=MUTED, linestyle="--", linewidth=1.2)
    run_ax.annotate(
        f"defense threshold ({threshold})",
        xy=(0, threshold),
        xycoords=("axes fraction", "data"),
        xytext=(6, 5),
        textcoords="offset points",
        ha="left",
        color=MUTED,
    )
    run_ax.set_title("Longest streak by a single miner")
    run_ax.set_ylabel("Consecutive blocks")
    run_ax.set_xticks(
        run_ax.get_xticks(),
        [f"{float(t.get_text()):.0%}" for t in run_ax.get_xticklabels()],
    )

    for ax in (orphan_ax, share_ax, run_ax):
        ax.set_xlabel(SHARE_LABEL)
    _move_legend_to_figure(fig, orphan_ax)
    _remove_legend(run_ax)
    fig.suptitle("Final chain structure (all confirmation depths pooled)")
    return fig


def plot_defense_overhead(results: pd.DataFrame) -> Figure:
    data = prepare_results(results) if "defense" not in results else results
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    panels = (
        ("runtime_ms", "Median runtime per trial (ms)"),
        ("memory_mb", "Median peak memory per trial (MB)"),
    )
    for ax, (column, label) in zip(axes, panels, strict=True):
        sns.barplot(
            data=data,
            x="attacker_share",
            y=column,
            hue="defense_label",
            hue_order=DEFENSE_ORDER,
            palette=DEFENSE_PALETTE,
            estimator="median",
            errorbar=None,
            width=0.7,
            ax=ax,
        )
        ax.set_xlabel(SHARE_LABEL)
        ax.set_ylabel(label)
        ax.set_xticks(
            ax.get_xticks(),
            [f"{float(t.get_text()):.0%}" for t in ax.get_xticklabels()],
        )
    _move_legend_to_figure(fig, axes[0])
    _remove_legend(axes[1])
    fig.suptitle("Cost of running the defense (all confirmation depths pooled)")
    return fig


def plot_false_positives(false_positives: pd.DataFrame) -> Figure:
    thresholds = sorted(false_positives["threshold"].unique())
    palette = dict(zip(thresholds, SERIES, strict=False))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    rate_ax, trigger_ax = axes

    sns.lineplot(
        data=false_positives,
        x="miner_share",
        y="blocked_rate",
        hue="threshold",
        palette=palette,
        marker="o",
        markersize=6,
        errorbar=("ci", 95),
        ax=rate_ax,
    )
    shares = sorted(false_positives["miner_share"].unique())
    for threshold in thresholds:
        theory = [false_positive_rate(s, threshold) for s in shares]
        rate_ax.plot(
            shares, theory, color=palette[threshold], linestyle=":", linewidth=1.5
        )
    rate_ax.set_title("Honest blocks wrongly rejected")
    rate_ax.set_ylabel("Share of the miner's blocks rejected")
    _percent_axis(rate_ax, "y")

    triggered = (
        false_positives.groupby(["threshold", "miner_share"])["safe_mode_triggered"]
        .mean()
        .reset_index()
    )
    sns.lineplot(
        data=triggered,
        x="miner_share",
        y="safe_mode_triggered",
        hue="threshold",
        palette=palette,
        marker="o",
        markersize=6,
        ax=trigger_ax,
    )
    trigger_ax.set_title("Safe Mode triggered with no attacker present")
    trigger_ax.set_ylabel("Share of runs that enter Safe Mode")
    trigger_ax.set_ylim(0, 1.02)
    _percent_axis(trigger_ax, "y")

    for ax in axes:
        ax.set_xlabel("Honest miner's hash share")
        _percent_axis(ax)
    handles = [
        Line2D(
            [], [], color=palette[t], marker="o", markersize=6, label=f"threshold = {t}"
        )
        for t in thresholds
    ]
    handles.append(
        Line2D([], [], color=MUTED, linestyle=":", label="theory: share^(threshold-1)")
    )
    for ax in axes:
        _remove_legend(ax)
    fig.legend(handles=handles, loc="outside lower center", ncol=len(handles))
    fig.suptitle("False positives: large honest miners blocked by the run limit")
    return fig
