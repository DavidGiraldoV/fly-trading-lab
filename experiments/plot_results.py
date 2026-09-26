"""Plot the reviewed export; requires pip install -e '.[report]'."""

import argparse
import csv
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    summaries = json.loads((directory / "summary.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    rows = list(csv.DictReader((directory / "equity.csv").open()))
    prices = list(csv.DictReader((directory / "prices.csv").open()))
    interval = float(prices[1]["timestamp"]) - float(prices[0]["timestamp"])
    hours = [float(row["step"]) * interval / 3600 for row in rows]
    fig, axes = plt.subplots(
        1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [1.3, 1]}
    )
    colors = ["#0072B2", "#009E73", "#D55E00", "#CC79A7", "#777777", "#222222"]
    for summary, color in zip(summaries, colors):
        name = summary["profile"]
        axes[0].plot(
            hours,
            [float(row[name]) for row in rows],
            label=name,
            color=color,
            linestyle="-" if "proposals" in summary else "--",
            linewidth=1.7,
        )
    axes[0].set(
        xlabel="Market hours elapsed",
        ylabel="Paper portfolio value ($)",
        title="Equity after modeled fees and friction",
    )
    axes[0].legend(fontsize=8, ncol=2)
    profiles = [row for row in summaries if "proposals" in row]
    left = [0] * len(profiles)
    for action, color in [("BUY", "#0072B2"), ("SELL", "#D55E00"), ("HOLD", "#CCCCCC")]:
        counts = [row["proposals"][action] for row in profiles]
        axes[1].barh(
            [row["profile"] for row in profiles],
            counts,
            left=left,
            color=color,
            label=action,
        )
        left = [a + b for a, b in zip(left, counts)]
    axes[1].set(
        xlabel="Proposed actions (before execution limits)",
        title="Proposed actions",
    )
    axes[1].legend(fontsize=8, loc="lower right")
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    neural_seconds = (
        manifest["arguments"]["steps"] * manifest["arguments"]["neural_ms"] / 1000
    )
    fig.suptitle(
        f"One replay: {hours[-1]:g} market hours · {neural_seconds:g} neural seconds per profile",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(directory / "comparison.png", dpi=160, facecolor="white")


if __name__ == "__main__":
    main()
