"""Pure view helpers: summaries, Plotly figures and HTML snippets for the dashboard."""

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from dashboard.engine import RaceTrace

RED = "#ff4d6d"
GREEN = "#2ee59d"
BLUE = "#3b82f6"
VIOLET = "#a78bfa"
AMBER = "#fbbf24"
CYAN = "#22d3ee"
TEXT = "#e8ecff"
GRID = "rgba(255,255,255,0.08)"
MAJORITY = 0.51

PAGE_CSS = """
<style>
:root {--card: rgba(255,255,255,0.045); --border: rgba(255,255,255,0.10);}
.stApp {background:
  radial-gradient(1100px 560px at 8% -10%, rgba(124,58,237,0.28), transparent 60%),
  radial-gradient(900px 480px at 100% 0%, rgba(236,72,153,0.20), transparent 55%),
  #0b1020;}
.block-container {padding-top: 2rem; max-width: 1280px;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #131839, #0d1230);
  border-right: 1px solid var(--border);}
[data-testid="stHeader"] {background: transparent;}
.hero {padding: 34px 38px; border-radius: 24px; margin-bottom: 22px;
  background: linear-gradient(120deg, #7c3aed, #ec4899, #f59e0b, #7c3aed);
  background-size: 300% 300%; animation: flow 16s ease infinite;
  box-shadow: 0 18px 50px rgba(124, 58, 237, 0.40);}
@keyframes flow {0% {background-position: 0% 50%;} 50% {background-position: 100% 50%;}
  100% {background-position: 0% 50%;}}
.hero h1 {margin: 0; color: #fff; font-size: 2.6rem; font-weight: 800;
  letter-spacing: -1px;}
.hero p {margin: 8px 0 0; color: rgba(255,255,255,0.92); font-size: 1.08rem;
  max-width: 760px;}
.hero .badges span {display: inline-block; margin: 16px 8px 0 0; padding: 5px 14px;
  border-radius: 999px; background: rgba(255,255,255,0.18); color: #fff;
  font-size: 0.78rem; font-weight: 600; backdrop-filter: blur(6px);
  border: 1px solid rgba(255,255,255,0.25);}
.kpi {padding: 18px 20px; border-radius: 20px; background: var(--card);
  border: 1px solid var(--border); backdrop-filter: blur(10px);
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;}
.kpi:hover {transform: translateY(-4px); border-color: var(--accent);
  box-shadow: 0 14px 34px color-mix(in srgb, var(--accent) 28%, transparent);}
.kpi .top {display: flex; align-items: center; justify-content: space-between;}
.kpi .icon {font-size: 1.35rem; width: 38px; height: 38px; border-radius: 12px;
  display: inline-flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--accent) 18%, transparent);}
.kpi .label {color: #aab3d9; font-size: 0.78rem; text-transform: uppercase;
  letter-spacing: 0.08em; font-weight: 600;}
.kpi .value {color: var(--accent); font-size: 2.2rem; font-weight: 800;
  margin-top: 8px; letter-spacing: -0.5px;}
.kpi .hint {color: #7f89b5; font-size: 0.8rem; margin-top: 2px;}
.insight {margin: 18px 0 6px; padding: 14px 18px; border-radius: 16px;
  background: linear-gradient(90deg, rgba(46,229,157,0.12), rgba(167,139,250,0.10));
  border: 1px solid rgba(46,229,157,0.30); color: #e8ecff; font-size: 0.98rem;}
.insight b {color: #2ee59d;}
.footer {margin-top: 28px; text-align: center; color: #6c76a3; font-size: 0.8rem;}
.stTabs [data-baseweb="tab-list"] {gap: 8px; background: transparent;}
.stTabs [data-baseweb="tab"] {border-radius: 999px; padding: 8px 20px;
  background: var(--card); border: 1px solid var(--border); height: auto;}
.stTabs [aria-selected="true"] {background: linear-gradient(90deg, #7c3aed, #ec4899);
  border-color: transparent;}
.stTabs [aria-selected="true"] p {color: #fff; font-weight: 700;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]
  {display: none;}
div[data-testid="stPlotlyChart"] {background: var(--card);
  border: 1px solid var(--border); border-radius: 20px; padding: 10px;}
div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden;}
.stDownloadButton button {border-radius: 999px; border: 1px solid var(--border);
  background: var(--card); transition: transform .15s ease;}
.stDownloadButton button:hover {transform: translateY(-2px); border-color: #a78bfa;}
.row {display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin: 8px 0;}
.row .label {width: 100%; color: #aab3d9; font-size: 0.85rem; font-weight: 600;}
.blk {width: 28px; height: 28px; border-radius: 8px; font-size: 0.65rem;
  display: inline-flex; align-items: center; justify-content: center; color: #fff;
  box-shadow: 0 3px 10px rgba(0,0,0,0.35); transition: transform .12s ease;}
.blk:hover {transform: scale(1.18);}
.blk.h {background: linear-gradient(135deg, #3b82f6, #60a5fa);}
.blk.p {background: linear-gradient(135deg, #ef4444, #fb7185);}
.blk.x {background: transparent; border: 2px dashed #ef4444; color: #ef4444;
  box-shadow: none;}
.banner {margin-top: 16px; padding: 16px 20px; border-radius: 16px; color: #08101f;
  font-weight: 800; font-size: 1.5rem; letter-spacing: 0.05em;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);}
.banner small {display: block; font-weight: 500; font-size: 0.85rem; margin-top: 3px;}
.banner.bad {background: linear-gradient(90deg, #ff4d6d, #ff8fa3);}
.banner.good {background: linear-gradient(90deg, #2ee59d, #8bf5c9);}
</style>
"""


