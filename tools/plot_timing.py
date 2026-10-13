"""Optional actual-board timing figure; never a CI/test dependency."""

import argparse
import json
import struct
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.replay / "timing_report.json").read_text())
    if report["status"] not in ("PASS", "FAIL"):
        raise ValueError("figure requires complete, verified raw timing evidence")
    from harness.replay_report import analyze

    raw = (args.replay / "raw/commands.bin").read_bytes()
    audited = analyze(
        raw,
        (args.replay / "raw/timing.bin").read_bytes(),
        (args.replay / "expected-forces.bin").read_bytes(),
        (args.replay / "inputs.bin").read_bytes(),
        report["raw_completion"]["summary_words"],
    )
    if any(report[key] != value for key, value in audited.items()):
        raise ValueError("timing figure/report mismatch")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = list(struct.iter_unpack("<IfIIB", raw))
    compute = [row[3] / 520 for row in rows]
    jitter = [((rows[k][2] - rows[k - 1][2]) % 2**32 - 520000) / 520 for k in range(1, 8000)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for ax, values, label, color in zip(
        axes,
        (compute, jitter),
        ("ctrl_step duration (µs)", "Period jitter (µs)"),
        ("#2563eb", "#a855f7"),
        strict=True,
    ):
        ax.hist(values, bins=40, color=color, alpha=0.85)
        ax.set(xlabel=label, ylabel="Ticks")
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_title(f"p99 {report['compute_us']['p99']:.3f} µs; gate <100 µs")
    axes[1].set_title(
        f"|jitter| p99 {report['absolute_period_jitter_us']['p99']:.3f} µs; gate <5 µs"
    )
    fig.suptitle(
        f"NUCLEO-H723ZG · {report['contact_profile']} · {report['status']}\n"
        "DWT/TIM6 share a clock; absolute clock accuracy unverified",
        fontsize=12,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
