"""Paper-only, chronological experiments. No exchange credentials or order APIs."""
import argparse
import csv
import hashlib
import json
import math
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import D, Settings


@dataclass(frozen=True)
class RewardCurve:
    gain: float = 1.0
    loss: float = 1.0
    gain_power: float = 1.0
    loss_power: float = 1.0
    reference_return: float = 0.001
    deadband_return: float = 0.00001
    max_current: float = 40.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid reward parameter: {name}")
        if not 0 < self.reference_return <= 1 or not 0 <= self.deadband_return < self.reference_return:
            raise ValueError("Require 0 <= deadband < reference <= 1")
        if not 0 < self.gain_power <= 3 or not 0 < self.loss_power <= 3:
            raise ValueError("Reward exponents must be in (0, 3]")
        if not 0 < self.max_current <= 40 or max(self.gain, self.loss) > 10:
            raise ValueError("Current cap <= 40 and sensitivity <= 10 required")

    def feedback(self, equity, anchor):
        if D(anchor) <= 0:
            raise ValueError("Positive equity anchor required")
        r = float((D(equity) - D(anchor)) / D(anchor))
        if abs(r) <= self.deadband_return:
            return "none", 0.0, r
        multiplier = self.gain if r > 0 else self.loss
        power = self.gain_power if r > 0 else self.loss_power
        magnitude = min(abs(r) / self.reference_return, 1e6)
        current = min(self.max_current, 20 * multiplier * magnitude * (1+magnitude)**(power-1))
        return ("reward" if r > 0 else "aversive") if current else "none", current, r


@dataclass
class Portfolio:
    cash: object = D(100)
    btc: object = D(0)
    fees: object = D(0)
    trades: int = 0

    def equity(self, price):
        return self.cash + self.btc * D(price)

    def execute(self, side, price, *, fee, friction, order, max_exposure):
        """Decision at prior close; fill at next open with adverse friction."""
        price, fee, friction, order, max_exposure = map(D, (price, fee, friction, order, max_exposure))
        if side == "BUY":
            execution_price = price * (1 + friction)
            # Cap BTC marked at this open, accounting for fee and execution friction.
            room = max(D(0), max_exposure * self.equity(price) - self.btc * price)
            exposure_budget = room / ((1-max_exposure) / (1+friction) + max_exposure*(1+fee))
            notional = min(order / (1+fee), self.cash / (1+fee), exposure_budget)
            quantity = notional / execution_price
        elif side == "SELL":
            execution_price = price * (1-friction)
            quantity = min(self.btc, order / execution_price)
            notional = quantity * execution_price
        elif side == "HOLD":
            return "HOLD"
        else:
            raise ValueError("Unknown action")
        if notional < D("0.01"):
            return "VETO"
        charge = notional * fee
        if side == "BUY":
            self.cash -= notional + charge
            self.btc += quantity
        else:
            self.cash += notional - charge
            self.btc -= quantity
        self.fees += charge
        self.trades += 1
        return side


def read_prices(path):
    with Path(path).open() as f:
        rows = list(csv.DictReader(f))
    previous = -math.inf
    for row in rows:
        stamp = float(row["timestamp"])
        if not math.isfinite(stamp) or stamp <= previous:
            raise ValueError("Timestamps must be finite and strictly increasing")
        previous = stamp
        for key in ("open", "close"):
            if D(row[key]) <= 0:
                raise ValueError("Prices must be positive")
    if len(rows) < 4:
        raise ValueError("At least four candles required")
    return rows


def fixture(path, count):
    if count < 4:
        raise ValueError("At least four candles required")
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "close"])
        last = 60000.0
        for i in range(count):
            close = 60000 * (1 + .025 * math.sin(i * .5))
            writer.writerow([1700000000 + i*300, f"{last:.4f}", f"{close:.4f}"])
            last = close
    path.with_suffix(".source.json").write_text(json.dumps({"source": "synthetic sine wave; not Bitcoin history", "candles": count}, indent=2))


