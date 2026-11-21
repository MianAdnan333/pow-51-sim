"""Regenerate the README figures from the simulation CSVs (created if missing)."""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")

from pow51sim.analysis.defense_plots import (  # noqa: E402
    plot_chain_structure,
    plot_defense_overhead,
    plot_false_positives,
    plot_success_vs_share,
)
from pow51sim.analysis.style import apply_style  # noqa: E402
from pow51sim.analysis.tables import load_results  # noqa: E402
from pow51sim.simulation.false_positives import FalsePositiveExperiment  # noqa: E402
from pow51sim.simulation.simulation_runner import SimulationRunner  # noqa: E402

SEED = 42
ATTACK_TRIALS = 200
FALSE_POSITIVE_TRIALS = 50


def main(
    results_dir: Path = Path("results"), out_dir: Path = Path("docs/images")
) -> None:
    grid_csv = results_dir / "grid_detailed.csv"
    fp_csv = results_dir / "false_positives.csv"
    if not grid_csv.exists():
        SimulationRunner(ATTACK_TRIALS, seed=SEED, detailed=True).run_to_csv(grid_csv)
    if not fp_csv.exists():
        FalsePositiveExperiment(FALSE_POSITIVE_TRIALS, seed=SEED).run_to_csv(fp_csv)

    apply_style()
    results = load_results(grid_csv)
    false_positives = pd.read_csv(fp_csv)
    figures = {
        "success_vs_share": plot_success_vs_share(results),
        "chain_structure": plot_chain_structure(results),
        "defense_overhead": plot_defense_overhead(results),
        "false_positives": plot_false_positives(false_positives),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, figure in figures.items():
        figure.savefig(out_dir / f"{name}.png", dpi=110)
        print(f"wrote {out_dir / name}.png")


if __name__ == "__main__":
    main()
