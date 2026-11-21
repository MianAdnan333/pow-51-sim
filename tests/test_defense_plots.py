import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.figure import Figure

from pow51sim.analysis.defense_plots import (
    plot_chain_structure,
    plot_defense_overhead,
    plot_false_positives,
    plot_success_vs_share,
)
from pow51sim.analysis.style import apply_style
from pow51sim.analysis.tables import load_results, overhead_table, prepare_results
from pow51sim.simulation.false_positives import FalsePositiveExperiment
from pow51sim.simulation.simulation_runner import ParameterGrid, SimulationRunner


@pytest.fixture(scope="module")
def results() -> pd.DataFrame:
    grid = ParameterGrid(attacker_shares=(0.2, 0.5), confirmations=(1, 3))
    return SimulationRunner(6, grid=grid, detailed=True).run()


@pytest.fixture(autouse=True)
def _close_figures():
    apply_style()
    yield
    plt.close("all")


def test_prepare_results_unpacks_scenario_and_derives_rates(results):
    data = prepare_results(results)
    assert set(data["confirmations"]) == {1, 3}
    assert set(data["defense_label"]) == {"No defense", "Defense on"}
    assert data["attack_success"].dtype == float
    assert data["orphan_rate"].dropna().between(0, 1).all()
    assert data["attacker_block_share"].dropna().between(0, 1).all()


def test_overhead_table_has_one_row_per_share(results):
    table = overhead_table(results)
    assert list(table.index) == [0.2, 0.5]
    assert {"runtime_overhead_pct", "memory_overhead_pct"} <= set(table.columns)


def test_load_results_round_trips_csv(results, tmp_path):
    path = tmp_path / "grid.csv"
    results.to_csv(path, index=False)
    assert len(load_results(path)) == len(results)


@pytest.mark.parametrize(
    "plot", [plot_success_vs_share, plot_chain_structure, plot_defense_overhead]
)
def test_attack_plots_return_figures(plot, results):
    assert isinstance(plot(results), Figure)


def test_success_plot_has_one_panel_per_confirmation_depth(results):
    assert len(plot_success_vs_share(results).axes) == 2


def test_false_positive_plot_returns_figure():
    frame = FalsePositiveExperiment(
        trials=2, shares=(0.2, 0.5), thresholds=(4, 6), rounds=200
    ).run()
    assert isinstance(plot_false_positives(frame), Figure)