@dataclass(frozen=True)
class Kpis:
    success_off: float
    success_on: float
    stopped_pp: float
    runtime_ms: float


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Per defense setting and attacker share aggregates of the per-trial rows."""
    data = results.assign(defense=results["scenario"] == "Defense ON")
    keys = ["defense", "attacker_share"]
    summary: pd.DataFrame = data.groupby(keys).agg(
        success_rate=("attack_success", "mean"),
        blocked_rate=("blocked_by_safe_mode", "mean"),
        mean_private_len=("private_len", "mean"),
        runtime_ms=("runtime_ms", "mean"),
    )
    depth = data[data["attack_success"]].groupby(keys)["reorg_depth"].mean()
    summary["mean_reorg_depth"] = depth.reindex(summary.index).fillna(0.0)
    flat: pd.DataFrame = summary.reset_index()
    return flat


def kpi_values(summary: pd.DataFrame, focus_share: float) -> Kpis:
    focus = summary[summary["attacker_share"].round(4) == round(focus_share, 4)]
    off = float(focus[~focus["defense"]]["success_rate"].iloc[0])
    on = float(focus[focus["defense"]]["success_rate"].iloc[0])
    return Kpis(off, on, (off - on) * 100, float(focus["runtime_ms"].mean()))


def hero_html() -> str:
    badges = ("Real simulator", "Seeded and reproducible", "LPC rule + Safe Mode")
    chips = "".join(f"<span>{badge}</span>" for badge in badges)
    return (
        '<div class="hero"><h1>pow-51-sim</h1>'
        "<p>51% attack lab: how often a private chain wins, and what the "
        "long-private-chain defense with Safe Mode stops.</p>"
        f'<div class="badges">{chips}</div></div>'
    )


def kpi_html(
    label: str, value: str, accent: str, hint: str = "", icon: str = ""
) -> str:
    return (
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="top"><div class="label">{label}</div>'
        f'<div class="icon">{icon}</div></div>'
        f'<div class="value">{value}</div><div class="hint">{hint}</div></div>'
    )


def insight_html(kpis: Kpis, focus_share: float) -> str:
    if kpis.stopped_pp < 0.05:
        verdict = "the defense makes <b>no measurable difference</b> here"
    else:
        verdict = (
            f"Safe Mode cuts double-spend success from <b>{kpis.success_off:.0%}</b> "
            f"to <b>{kpis.success_on:.0%}</b>, stopping <b>{kpis.stopped_pp:.0f}</b> "
            "in every 100 attacks"
        )
    return f'<div class="insight">💡 At {focus_share:.0%} hash share, {verdict}.</div>'


def footer_html() -> str:
    return (
        '<div class="footer">pow-51-sim · educational simulation · '
        "simplified PoW, no real network</div>"
    )


def success_figure(
    summary: pd.DataFrame, focus_share: float | None = None
) -> go.Figure:
    figure = go.Figure()
    for defense, name, color, fill in (
        (False, "Defense OFF", RED, None),
        (True, "Defense ON", GREEN, "rgba(46,229,157,0.14)"),
    ):
        rows = summary[summary["defense"] == defense]
        figure.add_trace(
            go.Scatter(
                x=rows["attacker_share"],
                y=rows["success_rate"],
                name=name,
                mode="lines+markers",
                line={"color": color, "width": 4, "shape": "spline", "smoothing": 0.6},
                marker={"size": 10, "line": {"width": 2, "color": "#0b1020"}},
                fill="tonexty" if fill else None,
                fillcolor=fill,
                hovertemplate="%{y:.1%}",
            )
        )
    shares = summary["attacker_share"]
    if shares.min() <= MAJORITY <= shares.max():
        figure.add_vline(
            x=MAJORITY,
            line={"dash": "dash", "color": AMBER},
            annotation_text="51% majority",
            annotation_font_color=AMBER,
        )
    if focus_share is not None:
        figure.add_vline(x=focus_share, line={"dash": "dot", "color": CYAN, "width": 2})
    return _style(figure, "Double-spend success vs attacker hash share", "Success rate")


def reorg_figure(summary: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    for defense, name, color in (
        (False, "Defense OFF", RED),
        (True, "Defense ON", GREEN),
    ):
        rows = summary[summary["defense"] == defense]
        figure.add_trace(
            go.Bar(
                x=rows["attacker_share"],
                y=rows["mean_reorg_depth"],
                name=name,
                marker={"color": color, "cornerradius": 8},
                hovertemplate="%{y:.1f} blocks",
            )
        )
    figure.update_layout(barmode="group", bargap=0.25)
    figure = _style(figure, "Reorg depth of successful attacks", "Blocks replaced")
    figure.update_yaxes(tickformat=None)
    return figure


def blocked_figure(summary: pd.DataFrame) -> go.Figure:
    rows = summary[summary["defense"]]
    figure = go.Figure(
        go.Scatter(
            x=rows["attacker_share"],
            y=rows["blocked_rate"],
            name="Blocked by Safe Mode",
            mode="lines",
            fill="tozeroy",
            line={"color": VIOLET, "width": 3},
            fillcolor="rgba(167,139,250,0.35)",
        )
    )
    return _style(figure, "Attacks blocked by Safe Mode", "Share of attacks blocked")


def false_positive_figure(
    curve: pd.DataFrame, limit: int, window: int, focus_share: float | None = None
) -> go.Figure:
    figure = go.Figure(
        go.Scatter(
            x=curve["hash_share"],
            y=curve["probability"],
            name="P(streak hits limit)",
            mode="lines",
            fill="tozeroy",
            line={"color": AMBER, "width": 3},
            fillcolor="rgba(251,191,36,0.25)",
        )
    )
    if focus_share is not None:
        figure.add_vline(x=focus_share, line={"dash": "dot", "color": CYAN})
    title = f"Honest miner mining {limit} blocks in a row within {window} blocks"
    return _style(figure, title, "Probability", "Honest miner's hash share")


def race_html(trace: RaceTrace) -> str:
    rejected = trace.private_blocks - trace.accepted_private_blocks
    private = _blocks("p", trace.accepted_private_blocks) + _blocks("x", rejected)
    verdict, tone = ("ACCEPTED", "bad") if trace.accepted else ("REJECTED", "good")
    return (
        f'<div class="row"><span class="label">Honest chain: '
        f"{trace.honest_blocks} blocks</span>{_blocks('h', trace.honest_blocks)}</div>"
        f'<div class="row"><span class="label">Private chain: '
        f"{trace.private_blocks} blocks</span>{private}</div>"
        f'<div class="banner {tone}">{verdict}<small>{trace.reason}</small></div>'
    )


def _blocks(kind: str, count: int) -> str:
    return "".join(f'<span class="blk {kind}">{i}</span>' for i in range(1, count + 1))


def _style(
    figure: go.Figure, title: str, y_label: str, x_label: str = "Attacker hash share"
) -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 17}},
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={
            "color": TEXT,
            "family": "system-ui, -apple-system, Segoe UI, sans-serif",
        },
        hovermode="x unified",
        hoverlabel={"bgcolor": "#141a33", "bordercolor": "rgba(255,255,255,0.2)"},
        legend={"orientation": "h", "y": 1.14, "bgcolor": "rgba(0,0,0,0)"},
        xaxis={
            "title": x_label,
            "tickformat": ".0%",
            "gridcolor": GRID,
            "zeroline": False,
        },
        yaxis={
            "title": y_label,
            "tickformat": ".0%",
            "gridcolor": GRID,
            "zeroline": False,
        },
        margin={"t": 90, "l": 50, "r": 24, "b": 50},
    )
    return figure
