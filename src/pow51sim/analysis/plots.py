import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes

from pow51sim.analysis.tables import success_matrix


def plot_success_heatmap(
    results: pd.DataFrame, reorg_limit: int | None = None, ax: Axes | None = None
) -> Axes:
    ax = ax or plt.subplots()[1]
    sns.heatmap(
        success_matrix(results, reorg_limit),
        annot=True,
        fmt=".2f",
        vmin=0,
        vmax=1,
        cmap="viridis",
        ax=ax,
    )
    ax.set_title("Double-spend success rate")
    return ax


def plot_success_curves(results: pd.DataFrame, ax: Axes | None = None) -> Axes:
    ax = ax or plt.subplots()[1]
    sns.lineplot(
        data=results,
        x="attacker_share",
        y="success_rate",
        hue="confirmations",
        marker="o",
        ax=ax,
    )
    ax.set_ylim(0, 1)
    return ax
