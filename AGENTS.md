# pow-51-sim

Simulation of a **51% double-spend attack** on a proof-of-work chain.

## Layout

```
src/pow51sim/
  core/        Transaction, Block, ProofOfWork, UTXOSet (follows reorgs via ChainListener),
               Blockchain (block tree, longest chain),
               ConsensusRule + built-in rules (integrity, linkage, timestamp, PoW, UTXO)
  miners/      Miner (ABC), HonestMiner, MaliciousMiner (private fork), BlockReceiver, winner selection
  defense/     MaxReorgDepthRule, LongPrivateChainRule (+ Safe Mode) as ConsensusRules,
               build_rules, confirmation check,
               ChainComparator (flags conflicting spends between two chains)
  simulation/  Network (discrete-event, seedable), latency models, build_network,
               AttackConfig, AttackScenario (UTXO double-spend race), sweep (aggregated),
               SimulationRunner (per-trial grid -> DataFrame/CSV),
               FalsePositiveExperiment (honest-only network vs the run limit)
  analysis/    tables, plots (defense_plots.py + style.py), Nakamoto and
               false-positive closed forms, chain metrics
tests/         mirrors src/ one test module per unit
notebooks/     analysis only; no logic lives here (plots and tables come from analysis/)
               defense_evaluation.ipynb needs `pip install -e ".[notebook]"`
```

## Commands

1. Setup: `pip install -r requirements.txt && pip install -e ".[dev]"`
2. Hooks: `pre-commit install`
3. Lint: `ruff check . && black --check . && mypy src`
4. Test with the 80% coverage gate: `pytest --cov` (end-to-end tests: `pytest -m integration`)

## Conventions

1. **Dependencies point inward**: `core` knows nothing else; `simulation` composes everything.
2. **Inject randomness** (`Chooser`) so tests can script outcomes.
3. **New validation or defenses** implement `ConsensusRule` and are passed to `Blockchain(rules=...)`; no engine changes.
4. Keep comments minimal; prefer clear names.
5. Every new unit gets a test in `tests/`. CI runs ruff, black, mypy, pytest.
