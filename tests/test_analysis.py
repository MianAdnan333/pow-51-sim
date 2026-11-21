import pytest
from matplotlib.axes import Axes

from pow51sim.analysis.plots import plot_success_curves, plot_success_heatmap
from pow51sim.analysis.tables import success_matrix
from pow51sim.analysis.theory import nakamoto_success_probability
from pow51sim.simulation.runner import sweep


@pytest.mark.parametrize(
    ("share", "confirmations", "expected"),
    [(0.1, 0, 1.0), (0.1, 5, 0.0009137), (0.3, 5, 0.1773523)],
)
def test_nakamoto_matches_published_values(share, confirmations, expected):
    assert nakamoto_success_probability(share, confirmations) == pytest.approx(
        expected, abs=1e-6
    )


def test_majority_attacker_always_succeeds():
    assert nakamoto_success_probability(0.6, 6) == 1.0


@pytest.fixture(scope="module")
def results():
    return sweep([0.1, 0.3], [1, 2], trials=20, reorg_limits=(None, 1))


def test_success_matrix_shape(results):
    matrix = success_matrix(results)
    assert matrix.shape == (2, 2)


def test_success_matrix_filters_by_limit(results):
    assert success_matrix(results, reorg_limit=1).shape == (2, 2)


def test_plots_return_axes(results):
    assert isinstance(plot_success_heatmap(results), Axes)
    assert isinstance(plot_success_curves(results), Axes)
