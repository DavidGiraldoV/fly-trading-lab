# Live prices, simulated portfolio

After the installation and graph preparation in the root README, run from the repository root:

```sh
python -m stonkfly.lab watch --profile loss-sensitive --steps 10 --out runs/live-paper
```

This observes public Coinbase BTC-USDC prices and maintains a local, simulated 100 USDC portfolio. It needs no exchange account or API key, does not read `.env`, and exposes no option to place real orders. Network requests obtain public candles, product metadata and bid/ask quotes. The full retained neural graph produces the decisions.

Choose `balanced`, `loss-sensitive`, `gain-sensitive`, or `frozen` from `experiments/profiles.json`. To customize gain/loss sensitivity, exponents or current limits, copy that file under `runs/`, edit a profile, and supply `--profiles runs/my-profiles.json --profile my-profile`. The [operator guide](LEARNING-LAB.md) explains the reward curve. A profile is fixed for each experiment: changing settings on restart is rejected. Use a new output directory for a new profile.

## Timing and accounting

The default is ten decisions, approximately a minute apart. The brain advances 500 ms per decision; it is not continuously simulated during the wait. `--steps 0` continues until stopped. Keep the terminal/process running; laptop sleep interrupts observations. No background service is installed.

The first observation has no feedback. Subsequent feedback uses the relative change in marked-to-bid portfolio equity since the preceding observation, including simulated fees. Positive changes drive the reward input; negative changes drive the aversive input. The same configurable `RewardCurve` is used by historical replay. Frozen plasticity still receives feedback. These engineered inputs do not represent subjective pleasure or pain.

The streaming runner has different execution assumptions from the published replay: current bid/ask simulated fills, a 0.6% fee, at most 10 USDC order commitment including a fee reserve, at least 60 seconds between order attempts, and at most 24 attempts per UTC day. It has no replay-style 50% exposure cap; successive accepted buys can use most available cash. No borrowing or shorting is available. A 20 USDC loss threshold stops further orders but does not liquidate holdings. Fresh quotes and price-movement checks can veto proposals. This is not an exposure-matched reproduction of the eight-hour experiment.

## Inspect, stop and resume

`runs/live-paper/latest.json` reports the latest proposal, simulated execution, feedback return/current, pre-decision equity and post-execution marked equity. `events.jsonl` contains the history; `latest-input.png` shows the chart sent to the brain. Provenance records the profile and exact source hashes. The SQLite ledger and alternating brain checkpoints preserve committed state. All remain Git-ignored.

```sh
python -m stonkfly status --out runs/live-paper
```

Stop with Ctrl-C or create `runs/live-paper/STOP`. After a clean stop, run the same watch command with the same profile and directory to continue; `--steps` specifies additional decisions. Remove your STOP file before resuming. Source or profile changes require a fresh directory. Connection and consistency failures halt the session; inspect `error.json` and follow the [recovery guide](operations.md#state-recovery-and-privacy) rather than deleting the ledger or silently restarting.

Separate simultaneous profiles may see different quotes and compute delays. Use recorded historical replay for strictly matched input comparisons. Paper fills do not model order-book depth or establish live execution performance.
