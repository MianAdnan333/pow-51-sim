from functools import cache

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import views
from dashboard.engine import (
    SimParams,
    honest_limit_probability,
    race_trace,
    run_grid,
)

PARAMS = SimParams(trials=40, confirmations=3, seed=5)


@cache
def _summary(shares=(0.2, 0.45, 0.6)):
    frames = [run_grid(shares, PARAMS, defense) for defense in (False, True)]
    return views.summarize(pd.concat(frames, ignore_index=True))


def test_summary_has_one_row_per_defense_and_share():
    summary = _summary()
    assert len(summary) == 6
    assert {"success_rate", "blocked_rate", "mean_reorg_depth"} <= set(summary.columns)
    assert summary["success_rate"].between(0, 1).all()
    assert (summary[~summary["defense"]]["blocked_rate"] == 0).all()


def test_kpis_match_the_summary():
    summary = _summary()
    kpis = views.kpi_values(summary, 0.45)
    rows = summary[summary["attacker_share"] == 0.45]
    assert kpis.success_off == pytest.approx(
        rows[~rows["defense"]]["success_rate"].iloc[0]
    )
    assert kpis.stopped_pp == pytest.approx((kpis.success_off - kpis.success_on) * 100)
    assert kpis.stopped_pp >= 0
    assert kpis.runtime_ms > 0


def test_success_figure_uses_red_for_off_and_green_for_on():
    figure = views.success_figure(_summary())
    colors = {trace.name: trace.line.color for trace in figure.data}
    assert colors == {"Defense OFF": views.RED, "Defense ON": views.GREEN}


def test_majority_marker_only_when_in_range():
    inside = views.success_figure(_summary((0.4, 0.6)))
    outside = views.success_figure(_summary((0.1, 0.3)))
    assert len(inside.layout.shapes) == 1
    assert inside.layout.shapes[0].x0 == views.MAJORITY
    assert len(outside.layout.shapes) == 0


def test_other_figures_are_plotly_figures():
    summary = _summary()
    curve = honest_limit_probability([0.1, 0.5], 6)
    figures = [
        views.reorg_figure(summary),
        views.blocked_figure(summary),
        views.false_positive_figure(curve, 6, 144, focus_share=0.5),
        views.false_positive_figure(curve, 6, 144),
    ]
    assert all(isinstance(figure, go.Figure) for figure in figures)
    assert len(figures[0].data) == 2
    assert figures[1].data[0].fill == "tozeroy"


def test_race_html_shows_the_verdict_and_both_chains():
    won = next(
        t for s in range(300) if (t := race_trace(0.55, PARAMS, False, s)).accepted
    )
    html = views.race_html(won)
    assert "ACCEPTED" in html
    assert html.count('class="blk h"') == won.honest_blocks
    assert html.count('class="blk p"') == won.private_blocks


def test_race_html_marks_rejected_blocks_when_safe_mode_blocks():
    blocked = next(
        t
        for s in range(300)
        if (t := race_trace(0.55, PARAMS, True, s)).blocked_by_safe_mode
    )
    html = views.race_html(blocked)
    assert "REJECTED" in html
    assert 'class="blk x"' in html


def test_focus_marker_is_added_when_requested():
    summary = _summary((0.4, 0.6))
    plain = views.success_figure(summary)
    marked = views.success_figure(summary, focus_share=0.5)
    assert len(marked.layout.shapes) == len(plain.layout.shapes) + 1


def test_the_defense_band_is_filled_between_the_two_lines():
    figure = views.success_figure(_summary())
    on = next(trace for trace in figure.data if trace.name == "Defense ON")
    assert on.fill == "tonexty"


def test_insight_states_the_numbers_or_admits_no_difference():
    gain = views.insight_html(views.Kpis(0.9, 0.6, 30.0, 1.0), 0.5)
    assert "90%" in gain
    assert "60%" in gain
    assert "30" in gain
    none = views.insight_html(views.Kpis(0.1, 0.1, 0.0, 1.0), 0.2)
    assert "no measurable difference" in none


def test_kpi_card_shows_its_icon():
    assert "🎯" in views.kpi_html("Label", "1", views.RED, "hint", "🎯")


def test_html_helpers_render_text():
    assert "pow-51-sim" in views.hero_html()
    card = views.kpi_html("Label", "42%", views.RED, "hint")
    assert "Label" in card
    assert "42%" in card
    assert views.RED in card