def fetch(path):
    """Public, completed BTC-USD five-minute candles; no account or API key."""
    import urllib.request
    end = int(time.time() // 300) * 300
    start = end - 300*300
    def iso(t):
        return datetime.fromtimestamp(t, timezone.utc).isoformat()
    from urllib.parse import urlencode
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?" + urlencode({"granularity":300,"start":iso(start),"end":iso(end)})
    req = urllib.request.Request(url, headers={"User-Agent":"FlyTradingLearningLab/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        candles = json.load(response)
    candles = sorted((c for c in candles if start <= c[0] < end), key=lambda c:c[0])
    if len(candles) < 4:
        raise ValueError("Insufficient public candles")
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "close"])
        for c in candles:
            writer.writerow([c[0], c[3], c[4]])
    read_prices(path)
    path.with_suffix(".source.json").write_text(json.dumps({"source":"Coinbase Exchange BTC-USD", "url":url, "retrieved":time.time(), "note":"USD candles; historical bid/ask unavailable; friction modeled"}, indent=2))


def run(args):
    import numpy as np
    from PIL import Image
    from .data import verify
    from .display import market_frame
    from .neural.controller import FlyController
    rows = read_prices(args.prices)
    profiles = json.loads(args.profiles.read_text())
    if not profiles or not isinstance(profiles, dict):
        raise ValueError("Profiles must be a nonempty object")
    for name, value in profiles.items():
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in name):
            raise ValueError("Use lowercase letters, digits, hyphens or underscores in names")
        if set(value) - {"learning", "curve"} or type(value.get("learning", True)) is not bool:
            raise ValueError("Invalid profile")
        RewardCurve(**value.get("curve", {}))
    if not 2 <= args.warmup < len(rows)-1 or args.steps < 1:
        raise ValueError("Invalid warmup or steps")
    if not 0 <= D(args.fee) <= D('.02') or not 0 <= D(args.friction) <= D('.01'):
        raise ValueError("Invalid fee/friction")
    if not 0 < D(args.max_exposure) <= 1 or not 0 < D(args.order) <= 10:
        raise ValueError("Invalid exposure/order")
    args.out.mkdir(parents=True, exist_ok=False)
    verified = verify()
    settings = Settings(neural_ms=args.neural_ms, pulse_ms=min(200, args.neural_ms))
    source = args.prices.with_suffix('.source.json')
    provenance = {"dataset":verified,"market_sha256":hashlib.sha256(args.prices.read_bytes()).hexdigest(),
        "market_source":json.loads(source.read_text()) if source.exists() else {"source":"user CSV; unverified origin"},
        "profiles":profiles,"settings":asdict(settings),"arguments":{k:str(v) for k,v in vars(args).items()},
        "python":platform.python_version(), "numpy":np.__version__,
        "source_sha256":{str(p.relative_to(Path(__file__).parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.rglob('*') if p.suffix in ('.py','.cpp')},
        "execution":"paper only; next candle open; fixed modeled friction; no exchange orders", "claims":"Exploratory comparison, not proof of learning or biological replication"}
    (args.out/'provenance.json').write_text(json.dumps(provenance, indent=2))
    controller = FlyController(settings)
    initial = args.out/'initial-brain.npz'
    controller.save(initial)
    stop = min(len(rows)-1, args.warmup+args.steps)
    histories = {}; summaries = []
    for name, profile in profiles.items():
        controller.restore(initial)
        controller.s = Settings(neural_ms=args.neural_ms, pulse_ms=min(200,args.neural_ms), learning=profile.get('learning', True))
        controller.brain.weights_frozen = not controller.s.learning
        curve = RewardCurve(**profile.get('curve', {}))
        portfolio = Portfolio(); anchor = D(100); peak = D(100); worst = D(0)
        proposals = {"BUY":0,"SELL":0,"HOLD":0}; events = []; started = time.monotonic()
        print(f"Starting {name}: {stop-args.warmup} full-brain observations", flush=True)
        with (args.out/f'{name}.jsonl').open('w') as log:
            for i in range(args.warmup, stop):
                equity = portfolio.equity(rows[i]['close'])
                kind, current, change = curve.feedback(equity,anchor)
                history = [float(r['close']) for r in rows[max(0,i-119):i+1]]
                price = D(rows[i]['close'])
                frame = market_frame('BTC / PAPER', history, price*(1-D(args.friction)), price*(1+D(args.friction)))
                neural = controller.observe(frame, kind, pulse_current=current)
                side = neural['side']; proposals[side] += 1
                result = portfolio.execute(side, rows[i+1]['open'], fee=args.fee, friction=args.friction, order=args.order, max_exposure=args.max_exposure)
                after = portfolio.equity(rows[i+1]['close'])
                peak = max(peak, after); worst = max(worst,(peak-after)/peak)
                row = {"timestamp":rows[i+1]['timestamp'],"equity":str(after),"cash":str(portfolio.cash),"btc":str(portfolio.btc),"feedback_return":change,"pulse_current":current,"execution":result,"neural":neural}
                log.write(json.dumps(row)+'\n'); log.flush(); events.append(row)
                anchor = equity
                print(f"{name} {i-args.warmup+1}/{stop-args.warmup}: {side} -> {result}; equity {after:.4f}; pulse {kind} {current:.2f}; neural {neural['compute_seconds']:.2f}s",flush=True)
            Image.fromarray(frame).save(args.out/f'{name}-input.png')
        controller.save(args.out/f'{name}-final.npz')
        histories[name] = [100.0]+[float(e['equity']) for e in events]
        summaries.append({"profile":name,"final_equity":str(after),"return_pct":float(after-100),"max_drawdown_pct":float(worst*100),"fees":str(portfolio.fees),"trades":portfolio.trades,"proposals":proposals,"wall_seconds":time.monotonic()-started,"changed_edges":neural['memory']['changed_edges'],"final_spike_sha256":neural['spike_sha256']})
    baseline = Portfolio()
    baseline.execute('BUY',rows[args.warmup+1]['open'],fee=args.fee,friction=args.friction,order=100,max_exposure=args.max_exposure)
    values = [100.0]+[float(baseline.equity(rows[i+1]['close'])) for i in range(args.warmup,stop)]
    histories['buy-and-hold'] = values; histories['cash'] = [100.0]*len(values)
    peak=100.; worst=0.
    for value in values:
        peak=max(peak,value); worst=max(worst,(peak-value)/peak*100)
    summaries += [{"profile":"buy-and-hold","final_equity":str(values[-1]),"return_pct":values[-1]-100,"max_drawdown_pct":worst,"fees":str(baseline.fees),"trades":baseline.trades}, {"profile":"cash","final_equity":"100","return_pct":0,"max_drawdown_pct":0,"fees":"0","trades":0}]
    (args.out/'summary.json').write_text(json.dumps(summaries,indent=2))
    with (args.out/'equity.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['step',*histories]); w.writerows([i,*[v[i] for v in histories.values()]] for i in range(len(values)))
    report = ['# Fly trading learning experiment','',f"Source: {provenance['market_source']['source']}", '',f'{stop-args.warmup} decisions per profile. Each starts from the same neural checkpoint and $100 paper balance.', '', '| Profile | Final balance | Return | Worst drawdown | Fees | Trades |','|---|---:|---:|---:|---:|---:|']
    for s in summaries:
        report.append(f"| {s['profile']} | ${float(s['final_equity']):.4f} | {s['return_pct']:.3f}% | {s['max_drawdown_pct']:.3f}% | ${float(s['fees']):.4f} | {s['trades']} |")
    report += ['', 'These are exploratory observations, not evidence of profitable learning. Reward settings are fixed during each run; market periods are not held out. Buy-and-hold invests up to the exposure cap immediately, while the fly has a $10 order cap. Compare exposure as well as return.', '', 'Feedback uses change in total marked portfolio value, including fees and unrealized gains/losses. A pulse reflects past portfolio change, not proof that an action caused it. Frozen memory still permits neural responses to feedback. CSV candle replay models execution costs; it does not reconstruct historical order books.', '', 'Inspect the JSONL files for input hashes, neural spike counts, reward currents, proposed actions, executed actions and memory changes. The initial checkpoint and each final checkpoint are saved.']
    (args.out/'REPORT.md').write_text('\n'.join(report)+'\n')
    print(f"Report: {args.out/'REPORT.md'}",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    for command in ('fixture','fetch'):
        q=sub.add_parser(command); q.add_argument('--out',type=Path,required=True)
        if command=='fixture': q.add_argument('--candles',type=int,default=160)
    q=sub.add_parser('run'); q.add_argument('--prices',type=Path,required=True); q.add_argument('--profiles',type=Path,default=Path('experiments/profiles.json')); q.add_argument('--out',type=Path,required=True)
    q.add_argument('--warmup',type=int,default=100); q.add_argument('--steps',type=int,default=12); q.add_argument('--neural-ms',type=float,default=500)
    q.add_argument('--fee',default='0.006'); q.add_argument('--friction',default='0.0005'); q.add_argument('--order',default='10'); q.add_argument('--max-exposure',default='0.5')
    args=p.parse_args()
    if args.command=='run': run(args)
    else:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        if args.out.exists(): raise ValueError('Choose a new output file')
        fixture(args.out,args.candles) if args.command=='fixture' else fetch(args.out)


if __name__=='__main__':
    main()
