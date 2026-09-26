# Your fly trading laboratory

This local extension uses Stonkfly's actual full retained MaleCNS neural simulation. The laboratory command only simulates trades. It does not load account credentials or call an order API.

## Start here

Run from the `fly-trading-lab` directory. The isolated Python environment is `.venv`.

```sh
.venv/bin/python -m stonkfly.lab fixture --out runs/synthetic.csv
.venv/bin/python -m stonkfly.lab run --prices runs/synthetic.csv --out runs/my-experiment --steps 12
```

Each result directory must be new, so previous runs cannot be overwritten. Four profiles run sequentially to avoid loading several full brains into RAM. Ctrl-C stops the experiment; completed profile logs remain, but this lab does not resume partial runs. Repeat with a new directory. The existing upstream trading CLI has its own checkpoint/resume behavior.

To download approximately one day of completed five-minute Bitcoin candles from the public Coinbase Exchange API:

```sh
.venv/bin/python -m stonkfly.lab fetch --out runs/bitcoin.csv
.venv/bin/python -m stonkfly.lab run --prices runs/bitcoin.csv --out runs/bitcoin-experiment --steps 12
```

These are BTC-USD candles, not BTC-USDC order-book data. The lab defaults to a modeled 0.6% fee per side and 0.05% adverse execution friction per side; these are experimental assumptions, not your actual exchange fee tier. Decisions see only completed candles through the current close and execute at the next open. Warmup means chart history, not neural pre-training. Missing candles retain their actual timestamps; neural time per observation remains fixed. There are no upstream wall-clock cooldowns in this replay: one proposal per candle, a $10 order cap, and a 50% exposure cap are the declared lab policy.

## Change reinforcement

Edit `experiments/profiles.json`, or copy it and pass `--profiles your-file.json`. Profile names become output filenames. All profiles begin at the identical saved neural checkpoint with $100 simulated cash.

| Setting | Meaning |
|---|---|
| `gain` / `loss` | Positive/negative reinforcement multipliers, 0–10 |
| `gain_power` / `loss_power` | Curve shape; 1 is linear; above 1 increases large-outcome sensitivity |
| `reference_return` | Portfolio return used to scale feedback; default 0.001 = 0.1% |
| `deadband_return` | Ignore absolute returns up to this amount; default 0.00001 = 0.001% |
| `max_current` | Cap on artificial current, maximum 40; default 40 |
| `learning` | False freezes connection efficacies, but neural activity still reacts to input |

If `x = abs(portfolio return) / reference_return`, the pulse current is `min(max_current, 20 * sensitivity * x * (1+x) ** (power-1))`. Positive returns stimulate the reward group; negative returns stimulate the aversive group. Pulse duration remains 200 ms at the default 500 ms neural decision window. This formula and cap are engineering choices, not calibrated biology. Larger currents need not produce proportionately larger spike responses or more cautious decisions. Inspect the recorded responses.

The input is change in total portfolio equity, including unrealized returns and fees, between successive observations. The first observation has no feedback. Reward from the last executed action would arrive at the next observation; after the final trade the portfolio is marked and the experiment ends. Reward is not a causal attribution to an individual action. Reward curves do not directly edit weights or select trades.

For reward-free control, add a profile with `gain: 0, loss: 0`. Endogenous neural modulation may still change weights when learning is enabled. For a strict fixed-weight control, use `learning: false`.

## Read results

- `REPORT.md`: comparable balances, returns, fees, trade counts and maximum drawdowns.
- `summary.json`: additionally records neural proposal counts, elapsed time and changed connections.
- `equity.csv`: portfolio curves for all profiles, cash and buy-and-hold.
- Each profile's `.jsonl`: reward intensity, reward/aversive neuron spikes, sensory input hash, output activity, proposed action, actual execution and memory changes at each observation.
- `*-input.png`: actual last image shown to the modeled photoreceptors.
- `initial-brain.npz` and `*-final.npz`: real full-brain checkpoints.
- `provenance.json`: dataset checks, code hashes, runtime versions, fixed operator settings and input data hash.

The buy-and-hold benchmark invests up to the exposure cap immediately; the fly builds exposure in $10 increments. Neither is an exposure-matched causal control. Balances mark BTC at the candle close, with no forced terminal sale or liquidation fee. Drawdown is sampled at candle closes; intrabar losses are not captured. Continuous BTC quantities are used, without exchange lot rounding or order-book depth.

Short runs explain the mechanism, not profitability. Compare neural activity and actions as well as balances: stronger pulses might change spike counts without changing any trade. Do not tune on a period and call that same period a test. Serious learning evaluation needs held-out chronological periods, multiple starts/market windows, shuffled feedback and weight-reset comparisons. A toy sine wave can help diagnose behavior, but useful conditioning is not guaranteed.
