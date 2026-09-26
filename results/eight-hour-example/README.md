# Eight-hour exploratory replay

Four identical initial brains observed the same historical Bitcoin candles with different fixed feedback settings. All four lost paper value after costs. Feedback changed behavior; this experiment does not demonstrate improved learning.

![Paper equity and proposed actions](comparison.png)

| Profile | BUY / SELL / HOLD proposals | Executed trades | Ending paper value | Fees | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Balanced | 29 / 3 / 64 | 16 | $99.1116 | $0.5997 | 1.080% |
| Loss-sensitive | 26 / 1 / 69 | 12 | $99.3232 | $0.4201 | 1.079% |
| Gain-sensitive | 46 / 2 / 48 | 15 | $99.1900 | $0.5392 | 1.079% |
| Frozen plasticity | 48 / 3 / 45 | 17 | $99.0720 | $0.6591 | 1.199% |
| Buy-and-hold | — | 1 | $99.5570 | $0.2992 | 0.846% |
| Cash | — | 0 | $100.0000 | $0 | 0% |

Starting paper capital: $100. Maximum exposure: 50%. Fly orders: at most $10. Fee: 0.6% per transaction; adverse fill friction: 0.05%. Orders use the next candle's open; equity uses its close. Final holdings are marked to market without a terminal liquidation fee. Buy-and-hold immediately invests up to the exposure cap, so its exposure is not matched to each fly profile.

## Clocks and data

The replay spans September 17, 2026, 12:15–20:15 UTC: 96 five-minute market intervals and **48 simulated neural seconds per profile** (500 ms per decision). The brain does not run continuously through market gaps. The initial chart history supplies context, not neural training.

The included 300-candle `prices.csv` is public Coinbase Exchange BTC-USD data, retrieved September 18, 2026. [Source request](https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300&start=2026-09-17T03%3A50%3A00%2B00%3A00&end=2026-09-18T04%3A50%3A00%2B00%3A00). Historical bid/ask spreads are unavailable; friction is modeled. The checksum and original source revision are in `manifest.json`.

The graph retains 166,700 neurons and 25,582,938 directed connections from MaleCNS v1.0. The simulator, sensory proxies, reinforcement rules and decoder are engineered assumptions; this is not a reproduction of a living fly's subjective experience.

## What changed?

Compared with balanced feedback, loss-sensitive feedback changed 31/96 proposed actions, gain-sensitive feedback 44/96, and frozen plasticity 46/96. The first differences occurred at decisions 13, 15 and 12 respectively. Balanced feedback shifted from 10 BUY, 1 SELL and 1 HOLD in hour one to 1 BUY, 2 SELL and 9 HOLD in hour eight.

Changed connections at the end: balanced 3,541; loss-sensitive 3,518; gain-sensitive 3,483; frozen 0. These are weight changes, not evidence of useful memories. The frozen profile still receives feedback pulses. Endogenous activity can occur in reward/aversive cells even without injected feedback.

`measurements.csv` contains selected per-decision measurements; `equity.csv` includes the initial balance and both benchmarks; `summary.json` contains aggregate measurements. Timestamp values identify the filled candle's start; equity is marked at that candle's close. Published values are simulated, not account records. Raw logs, checkpoints and connectome files remain excluded.

## Limits and next steps

This is a single window with fixed initial conditions and no independent repeats, held-out market test, reset/retention test or no-external-feedback comparison. Loss-sensitive behavior lost less here, but that cannot establish a better strategy or causal learning. Preserving eight hours of market history also does not test eight hours of continuous neural dynamics.

[Reproduce the run](../../docs/REPRODUCING.md) · [Planned validation, not yet performed](../../docs/VALIDATION-PLAN.md) · [Attribution](../../THIRD_PARTY.md).
