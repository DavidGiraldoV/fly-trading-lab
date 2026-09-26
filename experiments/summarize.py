"""Read completed experimental logs; report evidence without interpreting it as skill."""
import argparse
import json
from pathlib import Path


def summarize(directory):
    provenance = json.loads((directory / 'provenance.json').read_text())
    summaries = json.loads((directory / 'summary.json').read_text())
    lines = [
        f"## {directory.name}", "",
        f"Market: {provenance['market_source']['source']}", "",
        "| Profile | Ending balance | Fees | Trades | Reward events | Aversive events | Reward-cell spikes | Aversive-cell spikes | Changed connections |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    events_by_profile = {}
    for summary in summaries:
        name = summary['profile']
        path = directory / f'{name}.jsonl'
        if not path.exists():
            continue
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events_by_profile[name] = events
        neurons = [row['neural'] for row in events]
        metrics = [
            name, f"${float(summary['final_equity']):.4f}",
            f"${float(summary['fees']):.4f}", summary['trades'],
            sum(n['stimulus'] == 'reward' for n in neurons),
            sum(n['stimulus'] == 'aversive' for n in neurons),
            sum(n['reward_spikes'] for n in neurons),
            sum(n['aversive_spikes'] for n in neurons),
            neurons[-1]['memory']['changed_edges'],
        ]
        lines.append('| ' + ' | '.join(map(str, metrics)) + ' |')
    if 'balanced' in events_by_profile:
        baseline = events_by_profile['balanced']
        lines.extend(['', 'Comparisons with balanced feedback:', ''])
        for name, events in events_by_profile.items():
            if name == 'balanced':
                continue
            pairs = list(zip(baseline, events))
            changed_actions = sum(a['neural']['side'] != b['neural']['side'] for a, b in pairs)
            changed_activity = sum(a['neural']['spike_sha256'] != b['neural']['spike_sha256'] for a, b in pairs)
            lines.append(f'- {name}: different neural activity in {changed_activity}/{len(pairs)} observations; different proposed action in {changed_actions}/{len(pairs)} observations.')
    lines.extend(['', 'Cell spike counts include endogenous activity, not just the externally injected pulse. Changed connections count differences from the initial weights, not useful memories. An activity change can occur without changing an action; an action change alone does not establish improved learning.', ''])
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    lines = ['# First learning-lab observations', '', 'These short, fixed-start experiments demonstrate the input → neural activity → action → feedback loop. They are not held-out performance tests or evidence of profitable learning.', '']
    for directory in args.runs:
        lines.extend(summarize(directory))
    args.out.write_text('\n'.join(lines))
    print(args.out)


if __name__ == '__main__':
    main()
