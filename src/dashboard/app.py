from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import views
from dashboard.engine import (
    FALSE_POSITIVE_WINDOW,
    SimParams,
    honest_limit_probability,
    race_trace,
    run_grid,
)

DEFAULT_FOCUS = 0.45


@dataclass(frozen=True)
class Controls:
    shares: tuple[float, ...]
    params: SimParams
    focus_share: float


@st.cache_data(show_spinner="Simulating...")
def load_results(shares: tuple[float, ...], params: SimParams) -> pd.DataFrame:
    frames = [run_grid(shares, params, defense) for defense in (False, True)]
    results: pd.DataFrame = pd.concat(frames, ignore_index=True)
    return results


def sidebar() -> Controls:
    st.sidebar.header("Simulation")
    low, high = st.sidebar.slider(
        "Attacker hash share range", 5, 70, (10, 60), step=5, format="%d%%"
    )
    shares = tuple(pct / 100 for pct in range(low, high + 1, 5))
    params = SimParams(
        trials=st.sidebar.slider("Trials per point", 100, 2000, 100, step=100),
        confirmations=st.sidebar.slider("Confirmation depth", 0, 12, 3),
        lpc_limit=int(st.sidebar.number_input("LPC limit", 2, 50, 6)),
        seed=int(st.sidebar.number_input("Seed", 0, 2**31 - 1, 42)),
    )
    return Controls(shares, params, _pick_focus(shares))


def _pick_focus(shares: tuple[float, ...]) -> float:
    if len(shares) == 1:
        return shares[0]
    default = min(shares, key=lambda share: abs(share - DEFAULT_FOCUS))
    return st.sidebar.select_slider(
        "Focus share (KPI cards)",
        options=list(shares),
        value=default,
        format_func=lambda share: f"{share:.0%}",
    )


def show(figure: go.Figure) -> None:
    st.plotly_chart(figure, width="stretch")


def render_kpis(summary: pd.DataFrame, focus_share: float) -> None:
    kpis = views.kpi_values(summary, focus_share)
    where = f"at {focus_share:.0%} hash share"
    cards = (
        ("Success without defense", f"{kpis.success_off:.1%}", views.RED, where, "🔓"),
        ("Success with Safe Mode", f"{kpis.success_on:.1%}", views.GREEN, where, "🛡️"),
        (
            "Attacks stopped",
            f"{kpis.stopped_pp:.1f} pp",
            views.VIOLET,
            "percentage points",
            "🎯",
        ),
        (
            "Avg runtime / trial",
            f"{kpis.runtime_ms:.3f} ms",
            views.CYAN,
            "amortized",
            "⚡",
        ),
    )
    for column, (label, value, accent, hint, icon) in zip(
        st.columns(4), cards, strict=True
    ):
        column.markdown(
            views.kpi_html(label, value, accent, hint, icon), unsafe_allow_html=True
        )
    st.markdown(views.insight_html(kpis, focus_share), unsafe_allow_html=True)


def tab_success(summary: pd.DataFrame, focus_share: float) -> None:
    show(views.success_figure(summary, focus_share))
    left, right = st.columns(2)
    with left:
        show(views.reorg_figure(summary))
    with right:
        show(views.blocked_figure(summary))


def tab_race(controls: Controls) -> None:
    seed = int(st.number_input("Replay seed", 0, 2**31 - 1, controls.params.seed))
    st.caption(
        f"One attack at {controls.focus_share:.0%} hash share, same blocks both times."
    )
    for column, defense in zip(st.columns(2), (False, True), strict=True):
        trace = race_trace(controls.focus_share, controls.params, defense, seed)
        column.subheader("Defense ON" if defense else "Defense OFF")
        column.markdown(views.race_html(trace), unsafe_allow_html=True)


def tab_false_positives(controls: Controls) -> None:
    limit = controls.params.lpc_limit
    low, high = min(controls.shares), max(controls.shares)
    fine = [round(low + step / 100, 2) for step in range(round((high - low) * 100) + 1)]
    curve = honest_limit_probability(fine, limit, FALSE_POSITIVE_WINDOW)
    show(
        views.false_positive_figure(
            curve, limit, FALSE_POSITIVE_WINDOW, controls.focus_share
        )
    )
    st.caption("Dotted line marks the focus share. Exact calculation, no sampling.")


def tab_data(results: pd.DataFrame, summary: pd.DataFrame) -> None:
    st.dataframe(summary, width="stretch", hide_index=True)
    left, right = st.columns(2)
    left.download_button(
        "Download summary CSV", summary.to_csv(index=False), "summary.csv", "text/csv"
    )
    right.download_button(
        "Download raw trials CSV", results.to_csv(index=False), "trials.csv", "text/csv"
    )


def main() -> None:
    st.set_page_config(page_title="pow-51-sim", page_icon="⛓️", layout="wide")
    st.markdown(views.PAGE_CSS, unsafe_allow_html=True)
    controls = sidebar()
    st.markdown(views.hero_html(), unsafe_allow_html=True)
    results = load_results(controls.shares, controls.params)
    summary = views.summarize(results)
    render_kpis(summary, controls.focus_share)
    success, race, false_positives, data = st.tabs(
        ["Success Rate", "Chain Race", "False Positives", "Raw Data"]
    )
    with success:
        tab_success(summary, controls.focus_share)
    with race:
        tab_race(controls)
    with false_positives:
        tab_false_positives(controls)
    with data:
        tab_data(results, summary)
    st.markdown(views.footer_html(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
