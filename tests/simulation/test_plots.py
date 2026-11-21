import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from simulation.false_positives import FalsePositiveExperiment  # noqa: E402
from simulation.plots import (  # noqa: E402
    apply_style,
    plot_chain_structure,
    plot_false_positives,
    plot_overhead,
    plot_success_vs_share,
)
from simulation.runner import SimulationRunner  # noqa: E402


@pytest.fixture(scope="module")
def results():
    runner = SimulationRunner(
        shares=(0.2, 0.5), depths=(1, 3), trials=6, detailed=True, measure_memory=True
    )
    return runner.run()


@pytest.fixture(autouse=True)
def _style_and_close():
    apply_style()
    yield
    plt.close("all")


def test_attack_plots_return_figures(results):
    for plot in (plot_success_vs_share, plot_chain_structure, plot_overhead):
        assert isinstance(plot(results), Figure)


def test_success_plot_has_one_panel_per_depth(results):
    assert len(plot_success_vs_share(results).axes) == 2


def test_chain_structure_needs_the_detailed_columns(results):
    plain = results.drop(
        columns=["attacker_blocks", "honest_blocks", "top_honest_blocks"]
    )
    with pytest.raises(ValueError):
        plot_chain_structure(plain)


def test_overhead_plot_needs_memory_measurements(results):
    unmeasured = results.assign(memory_mb=float("nan"))
    with pytest.raises(ValueError):
        plot_overhead(unmeasured)


def test_false_positive_plot_returns_a_figure():
    frame = FalsePositiveExperiment(shares=(0.3, 0.45), trials=5).run()
    assert isinstance(plot_false_positives(frame), Figure)
