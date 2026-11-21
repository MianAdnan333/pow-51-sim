# pow-51-sim

Simulation of a **51% double-spend attack** on a proof-of-work chain and of the
long-private-chain (LPC) defense with Safe Mode.

## Layout

```
src/core/        Transaction, Block, Blockchain (block tree, longest chain, on_reorg /
                 on_extend hooks), ConsensusRule + BasicRule, pow (test-only hash loop)
src/miners/      Miner (ABC), HonestMiner, MaliciousMiner (private-chain building
                 blocks only), Network (seeded discrete-event simulation)
src/defense/     UTXOSet, ChainComparator, LongPrivateChainRule + SafeModeStats
src/simulation/  attack (AttackScenario, make_scenario), runner (grid -> CSV, CLI),
                 false_positives, plots, seeding
src/dashboard/   Streamlit app: engine.py (run_grid on the real runner), model.py (fast
                 replay + exact curves), views.py (figures/HTML), app.py (wiring)
src/pow51sim/    earlier standalone iteration; not used by the pipeline above
tests/           mirrors src/ (tests/core, miners, defense, simulation, dashboard tests)
notebooks/       analysis.ipynb (current); others belong to pow51sim
scripts/         generate_figures.py, run_demo.py (pow51sim)
```

## Commands

1. Setup: `pip install -r requirements.txt && pip install -e ".[dev,notebook]"`
2. Hooks: `pre-commit install`
3. Lint: `ruff check . && black --check . && mypy src`
4. Test with the 80% coverage gate: `pytest --cov` (end-to-end only: `pytest -m integration`)
5. Grid: `python -m src.simulation.runner --trials 100 --seed 42`
6. Dashboard: `streamlit run src/dashboard/app.py`

## Conventions

1. **Dependencies point down**: core <- miners <- defense <- simulation <- dashboard.
2. **Inject, don't hard-code**: rules go into `Blockchain(rules=...)`, miners into
   `Network`; the LPC rule needs `attach(blockchain)` (see `defense.lpc.build_chain`).
3. **Seed everything**: derive trial seeds with `simulation.seeding.derive_seed`; never
   use global randomness.
4. Keep comments minimal; prefer clear names.
5. Every new unit gets a test in `tests/`. CI runs ruff, black, mypy, pytest --cov.
