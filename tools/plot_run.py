"""Plot a saved run's errors and force without executing any simulation.

Install tools/requirements-viz.txt separately; this tool is never called by CI.
"""

import argparse
import json
from pathlib import Path

from _run_artifact import default_output, load_run, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metrics, config, rows = load_run(args.run)

    import matplotlib

    matplotlib.use("Agg")  # No window and no display needed.
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Patch

    output = (args.output or default_output(metrics, "png")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    t = np.array([r["time_us"] for r in rows]) / 1e6
    signals = (
        np.array([r["e_m"] for r in rows]) * 1e6,
        np.array([r["edot_m_s"] for r in rows]) * 1e3,
        np.array([r["contact_force_n"] for r in rows]) * 1e3,
    )
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#263548",
            "xtick.color": "#536174",
            "ytick.color": "#536174",
            "axes.edgecolor": "#bbc4ce",
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    fig.subplots_adjust(left=0.11, right=0.96, bottom=0.16, top=0.77, hspace=0.26)
    fig.suptitle(
        f"{metrics['controller']}  |  Recorded trajectory",
        x=0.11,
        y=0.97,
        ha="left",
        fontsize=21,
        weight="bold",
        color="#14283f",
    )
    fig.text(
        0.11,
        0.92,
        f"{metrics['contact_profile']}  /  seed {metrics['seed']}  /  "
        f"{config['contact']['target_stiffness_n_per_m']:g} N/m contact  /  "
        f"{metrics['duration_s']:g} s  /  measured plant velocities",
        color="#536174",
        fontsize=11,
    )
    summary = (
        (0.11, "FREE RMS", f"{metrics['free']['rms_e_um']:.3f} µm"),
        (0.40, "CONTACT RMS", f"{metrics['contact']['rms_e_um']:.3f} µm"),
        (0.70, "CONTACT PEAK FORCE", f"{metrics['contact']['peak_contact_force_mn']:.3f} mN"),
    )
    for x, label, value in summary:
        fig.text(x, 0.866, label, fontsize=9, color="#64748b", weight="bold")
        fig.text(x, 0.826, value, fontsize=21, color="#14283f", weight="bold")
    free_color, contact_color, spec_color = "#dbeafe", "#ffedd5", "#bbf7d0"
    panels = (
        ("a", r"Relative placement error $e$ (µm)", "#185fa5", 20.0),
        ("b", r"Relative velocity error $\dot{e}$ (mm/s)", "#6554a4", 2.0),
        ("c", "Contact force F (mN)", "#bd542b", None),
    )
    for ax, signal, (letter, label, color, limit) in zip(axes, signals, panels):
        ax.axvspan(1, 2, color=free_color, alpha=0.7, linewidth=0)
        ax.axvspan(3, 8, color=contact_color, alpha=0.6, linewidth=0)
        if limit is not None:
            ax.axhspan(-limit, limit, color=spec_color, alpha=0.55, linewidth=0)
            for bound in (-limit, limit):
                ax.axhline(bound, color="#27885c", linestyle=(0, (4, 3)), linewidth=1)
        ax.axhline(0, color="#94a3b8", linewidth=0.7)
        ax.plot(t, signal, color=color, linewidth=1.7)
        ax.set_title(f"{letter}   {label}", loc="left", fontsize=11, weight="bold", pad=9)
        ax.grid(axis="y", color="#64748b", alpha=0.12)
        ax.set_xlim(0, metrics["duration_s"])
        ax.margins(y=0.16)
        if limit is not None:
            ax.set_ylim(
                min(signal.min() * 1.18, -limit * 1.2), max(signal.max() * 1.18, limit * 1.2)
            )
        else:
            ax.set_ylim(bottom=-0.25)
    fig.legend(
        handles=[
            Patch(color=free_color, label="Free-space window  1–2 s"),
            Patch(color=contact_color, label="Contact window  3–8 s"),
            Patch(color=spec_color, label="Spec bands  ±20 µm / ±2 mm/s"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.54, 0.085),
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    axes[-1].set_xlabel("Time (s)", labelpad=8)
    fig.text(
        0.11,
        0.032,
        "e = desired gap − (needle − tissue). Bands are instantaneous references; "
        "task verdict uses contact RMS and peak velocity.",
        fontsize=8,
        color="#64748b",
    )
    fig.text(
        0.11,
        0.013,
        f"Trace SHA-256: {metrics['determinism']['trace_sha256']}",
        fontsize=7,
        color="#64748b",
    )
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    output.with_suffix(".plot.json").write_text(
        json.dumps(provenance(metrics, args.run), indent=2) + "\n", encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
