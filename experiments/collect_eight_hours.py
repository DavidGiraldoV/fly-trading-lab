"""Collect independent paper runs after checking their model and input identity."""
import csv
import json
import shutil
from decimal import Decimal as D
from pathlib import Path

import numpy as np


def main():
    original = Path('runs/bitcoin-eight-hours')
    worker_root = Path('runs/eight-hour-workers')
    target = Path('runs/bitcoin-eight-hours-comparison')
    provenance = json.loads((original/'provenance.json').read_text())
    prices = {row['timestamp']: D(row['open']) for row in csv.DictReader(open('runs/bitcoin.csv'))}
    sources = {'balanced': original, **{name:worker_root/name for name in ('loss-sensitive','gain-sensitive','frozen')}}
    all_rows = {}
    summaries = []
    fee = D(provenance['arguments']['fee'])
    friction = D(provenance['arguments']['friction'])
    for name, source in sources.items():
        if not (source/f'{name}-final.npz').exists():
            raise ValueError(f'{name} has no finished checkpoint')
        worker = json.loads((source/'provenance.json').read_text())
        for key in ('settings','market_sha256','source_sha256','dataset'):
            if worker[key] != provenance[key]:
                raise ValueError(f'{name} changed {key}')
        if worker['profiles'][name] != provenance['profiles'][name]:
            raise ValueError('Reward configuration mismatch')
        for key in ('warmup','steps','neural_ms','fee','friction','order','max_exposure'):
            if worker['arguments'][key] != provenance['arguments'][key]:
                raise ValueError(f'{name} changed {key}')
        with np.load(original/'initial-brain.npz') as initial, np.load(source/'initial-brain.npz') as other:
            if set(initial.files) != set(other.files) or any(not np.array_equal(initial[k],other[k]) for k in initial.files):
                raise ValueError(f'{name} has a different initial brain')
        rows=[json.loads(line) for line in (source/f'{name}.jsonl').read_text().splitlines()]
        if len(rows)!=96 or rows[-1]['neural']['brain_ms']!=48000:
            raise ValueError(f'{name} has incomplete neural/market time')
        if all_rows and [r['timestamp'] for r in rows] != [r['timestamp'] for r in all_rows['balanced']]:
            raise ValueError('Market timeline mismatch')
        all_rows[name]=rows
        previous_btc=D(0); fees=D(0); peak=D(100); drawdown=D(0)
        counts={'BUY':0,'SELL':0,'HOLD':0}; trades=0
        for row in rows:
            counts[row['neural']['side']]+=1
            quantity=D(row['btc'])-previous_btc
            side=row['execution']
            if side in ('BUY','SELL'):
                execution_price=prices[row['timestamp']]*(1+friction if side=='BUY' else 1-friction)
                fees+=abs(quantity)*execution_price*fee
                trades+=1
            elif quantity:
                raise ValueError('Inventory changed without execution')
            previous_btc=D(row['btc'])
            equity=D(row['equity']); peak=max(peak,equity); drawdown=max(drawdown,(peak-equity)/peak)
        summary={'profile':name,'final_equity':rows[-1]['equity'],'return_pct':float(equity-100),
                 'max_drawdown_pct':float(drawdown*100),'fees':str(fees),'trades':trades,'proposals':counts,
                 'changed_edges':rows[-1]['neural']['memory']['changed_edges']}
        if (source/'summary.json').exists():
            worker_summary=next(s for s in json.loads((source/'summary.json').read_text()) if s['profile']==name)
            if abs(D(worker_summary['fees'])-fees)>D('1e-20') or worker_summary['trades']!=trades or worker_summary['final_equity']!=summary['final_equity']:
                raise ValueError('Independent accounting summary mismatch')
        summaries.append(summary)
    reference=json.loads((worker_root/'frozen'/'summary.json').read_text())
    summaries.extend(s for s in reference if s['profile'] in ('cash','buy-and-hold'))
    target.mkdir(exist_ok=False)
    provenance['execution_layout']={name:str(path) for name,path in sources.items()}
    provenance['initial_arrays_identical_across_workers']=True
    provenance['timing_note']='Workers were paused/resumed to avoid resource contention. Neural and market clocks are unchanged; compute_seconds may include scheduling pauses and is not a performance benchmark.'
    (target/'provenance.json').write_text(json.dumps(provenance,indent=2))
    (target/'summary.json').write_text(json.dumps(summaries,indent=2))
    shutil.copy2(original/'initial-brain.npz',target/'initial-brain.npz')
    for name,source in sources.items():
        for suffix in ('.jsonl','-input.png','-final.npz'):
            shutil.copy2(source/f'{name}{suffix}',target/f'{name}{suffix}')
    report=['# Eight-hour paper experiment','',
            '96 five-minute decisions per profile; 48 seconds of neural simulation. All initial brain arrays, market inputs and model settings were verified identical across workers.', '',
            '| Profile | Ending balance | Return | Worst drawdown | Fees | Trades |','|---|---:|---:|---:|---:|---:|']
    for s in summaries:
        report.append(f"| {s['profile']} | ${float(s['final_equity']):.4f} | {s['return_pct']:.3f}% | {s['max_drawdown_pct']:.3f}% | ${float(s['fees']):.4f} | {s['trades']} |")
    report.extend(['','Fees are modeled at 0.6% per side plus 0.05% adverse execution friction. The fly has a $10 order limit and 50% exposure cap. Buy-and-hold invests up to the cap immediately; cash remains uninvested. Portfolio values include unsold BTC, without terminal liquidation fees. These are exploratory results, not evidence of profitable learning.',''])
    (target/'REPORT.md').write_text('\n'.join(report))
    # Preserve baseline series produced by the reference worker.
    base_rows=list(csv.DictReader(open(worker_root/'frozen'/'equity.csv')))
    with (target/'equity.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['step',*sources,'buy-and-hold','cash'])
        for i,base in enumerate(base_rows):
            w.writerow([i,*[100 if i==0 else all_rows[name][i-1]['equity'] for name in sources],base['buy-and-hold'],base['cash']])
    print(target)


if __name__=='__main__':
    main()
