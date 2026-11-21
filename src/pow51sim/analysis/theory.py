from math import exp, factorial


def false_positive_rate(share: float, threshold: int) -> float:
    """Long-run fraction of a lone honest miner's blocks rejected by the run limit.

    Once its streak reaches threshold-1, every further win is rejected until someone
    else mines, which gives a stationary rejection rate of share^(threshold-1).
    """
    return share ** (threshold - 1)


def nakamoto_success_probability(share: float, confirmations: int) -> float:
    honest = 1.0 - share
    if share >= honest:
        return 1.0
    ratio = share / honest
    lam = confirmations * ratio
    caught_up = sum(
        exp(-lam) * lam**k / factorial(k) * (1 - ratio ** (confirmations - k))
        for k in range(confirmations + 1)
    )
    return 1.0 - caught_up
