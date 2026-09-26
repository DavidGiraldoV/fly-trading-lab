import json
from types import SimpleNamespace

import pytest

from stonkfly import cli, lab


def test_watch_routes_only_to_paper(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "main", calls.append)
    lab.main(
        ["watch", "--out", str(tmp_path), "--profile", "loss-sensitive", "--steps", "3"]
    )
    assert calls[0][0] == "run"
    assert "--live" not in calls[0] and "--fixture" not in calls[0]
    assert calls[0][calls[0].index("--profile") + 1] == "loss-sensitive"
    with pytest.raises(SystemExit):
        lab.main(["watch", "--out", str(tmp_path), "--live"])


def test_profiles_forbid_real_execution(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "run",
                "--live",
                "--profiles",
                "experiments/profiles.json",
                "--out",
                str(tmp_path / "out"),
            ]
        )
    assert not (tmp_path / "out").exists()


def test_stream_feedback_persistence_and_restart(monkeypatch, tmp_path):
    import dotenv

    from stonkfly import broker, data, market
    from stonkfly.neural import controller

    calls = []
    original_snapshot = market.FixtureMarket.snapshot

    def stable_snapshot(self):
        self.tick = 0
        return original_snapshot(self)

    monkeypatch.setattr(market.FixtureMarket, "snapshot", stable_snapshot)

    class FakeController:
        def __init__(self, settings):
            self.brain = SimpleNamespace(circuit={"report": {}}, visual_report={})

        def save(self, path):
            path.write_bytes(b"test checkpoint")

        def restore(self, path):
            assert path.read_bytes() == b"test checkpoint"

        def observe(self, frame, kind, *, pulse_current):
            calls.append((kind, pulse_current))
            return {"side": "BUY", "memory": {"changed_edges": 0}}

    monkeypatch.setattr(controller, "FlyController", FakeController)
    monkeypatch.setattr(data, "verify", lambda: {"test_double": True})
    monkeypatch.setattr(
        dotenv,
        "load_dotenv",
        lambda **kw: pytest.fail("Paper must not load credentials"),
    )
    monkeypatch.setattr(
        broker.CoinbaseBroker, "from_env", lambda *args: pytest.fail("No funded broker")
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"custom": {"curve": {"gain": 2, "loss": 2}}}))
    out = tmp_path / "run"
    argv = [
        "run",
        "--fixture",
        "--fast",
        "--profiles",
        str(profiles),
        "--profile",
        "custom",
        "--out",
        str(out),
        "--steps",
        "2",
    ]
    cli.main(argv)
    assert calls[0] == ("none", 0)
    events = [
        json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()
    ]
    assert events[0]["execution"]["status"] == "FILLED"
    assert events[0]["mode"] == "paper"
    assert float(events[0]["post_execution_equity_usdc"]) < 100
    for event, call in zip(events, calls):
        assert event["feedback"]["pulse_current"] == call[1]
    expected = lab.RewardCurve(gain=2, loss=2).feedback(
        events[1]["equity_usdc"], events[0]["equity_usdc"]
    )
    assert calls[1] == expected[:2]
    cli.main(argv[:-1] + ["1"])
    assert len(calls) == 3
    profiles.write_text(json.dumps({"custom": {"curve": {"gain": 3, "loss": 2}}}))
    with pytest.raises(SystemExit):
        cli.main(argv)
    assert len(calls) == 3  # Reject changed feedback before another neural decision.
