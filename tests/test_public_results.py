"""Check publication evidence and prevent accidental arbitrary-metadata exports."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from experiments.export_results import export

RESULTS = Path(__file__).resolve().parents[1] / "results"


@pytest.mark.parametrize(
    "directory,steps", [("eight-hour-example", 96), ("two-week-hourly", 336)]
)
def test_reviewed_results_are_consistent(directory, steps):
    result = RESULTS / directory
    manifest = json.loads((result / "manifest.json").read_text())
    assert (
        hashlib.sha256((result / "prices.csv").read_bytes()).hexdigest()
        == manifest["market_sha256"]
    )
    measurements = list(csv.DictReader((result / "measurements.csv").open()))
    equity = list(csv.DictReader((result / "equity.csv").open()))
    for summary in json.loads((result / "summary.json").read_text()):
        name = summary["profile"]
        assert float(equity[-1][name]) == pytest.approx(summary["final_equity"])
        if "proposals" not in summary:
            continue
        events = [row for row in measurements if row["profile"] == name]
        assert len(events) == manifest["arguments"]["steps"] == steps
        assert float(events[-1]["equity"]) == pytest.approx(summary["final_equity"])
        assert {
            side: sum(row["action"] == side for row in events)
            for side in ("BUY", "SELL", "HOLD")
        } == summary["proposals"]


def make_run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    prices = tmp_path / "prices.csv"
    prices.write_text("timestamp,open,close\n1,10,10\n2,10,10\n")
    provenance = {
        "execution": "paper only; test",
        "market_sha256": hashlib.sha256(prices.read_bytes()).hexdigest(),
        "profiles": {"a": {"learning": True, "curve": {"gain": 1}}},
        "arguments": dict(
            warmup=2,
            steps=1,
            neural_ms=500,
            fee=0.006,
            friction=0.0005,
            order=10,
            max_exposure=0.5,
            out="/Users/PRIVATE_SENTINEL",
        ),
        "dataset": {"neurons": 1, "directed_edges": 1, "path": "PRIVATE_SENTINEL"},
        "source_sha256": {},
        "api_key": "PRIVATE_SENTINEL",
        "market_source": {"source": "PRIVATE_SENTINEL"},
    }
    (run / "provenance.json").write_text(json.dumps(provenance))
    (run / "summary.json").write_text(
        json.dumps(
            [
                dict(
                    profile="a",
                    final_equity=100,
                    return_pct=0,
                    max_drawdown_pct=0,
                    fees=0,
                    trades=0,
                    private="PRIVATE_SENTINEL",
                )
            ]
        )
    )
    (run / "a.jsonl").write_text(
        json.dumps(
            dict(
                timestamp=2,
                equity=100,
                feedback_return=0,
                pulse_current=0,
                private="PRIVATE_SENTINEL",
                neural=dict(
                    side="HOLD",
                    gate_spikes=0,
                    reward_spikes=0,
                    aversive_spikes=0,
                    memory=dict(changed_edges=0),
                ),
            )
        )
    )
    (run / "equity.csv").write_text(
        "step,a,buy-and-hold,cash\n0,100,100,100\n1,100,100,100\n"
    )
    return run, prices


def test_export_excludes_arbitrary_private_metadata(tmp_path):
    run, prices = make_run(tmp_path)
    out = tmp_path / "export"
    export(run, prices, out)
    assert all("PRIVATE_SENTINEL" not in p.read_text() for p in out.iterdir())
    with pytest.raises(FileExistsError):
        export(run, prices, out)


@pytest.mark.parametrize("problem", ["hash", "live", "name", "price_metadata"])
def test_export_rejects_invalid_inputs_before_writing(tmp_path, problem):
    run, prices = make_run(tmp_path)
    p = json.loads((run / "provenance.json").read_text())
    if problem == "hash":
        p["market_sha256"] = "wrong"
    if problem == "live":
        p["execution"] = "live"
    if problem == "name":
        p["profiles"] = {"../private": {}}
    if problem == "price_metadata":
        prices.write_text("timestamp,open,close,secret\n1,10,10,PRIVATE_SENTINEL\n")
        p["market_sha256"] = hashlib.sha256(prices.read_bytes()).hexdigest()
    (run / "provenance.json").write_text(json.dumps(p))
    with pytest.raises(ValueError):
        export(run, prices, tmp_path / "export")
    assert not (tmp_path / "export").exists()
