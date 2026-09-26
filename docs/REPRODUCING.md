# Reproduce the eight-hour example

Use the installation and dataset preparation instructions in the root README. Run commands from the repository root. No account, API key or funded balance is needed.

## One command for all four profiles

```sh
python -m stonkfly.lab run \
  --prices results/eight-hour-example/prices.csv \
  --profiles experiments/profiles.json \
  --warmup 100 --steps 96 --neural-ms 500 \
  --fee 0.006 --friction 0.0005 --order 10 --max-exposure 0.5 \
  --out runs/reproduction
```

The runner handles all four profiles sequentially from the same saved initial brain. No process IDs, worker suspension, manual merging or parallel execution are necessary. The output directory must be new. The runner rejects insufficient input rather than silently shortening a requested experiment. It writes local reports, measurements and checkpoints under `runs/`, which remains Git-ignored.

The included market input is a 300-candle snapshot of public Coinbase Exchange BTC-USD data. Its source is linked in the result README; its SHA-256 checksum is recorded in `results/eight-hour-example/manifest.json`. The measured window is September 17, 2026, 12:15–20:15 UTC. `warmup` supplies historical chart prices, not neural pre-training. No future candle is shown to the model. Each decision executes at the next candle's open with declared costs.

## Original experiment versus release cleanup

The original experiment implementation is preserved at commit `26a37d0`; the manifest records the full revision and the original Python/C++ source hashes. The publication cleanup formats source and strengthens argument validation without changing the neuron equations, reward formula or action decoder. For an exact source-level historical reconstruction, check out that commit in a separate clone and use the same input and settings. The original dependencies are pinned in that revision's `pyproject.toml`; transitive dependency resolution and native compiler/platform differences can still affect bitwise reproducibility.

The original long experiment used separate workers paused and resumed to avoid resource contention. Initial brain arrays and the first-hour numerical outputs were verified identical. CPU timing fields from those workers include suspension and are not benchmarks. The public command uses the simpler sequential runner.

## Inspect or share another run

```sh
python experiments/summarize.py runs/reproduction --out runs/reproduction/NEURAL-RESPONSES.md
python experiments/export_results.py --run runs/reproduction \
  --prices results/eight-hour-example/prices.csv --out runs/reviewed-export
```

The export selects derived measurements and approved metadata; it does not copy raw logs, checkpoint files, local paths, credentials or arbitrary provenance fields. Review an export before intentionally adding it to Git. Simulated portfolio values are published only as explicitly selected experimental results.

To regenerate the published figure from the reviewed measurements:

```sh
pip install -e '.[report]'
python experiments/plot_results.py results/eight-hour-example
```

## Validation

The normal test suite exercises accounting, temporal ordering, reward curves, validation and result export without the connectome. After preparing the data, the explicit integration check runs the full graph:

```sh
STONKFLY_FULL_TEST=1 python -m pytest tests/test_neural.py::test_full_graph_sensory_reinforcement_checkpoint -q
```

Software tests establish implementation behavior. They do not establish faithful fly physiology, subjective pain/pleasure or profitable learning.
