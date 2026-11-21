from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py"

pytestmark = pytest.mark.integration


def _fresh_app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=120)


def _narrow(app: AppTest, low: int, high: int) -> None:
    share_range = next(s for s in app.sidebar.slider if "range" in s.label)
    share_range.set_range(low, high)


@pytest.fixture(scope="module")
def app() -> AppTest:
    return _fresh_app().run()


def test_app_renders_without_errors(app):
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Success Rate",
        "Chain Race",
        "False Positives",
        "Raw Data",
    ]


def test_kpi_cards_are_rendered(app):
    page = " ".join(markdown.value for markdown in app.markdown)
    for label in (
        "Success without defense",
        "Success with Safe Mode",
        "Attacks stopped",
        "Avg runtime / trial",
    ):
        assert label in page


def test_chain_race_shows_both_verdicts(app):
    page = " ".join(markdown.value for markdown in app.markdown)
    assert page.count("ACCEPTED") + page.count("REJECTED") == 2


def test_changing_seed_and_depth_reruns_cleanly():
    page = _fresh_app().run()
    _narrow(page, 30, 40)
    seed = next(box for box in page.sidebar.number_input if box.label == "Seed")
    seed.set_value(7)
    page.run()
    depth = next(s for s in page.sidebar.slider if s.label == "Confirmation depth")
    depth.set_value(5)
    page.run()
    assert not page.exception


def test_single_share_range_still_works():
    page = _fresh_app().run()
    _narrow(page, 30, 30)
    page.run()
    assert not page.exception
