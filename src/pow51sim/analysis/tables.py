from pathlib import Path

import pandas as pd

DEFENSE_LABELS = {False: "No defense", True: "Defense on"}


def success_matrix(
    results: pd.DataFrame, reorg_limit: int | None = None
) -> pd.DataFrame:
    if reorg_limit is None:
        subset = results[results["reorg_limit"].isna()]
    else:
        subset = results[results["reorg_limit"] == reorg_limit]
    matrix: pd.DataFrame = subset.pivot(
        index="confirmations", columns="attacker_share", values="success_rate"
    )
    return matrix


def prepare_results(results: pd.DataFrame) -> pd.DataFrame:
    """Unpack the `scenario` label and add numeric/derived columns for plotting."""
    frame: pd.DataFrame = results.copy()
    parts = frame["scenario"].str.extract(r"conf=(\d+),defense=(on|off)")
    frame["confirmations"] = parts[0].astype(int)
    frame["defense"] = parts[1] == "on"
    frame["defense_label"] = frame["defense"].map(DEFENSE_LABELS)
    frame["attack_success"] = frame["attack_success"].astype(float)
    if "total_blocks" in frame:
        frame["orphan_rate"] = frame["orphaned_blocks"] / frame["total_blocks"].where(
            frame["total_blocks"] > 0
        )
        mined = frame["attacker_blocks"] + frame["honest_blocks"]
        frame["attacker_block_share"] = frame["attacker_blocks"] / mined.where(
            mined > 0
        )
    return frame


def load_results(path: str | Path) -> pd.DataFrame:
    return prepare_results(pd.read_csv(path))


def overhead_table(results: pd.DataFrame) -> pd.DataFrame:
    """Median runtime/memory with and without the defense, per attacker share."""
    data = results if "defense" in results else prepare_results(results)
    medians = (
        data.groupby(["attacker_share", "defense"])[["runtime_ms", "memory_mb"]]
        .median()
        .unstack("defense")
    )
    table: pd.DataFrame = pd.DataFrame(index=medians.index)
    for metric, unit in (("runtime", "ms"), ("memory", "mb")):
        source = medians[f"{metric}_{unit}"]
        table[f"{metric}_off_{unit}"] = source[False]
        table[f"{metric}_on_{unit}"] = source[True]
        table[f"{metric}_overhead_pct"] = (source[True] / source[False] - 1) * 100
    return table
