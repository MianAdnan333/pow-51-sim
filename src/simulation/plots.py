import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

OFF, ON = "Defense OFF", "Defense ON"
PALETTE = {OFF: "#d62f4f", ON: "#1f9d6b"}
ORDER = [OFF, ON]
MUTED = "#898781"
AMBER = "#d98e04"
SHARE_LABEL = "Attacker hash share"


def apply_style() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={"axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2},
    )


def _percent(ax: Axes, axis: str, decimals: int = 0) -> None:
    target = ax.xaxis if axis == "x" else ax.yaxis
    target.set_major_formatter(PercentFormatter(1.0, decimals=decimals))


def _line(ax: Axes, data: pd.DataFrame, y: str, legend: bool = False) -> None:
    sns.lineplot(
        data=data,
        x="attacker_share",
        y=y,
        hue="scenario",
        hue_order=ORDER,
        palette=PALETTE,
        marker="o",
        errorbar=("ci", 95),
        legend="auto" if legend else False,
        ax=ax,
    )
    _percent(ax, "x")
    ax.set_xlabel(SHARE_LABEL)


def _with_numeric_success(frame: pd.DataFrame) -> pd.DataFrame:
    data: pd.DataFrame = frame.copy()
    data["attack_success"] = data["attack_success"].astype(float)
    return data


def plot_success_vs_share(frame: pd.DataFrame) -> Figure:
    data = _with_numeric_success(frame)
    depths = sorted(data["confirmation_depth"].unique())
    fig, axes = plt.subplots(
        1, len(depths), figsize=(4.6 * len(depths), 4.4), sharey=True, squeeze=False
    )
    for index, (ax, depth) in enumerate(zip(axes[0], depths, strict=True)):
        _line(
            ax, data[data["confirmation_depth"] == depth], "attack_success", index == 0
        )
        ax.set_title(f"{depth} confirmation{'s' if depth != 1 else ''}")
        ax.set_ylabel("Double-spend success rate" if index == 0 else "")
        ax.set_ylim(0, 1.02)
        _percent(ax, "y")
    legend = axes[0][0].get_legend()
    if legend is not None:
        legend.set_title("")
    fig.suptitle("Attack success rate vs attacker hash share")
    fig.tight_layout()
    return fig


def plot_chain_structure(frame: pd.DataFrame, threshold: int = 6) -> Figure:
    """Needs a frame produced with `detailed=True`."""
    if "attacker_blocks" not in frame:
        raise ValueError("run the SimulationRunner with detailed=True")
    data: pd.DataFrame = frame.copy()
    mined = data["attacker_blocks"] + data["honest_blocks"]
    data["attacker_block_share"] = data["attacker_blocks"] / mined.where(mined > 0)
    fig, (orphan_ax, owner_ax, streak_ax) = plt.subplots(1, 3, figsize=(15, 4.4))

    _line(orphan_ax, data, "orphan_rate", legend=True)
    orphan_ax.set_title("Orphaned blocks")
    orphan_ax.set_ylabel("Share of published blocks orphaned")
    _percent(orphan_ax, "y")

    _line(owner_ax, data, "attacker_block_share")
    owner_ax.plot([0.1, 0.6], [0.1, 0.6], color=MUTED, linestyle="--", linewidth=1.2)
    owner_ax.annotate(
        "fair share",
        (0.6, 0.6),
        xytext=(-4, 8),
        textcoords="offset points",
        ha="right",
        color=MUTED,
    )
    owner_ax.set_title("Who owns the final chain")
    owner_ax.set_ylabel("Attacker share of final-chain blocks")
    _percent(owner_ax, "y")

    sns.boxplot(
        data=data,
        x="attacker_share",
        y="max_consecutive_by_one_miner",
        hue="scenario",
        hue_order=ORDER,
        palette=PALETTE,
        width=0.7,
        linewidth=1,
        fliersize=2,
        legend=False,
        ax=streak_ax,
    )
    streak_ax.axhline(threshold, color=MUTED, linestyle="--", linewidth=1.2)
    streak_ax.annotate(
        f"LPC limit ({threshold})",
        (0, threshold),
        xytext=(6, 5),
        textcoords="offset points",
        color=MUTED,
    )
    streak_ax.set_title("Longest streak by a single miner")
    streak_ax.set_ylabel("Consecutive blocks")
    streak_ax.set_xlabel(SHARE_LABEL)
    streak_ax.set_xticks(
        streak_ax.get_xticks(),
        [f"{float(t.get_text()):.0%}" for t in streak_ax.get_xticklabels()],
    )
    legend = orphan_ax.get_legend()
    if legend is not None:
        legend.set_title("")
    fig.suptitle("Final chain structure (all confirmation depths pooled)")
    fig.tight_layout()
    return fig


def plot_overhead(frame: pd.DataFrame) -> Figure:
    if frame["memory_mb"].isna().all():
        raise ValueError("memory was not measured; rerun with memory tracing on")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    panels = (
        ("runtime_ms", "Median runtime per trial (ms)"),
        ("memory_mb", "Median peak memory per trial (MB)"),
    )
    for index, (ax, (column, label)) in enumerate(zip(axes, panels, strict=True)):
        sns.barplot(
            data=frame,
            x="attacker_share",
            y=column,
            hue="scenario",
            hue_order=ORDER,
            palette=PALETTE,
            estimator="median",
            errorbar=None,
            width=0.7,
            legend="auto" if index == 0 else False,
            ax=ax,
        )
        ax.set_xlabel(SHARE_LABEL)
        ax.set_ylabel(label)
        ax.set_xticks(
            ax.get_xticks(),
            [f"{float(t.get_text()):.0%}" for t in ax.get_xticklabels()],
        )
    legend = axes[0].get_legend()
    if legend is not None:
        legend.set_title("")
    fig.suptitle("Cost of running the defense (all confirmation depths pooled)")
    fig.tight_layout()
    return fig


def plot_false_positives(frame: pd.DataFrame, threshold: int = 6) -> Figure:
    data: pd.DataFrame = frame.copy()
    data["flagged"] = data["flagged"].astype(float)
    fig, (run_ax, rate_ax) = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, column, title, label in (
        (
            run_ax,
            "flagged",
            "Runs with at least one flagged block",
            "Share of honest runs flagged",
        ),
        (
            rate_ax,
            "flagged_rate",
            "Honest blocks flagged",
            "Share of the miner's blocks flagged",
        ),
    ):
        sns.lineplot(
            data=data,
            x="miner_share",
            y=column,
            marker="o",
            color=AMBER,
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("Honest miner's hash share")
        ax.set_ylabel(label)
        ax.set_xticks(sorted(data["miner_share"].unique()))
        _percent(ax, "x")
        _percent(ax, "y", decimals=1 if column == "flagged_rate" else 0)
    fig.suptitle(f"False positives of the LPC rule (limit {threshold}, no attacker)")
    fig.tight_layout()
    return fig
