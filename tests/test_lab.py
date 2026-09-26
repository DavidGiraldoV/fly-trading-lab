import json
from types import SimpleNamespace

import numpy as np
import pytest

from stonkfly.config import D
from stonkfly.lab import Portfolio, RewardCurve, fixture, read_prices, run


def test_feedback_scale_deadband_and_caps():
    balanced = RewardCurve()
    sensitive = RewardCurve(loss=2, loss_power=1.5)
    assert balanced.feedback("100.0001", 100)[:2] == ("none", 0)
    assert balanced.feedback("100.05", 100)[1] == pytest.approx(10)
    assert balanced.feedback("99.95", 100)[1] == pytest.approx(10)
    assert sensitive.feedback("99.95", 100)[1] > balanced.feedback("99.95", 100)[1]
    assert sensitive.feedback(90, 100)[1] == 40
    assert RewardCurve(gain=0, loss=0).feedback(90, 100)[:2] == ("none", 0)
    assert balanced.feedback(200.1, 200)[1] == pytest.approx(
        balanced.feedback(100.05, 100)[1]
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"gain": float("nan")},
        {"loss": -1},
        {"loss_power": 0},
        {"reference_return": 0},
        {"max_current": 41},
        {"deadband_return": 1},
    ],
)
def test_invalid_curves(kwargs):
    with pytest.raises(ValueError):
        RewardCurve(**kwargs)


def test_roundtrip_costs_and_exposure():
    p = Portfolio()
    for _ in range(20):
        p.execute("BUY", 100, fee=".006", friction=".0005", order=10, max_exposure=".5")
    assert p.cash >= 0 and p.btc * 100 / p.equity(100) <= D(".5000000000000000000001")
    while p.btc > D(".0001"):
        result = p.execute(
            "SELL", 100, fee=".006", friction=".0005", order=10, max_exposure=".5"
        )
        if result == "VETO":
            break
    assert p.equity(100) < 100 and p.fees > 0 and p.btc >= 0


def test_market_validation(tmp_path):
    path = tmp_path / "prices.csv"
    fixture(path, 5)
    assert len(read_prices(path)) == 5
    path.write_text("timestamp,open,close\n1,10,10\n1,11,11\n2,12,12\n3,13,13\n")
    with pytest.raises(ValueError):
        read_prices(path)


def test_chronology_and_identical_restarts(tmp_path, monkeypatch):
    # A test double checks accounting and timing only; never a claimed neural run.
    from stonkfly import data, display
    from stonkfly.neural import controller

    shown = []
    restores = []

    class FakeController:
        def __init__(self, s):
            self.s = s
            self.brain = SimpleNamespace(weights_frozen=False)

        def save(self, path):
            path.write_bytes(b"test double")

        def restore(self, path):
            restores.append(path)

        def observe(self, frame, kind, **kwargs):
            return {
                "side": "BUY",
                "compute_seconds": 0,
                "memory": {"changed_edges": 0},
                "spike_sha256": "test-double",
            }

    def frame(product, history, bid, ask):
        shown.append(history.copy())
        return np.zeros((180, 320, 3), dtype=np.uint8)

    monkeypatch.setattr(data, "verify", lambda: {"test_double": True})
    monkeypatch.setattr(controller, "FlyController", FakeController)
    monkeypatch.setattr(display, "market_frame", frame)
    prices = tmp_path / "prices.csv"
    prices.write_text(
        "timestamp,open,close\n1,10,10\n2,20,20\n3,30,30\n4,100,100\n5,200,200\n"
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"a": {}, "b": {}}))
    out = tmp_path / "results"
    run(
        SimpleNamespace(
            prices=prices,
            profiles=profiles,
            out=out,
            warmup=2,
            steps=1,
            fee="0",
            friction="0",
            order="10",
            max_exposure=".5",
            neural_ms=500,
        )
    )
    assert shown == [[10.0, 20.0, 30.0], [10.0, 20.0, 30.0]]
    assert len(restores) == 2 and restores[0] == restores[1]
    row = json.loads((out / "a.jsonl").read_text())
    assert D(row["btc"]) == D(".1")  # next open 100, never prior close 30
    assert D(row["equity"]) == 100
    assert (out / "a.jsonl").read_text() == (out / "b.jsonl").read_text()
    assert (out / "REPORT.md").exists()


@pytest.mark.parametrize("problem", ["short_input", "reserved_name", "existing_output"])
def test_invalid_run_preserves_output(tmp_path, monkeypatch, problem):
    from stonkfly import data

    monkeypatch.setattr(
        data, "verify", lambda: pytest.fail("Must reject before loading graph")
    )
    prices = tmp_path / "prices.csv"
    fixture(prices, 5)
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"cash" if problem == "reserved_name" else "a": {}}))
    out = tmp_path / "result"
    if problem == "existing_output":
        out.mkdir()
        (out / "keep").write_text("original")
    args = SimpleNamespace(
        prices=prices,
        profiles=profiles,
        out=out,
        warmup=2,
        steps=10 if problem == "short_input" else 1,
        fee="0",
        friction="0",
        order="10",
        max_exposure=".5",
        neural_ms=500,
    )
    with pytest.raises((ValueError, FileExistsError)):
        run(args)
    if problem == "existing_output":
        assert (out / "keep").read_text() == "original"
    else:
        assert not out.exists()
