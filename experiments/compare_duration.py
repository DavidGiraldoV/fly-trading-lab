"""Compare an extended replay with its original short prefix."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read_events(directory, profile):
    return [json.loads(line) for line in (directory / f'{profile}.jsonl').read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('extended', type=Path)
    args = parser.parse_args()
    old_prov = json.loads((args.original / 'provenance.json').read_text())
    new_prov = json.loads((args.extended / 'provenance.json').read_text())
    for key in ('market_sha256', 'profiles', 'settings', 'source_sha256'):
        if old_prov[key] != new_prov[key]:
            raise ValueError(f'Comparison changed {key}')
    summaries = json.loads((args.extended / 'summary.json').read_text())
    profiles = list(new_prov['profiles'])
    data = {name: read_events(args.extended, name) for name in profiles}
    baseline = data['balanced']
    if any(len(rows) != len(baseline) for rows in data.values()):
        raise ValueError('Unequal observation counts')
    count = len(baseline)
    spacing = float(baseline[1]['timestamp']) - float(baseline[0]['timestamp'])
    times = [float(row['timestamp']) for row in baseline]
    if any(b-a != spacing for a,b in zip(times,times[1:])):
        raise ValueError('Irregular observation spacing')
    hours = count * spacing / 3600
    stamp = lambda seconds: datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lines = [
        '# Eight-hour behavior comparison', '',
        f'{hours:g} hours of historical market time: {stamp(times[0])} to {stamp(times[-1]+spacing)}. '
        f'{count} decisions per profile; {baseline[-1]["neural"]["brain_ms"]/1000:g} seconds of simulated neural time per profile.', '',
        'The same Bitcoin data, source code, settings and reward profiles were used. Every profile restarted from its original initial state; the first-hour prefix was checked against the prior experiment. All balances are paper balances starting at $100.', '',
        '| Profile | Balance after 1 hour | Balance after 8 hours | Fees over 8 hours | Trades | BUY / SELL / HOLD proposals |',
        '|---|---:|---:|---:|---:|---|',
    ]
    findings = {}
    for summary in summaries:
        name = summary['profile']
        if name not in data:
            continue
        rows = data[name]
        original = read_events(args.original, name)
        # Wall time is deliberately excluded from the exact deterministic check.
        for i, (a, b) in enumerate(zip(original, rows)):
            a = json.loads(json.dumps(a)); b = json.loads(json.dumps(b))
            a['neural'].pop('compute_seconds'); b['neural'].pop('compute_seconds')
            if a != b:
                raise ValueError(f'{name} differs from original prefix at observation {i+1}')
        counts = Counter(row['neural']['side'] for row in rows)
        lines.append(f"| {name} | ${float(original[-1]['equity']):.4f} | ${float(summary['final_equity']):.4f} | ${float(summary['fees']):.4f} | {summary['trades']} | {counts['BUY']} / {counts['SELL']} / {counts['HOLD']} |")
        different = [i+1 for i,(a,b) in enumerate(zip(baseline,rows)) if a['neural']['side'] != b['neural']['side']]
        findings[name] = {'prefix_matches': True, 'different_decisions_vs_balanced': different,
            'proposals': dict(counts), 'execution': dict(Counter(row['execution'] for row in rows)),
            'reward_events':sum(row['neural']['stimulus']=='reward' for row in rows),
            'aversive_events':sum(row['neural']['stimulus']=='aversive' for row in rows),
            'first_hour':dict(Counter(row['neural']['side'] for row in rows[:12])),
            'last_hour':dict(Counter(row['neural']['side'] for row in rows[-12:])),
            'holds_without_gate_spikes':sum(row['neural']['side']=='HOLD' and row['neural']['gate_spikes']==0 for row in rows),
            'holds_below_direction_threshold':sum(row['neural']['side']=='HOLD' and abs(row['neural']['difference_hz'])<2 for row in rows),
            'final_changed_connections':rows[-1]['neural']['memory']['changed_edges']}
    lines += ['', '## Did the profiles diverge?', '']
    for name, finding in findings.items():
        if name == 'balanced':
            continue
        different = finding['different_decisions_vs_balanced']
        detail = f"First differing decision: {different[0]} ({(different[0]-1)*spacing/60:g} minutes after the initial observation)." if different else 'No differing decisions.'
        lines.append(f'- **{name}:** {len(different)}/{count} proposed actions differ from balanced. {detail}')
    lines += ['', '## Why did it hold?', '']
    for name, finding in findings.items():
        holds=finding['proposals'].get('HOLD',0)
        lines.append(f"- {name}: {finding['holds_without_gate_spikes']}/{holds} HOLD decisions had no DNpe017 gate spikes; {finding['holds_below_direction_threshold']}/{holds} also or instead had a direction difference below 2 Hz. The fixed decoder requires both sufficient direction difference and an active gate to trade. These criteria can overlap.")
    lines += ['', '## Behavior by hour', '', '| Profile | Hour | BUY | SELL | HOLD | Executed trades | Ending balance |', '|---|---:|---:|---:|---:|---:|---:|']
    per_hour = int(3600/spacing)
    for name, rows in data.items():
        for start in range(0, count, per_hour):
            part = rows[start:start+per_hour]
            counts = Counter(row['neural']['side'] for row in part)
            trades = sum(row['execution'] in ('BUY','SELL') for row in part)
            lines.append(f"| {name} | {start//per_hour+1} | {counts['BUY']} | {counts['SELL']} | {counts['HOLD']} | {trades} | ${float(part[-1]['equity']):.4f} |")
    lines += ['', '## Interpretation limits', '', 'This is an exploratory replay, not a held-out profitability evaluation. Market inputs change over the eight hours, so differences between the first and last hour alone cannot establish learning. Frozen learning is the fixed-weight comparison; the reward profiles also change ongoing neural stimulation. A different action is evidence of different behavior, not necessarily a better decision.', '', 'A BUY proposal can be vetoed by the exposure/cash limit. These vetoes must not be interpreted as neural caution. The assumed fee is 0.6% per side, with 0.05% adverse execution friction; terminal holdings are marked without forced liquidation. The unchanged buy-and-hold and cash benchmarks appear in REPORT.md.', '']
    (args.extended/'BEHAVIOR.md').write_text('\n'.join(lines))
    (args.extended/'behavior.json').write_text(json.dumps(findings, indent=2))
    print(json.dumps(findings, indent=2))


if __name__ == '__main__':
    main()
