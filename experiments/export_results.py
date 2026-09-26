"""Export selected paper measurements, never raw logs or local runtime metadata."""

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path


def export(run, prices, out, experiment_commit=None):
    provenance = json.loads((run / "provenance.json").read_text())
    if not provenance["execution"].startswith("paper only;"):
        raise ValueError("Only paper experiments may be exported")
    price_bytes = prices.read_bytes()
    digest = hashlib.sha256(price_bytes).hexdigest()
    if digest != provenance["market_sha256"]:
        raise ValueError("Market input hash mismatch")
    price_rows = csv.DictReader(io.StringIO(price_bytes.decode()))
    if price_rows.fieldnames != ["timestamp", "open", "close"]:
        raise ValueError("Only numeric timestamp/open/close market input is exportable")
    for price_row in price_rows:
        if set(price_row) != {"timestamp", "open", "close"} or any(
            not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", v) or not math.isfinite(float(v))
            for v in price_row.values()
        ):
            raise ValueError("Market input contains nonnumeric data")
    profiles = provenance["profiles"]
    if any(
        not re.fullmatch(r"[a-z0-9_][a-z0-9_-]{0,63}", name)
        or name in {"cash", "buy-and-hold"}
        for name in profiles
    ):
        raise ValueError("Invalid profile name")
    clean_profiles = {}
    for name, profile in profiles.items():
        clean_profiles[name] = {
            "learning": bool(profile.get("learning", True)),
            "curve": {
                k: float(v)
                for k, v in profile.get("curve", {}).items()
                if k
                in {
                    "gain",
                    "loss",
                    "gain_power",
                    "loss_power",
                    "reference_return",
                    "deadband_return",
                    "max_current",
                }
            },
        }
    arguments = {
        k: float(provenance["arguments"][k])
        for k in (
            "warmup",
            "steps",
            "neural_ms",
            "fee",
            "friction",
            "order",
            "max_exposure",
        )
    }
    measurements = []
    for name in profiles:
        events = [
            json.loads(line)
            for line in (run / f"{name}.jsonl").read_text().splitlines()
        ]
        if len(events) != int(arguments["steps"]):
            raise ValueError("Incomplete experiment")
        for step, event in enumerate(events, 1):
            neural = event["neural"]
            if neural["side"] not in {"BUY", "SELL", "HOLD"}:
                raise ValueError("Invalid action")
            measurements.append(
                {
                    "profile": name,
                    "step": step,
                    "timestamp": int(event["timestamp"]),
                    "equity": float(event["equity"]),
                    "action": neural["side"],
                    "feedback_return": float(event["feedback_return"]),
                    "pulse_current": float(event["pulse_current"]),
                    "gate_spikes": int(neural["gate_spikes"]),
                    "reward_spikes": int(neural["reward_spikes"]),
                    "aversive_spikes": int(neural["aversive_spikes"]),
                    "changed_edges": int(neural["memory"]["changed_edges"]),
                }
            )
    summaries = []
    for row in json.loads((run / "summary.json").read_text()):
        if row["profile"] not in {*profiles, "cash", "buy-and-hold"}:
            continue
        clean = {
            "profile": row["profile"],
            **{
                k: float(row[k])
                for k in ("final_equity", "return_pct", "max_drawdown_pct", "fees")
            },
            "trades": int(row["trades"]),
        }
        if "proposals" in row:
            clean["proposals"] = {
                k: int(row["proposals"][k]) for k in ("BUY", "SELL", "HOLD")
            }
            clean["changed_edges"] = int(row["changed_edges"])
        summaries.append(clean)
    hashes = {
        k: v
        for k, v in provenance["source_sha256"].items()
        if re.fullmatch(r"[a-zA-Z0-9_/]+\.(py|cpp)", k)
        and ".." not in k
        and not k.startswith("/")
        and re.fullmatch(r"[a-f0-9]{64}", v)
    }
    manifest = {
        "execution": "paper only",
        "market_sha256": digest,
        "arguments": arguments,
        "dataset": {
            k: int(provenance["dataset"][k]) for k in ("neurons", "directed_edges")
        },
        "source_sha256": hashes,
        "profiles": clean_profiles,
    }
    if experiment_commit:
        if not re.fullmatch(r"[a-f0-9]{40}", experiment_commit):
            raise ValueError("Expected full experiment commit hash")
        manifest["experiment_commit"] = experiment_commit
    equity = list(csv.DictReader((run / "equity.csv").open()))
    columns = ["step", *profiles, "buy-and-hold", "cash"]
    clean_equity = [{key: float(row[key]) for key in columns} for row in equity]
    out.mkdir(parents=True, exist_ok=False)
    (out / "prices.csv").write_bytes(price_bytes)
    for filename, value in [
        ("manifest.json", manifest),
        ("summary.json", summaries),
        ("profiles.json", clean_profiles),
    ]:
        (out / filename).write_text(json.dumps(value, indent=2) + "\n")
    for filename, rows in [
        ("measurements.csv", measurements),
        ("equity.csv", clean_equity),
    ]:
        with (out / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--experiment-commit")
    args = parser.parse_args()
    export(args.run, args.prices, args.out, args.experiment_commit)


if __name__ == "__main__":
    main()
