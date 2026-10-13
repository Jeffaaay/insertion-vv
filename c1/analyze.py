"""Read a sealed matrix, assess frozen predictions, and render five research figures."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = dict(
    F1="Frozen frames",
    F2="Dropped frames",
    F3="Delay jitter",
    F4="Sample rate",
    F5="Heart-rate drift",
    F6="Simulated deadline miss",
    F7="Actuator clipping",
    F8="Surface quantization",
)
UNITS = dict(F1="tick", F2="%", F3="ms", F4="Hz", F5="Hz", F6="tick", F7="%", F8="bit")
ABLATIONS = ["no-delay", "no-jitter-model", "no-quantization", "no-noise", "no-dropped-frame-model"]
COLORS = {"PASS": "#2d8878", "FAIL": "#c45343", "INVALID": "#77798b"}


def specs():
    return {f"F{i}": json.loads((ROOT / f"faults/F{i}.yaml").read_text()) for i in range(1, 9)}


def load_sealed(root):
    data = (root / "matrix.json").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == (root / "matrix.sha256").read_text().split()[0], "matrix seal mismatch"
    return json.loads(data), digest


def subset(rows, **terms):
    return [r for r in rows if all(r["scenario"][k] == v for k, v in terms.items())]


def aggregate(rows):
    states = {r["verdict"]["status"] for r in rows}
    return "INVALID" if not rows or "INVALID" in states else "FAIL" if "FAIL" in states else "PASS"


def worst(rows):
    return min(
        rows,
        key=lambda r: (
            -(r["contact"]["rms_e_um"] or 0),
            r["scenario"]["seed"],
            r["scenario"]["onset_ms"],
        ),
    )


def assess(matrix, digest):
    rows = matrix["runs"]
    base = subset(rows, controller="preview", ablation="baseline")
    nominal = subset(base, fault="none")[0]
    margins = {}
    for fault in specs():
        group = subset(base, fault=fault)
        rms = [r["contact"]["rms_e_um"] for r in group]
        velocity = max(r["contact"]["peak_abs_edot_mm_s"] for r in group)
        margins[fault] = {
            "min_rms_um": min(rms),
            "max_rms_um": max(rms),
            "max_peak_abs_edot_mm_s": velocity,
            "rms_margin_um": 20 - max(rms),
            "edot_margin_mm_s": 2 - velocity,
            "max_abs_rms_difference_from_nominal_nm": max(
                abs(v - nominal["contact"]["rms_e_um"]) for v in rms
            )
            * 1000,
        }
    boundaries, video = {}, {}
    for fault, spec in specs().items():
        series = [
            {"level": level, "status": aggregate(subset(base, fault=fault, level=level))}
            for level in spec["levels"]
        ]
        fails = [i for i, s in enumerate(series) if s["status"] == "FAIL"]
        first = fails[0] if fails else None
        boundary = series[first]["level"] if first is not None else None
        boundaries[fault] = {
            "levels": series,
            "first_fail": boundary,
            "preceding_level_passed": first is not None
            and first > 0
            and series[first - 1]["status"] == "PASS",
            "nominal_status": nominal["verdict"]["status"],
            "nonmonotonic": any(
                series[i]["status"] == "FAIL" and series[j]["status"] == "PASS"
                for i in range(len(series))
                for j in range(i + 1, len(series))
            ),
        }
        chosen = worst(
            subset(
                base, fault=fault, level=boundary if boundary is not None else spec["levels"][-1]
            )
        )
        video[fault] = {
            "run_id": chosen["run_id"],
            "scenario": chosen["scenario"],
            "boundary_observed": boundary is not None,
            "contact": chosen["contact"],
        }
    predictions = {}
    for key, selected in (
        ("P1", subset(base, fault="F4", level=25)),
        ("P2", [r for r in subset(base, fault="F5") if r["scenario"]["level"] >= 1.6]),
        ("P3", [r for r in subset(base, fault="F1") if r["scenario"]["level"] >= 60]),
    ):
        count = dict(Counter(r["verdict"]["status"] for r in selected))
        predictions[key] = {
            "supported": len(selected) == count.get("FAIL", 0),
            "counts": count,
            "total": len(selected),
        }
    timing = {}
    for fault in ("F1", "F2", "F3", "F6"):
        maxima = {
            str(onset): max(
                r["contact"]["rms_e_um"] for r in subset(base, fault=fault, onset_ms=onset)
            )
            for onset in (200, 1500, 2400, 5000)
        }
        largest = max(maxima.values())
        timing[fault] = {
            "max_contact_rms_um": maxima,
            "worst_onsets_ms": [int(t) for t, v in maxima.items() if v == largest],
        }
    predictions["P4"] = {
        "supported": all(2400 in x["worst_onsets_ms"] for x in timing.values()),
        "faults": timing,
    }
    baseline_lookup = {
        (
            r["scenario"]["fault"],
            r["scenario"]["level"],
            r["scenario"]["onset_ms"],
            r["scenario"]["seed"],
        ): r
        for r in base
        if r["scenario"]["fault"] != "none"
    }
    flips = {}
    for ablation in ABLATIONS:
        per_fault = {}
        for fault in specs():
            counts = Counter()
            for r in subset(rows, controller="preview", ablation=ablation, fault=fault):
                c = r["scenario"]
                b = baseline_lookup[(fault, c["level"], c["onset_ms"], c["seed"])]["verdict"][
                    "status"
                ]
                a = r["verdict"]["status"]
                counts["invalid" if "INVALID" in (a, b) else f"{b}->{a}"] += 1
            per_fault[fault] = dict(counts)
        total = sum(c.get("PASS->FAIL", 0) + c.get("FAIL->PASS", 0) for c in per_fault.values())
        flips[ablation] = {"total_flips": total, "faults": per_fault}
    maximum = max(f["total_flips"] for f in flips.values())
    leaders = [a for a, f in flips.items() if f["total_flips"] == maximum]
    predictions["P5"] = {
        "supported": leaders == ["no-delay"],
        "leaders": leaders,
        "ablations": flips,
    }
    py = subset(rows, controller="preview")
    c32 = {tuple(sorted(r["scenario"].items())): r for r in subset(rows, controller="preview_c32")}
    counts = Counter(
        {
            k: 0
            for k in (
                "total_pairs",
                "valid_pairs",
                "matching_pairs",
                "disagreeing_pairs",
                "invalid_pairs",
            )
        }
    )
    disagreements, invalid, differences = [], [], []
    for p in py:
        q = c32[tuple(sorted({**p["scenario"], "controller": "preview_c32"}.items()))]
        a, b = p["verdict"]["status"], q["verdict"]["status"]
        counts["total_pairs"] += 1
        if "INVALID" in (a, b):
            counts["invalid_pairs"] += 1
            invalid.append(
                {
                    "python": p["run_id"],
                    "c32": q["run_id"],
                    "fault": p["scenario"]["fault"],
                    "error": q["error"],
                }
            )
        else:
            counts["valid_pairs"] += 1
            rms_delta = abs(p["contact"]["rms_e_um"] - q["contact"]["rms_e_um"])
            differences.append(
                {
                    "python_run_id": p["run_id"],
                    "c32_run_id": q["run_id"],
                    "scenario": p["scenario"],
                    "rms_absolute_difference_um": rms_delta,
                    "rms_relative_difference_percent": 100 * rms_delta / p["contact"]["rms_e_um"],
                    "peak_edot_absolute_difference_mm_s": abs(
                        p["contact"]["peak_abs_edot_mm_s"] - q["contact"]["peak_abs_edot_mm_s"]
                    ),
                }
            )
            counts["matching_pairs" if a == b else "disagreeing_pairs"] += 1
            if a != b:
                disagreements.append(
                    {
                        "python": p["run_id"],
                        "c32": q["run_id"],
                        "scenario": p["scenario"],
                        "python_status": a,
                        "c32_status": b,
                    }
                )
    return {
        "matrix_sha256": digest,
        "run_count": len(rows),
        "counts": dict(Counter(r["verdict"]["status"] for r in rows)),
        "completed_reproducible": sum(r["reproducible"] for r in rows),
        "repeat_hash_pairs_match": sum(
            r["trace_sha256"] == r["repeat_trace_sha256"]
            and r["truth_sha256"] == r["repeat_truth_sha256"]
            for r in rows
        ),
        "identity_checks": sum("identity_check" in r for r in rows),
        "identity_failures": sum(not r.get("identity_check", {}).get("passed", True) for r in rows),
        "nominal": {"status": nominal["verdict"]["status"], "contact": nominal["contact"]},
        "boundaries": boundaries,
        "baseline_margins": margins,
        "predictions": predictions,
        "video_selection": video,
        "c32_comparison": {
            **dict(counts),
            "disagreements": disagreements,
            "invalid_pairs_detail": invalid,
            "metric_difference_maxima": {
                key: max(differences, key=lambda r: r[key])
                for key in (
                    "rms_absolute_difference_um",
                    "rms_relative_difference_percent",
                    "peak_edot_absolute_difference_mm_s",
                )
            },
        },
    }


def figures(matrix, summary, root):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "figure.facecolor": "#fbfbf8",
            "axes.facecolor": "#fbfbf8",
        }
    )
    folder = root / "figs"
    folder.mkdir(exist_ok=True)
    base = subset(matrix["runs"], controller="preview", ablation="baseline")
    stamp = "Windows SIL • frozen controller & verdict • matrix " + summary["matrix_sha256"][:12]

    def save(fig, name):
        fig.text(0.02, 0.015, stamp, fontsize=8, color="#59616a")
        fig.savefig(folder / f"{name}.png", dpi=300, facecolor=fig.get_facecolor())
        fig.savefig(folder / f"{name}.svg", facecolor=fig.get_facecolor())
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.8))
    fig.subplots_adjust(left=0.25, right=0.97, bottom=0.19, top=0.84)
    for y, (fault, b) in enumerate(summary["boundaries"].items()):
        for x, item in enumerate(b["levels"]):
            ax.add_patch(Rectangle((x - 0.46, y - 0.4), 0.92, 0.8, color=COLORS[item["status"]]))
            label = f"{item['level']:g} {UNITS[fault]}\n{item['status']}"
            if item["level"] == b["first_fail"]:
                label += " *"
            rms = max(
                r["contact"]["rms_e_um"] for r in subset(base, fault=fault, level=item["level"])
            )
            label += f"\nmax RMS {rms:.3f} µm"
            ax.text(x, y, label, ha="center", va="center", color="white", fontsize=9)
    ax.set(
        xlim=(-0.6, 5.6),
        ylim=(7.6, -0.7),
        yticks=range(8),
        yticklabels=[f"{f}  {NAMES[f]}" for f in specs()],
        xticks=[],
        xlabel=(
            "Registered severity →\n* First observed FAIL; pooled across registered onsets / seeds"
        ),
    )
    for s in ax.spines.values():
        s.set_visible(False)
    fig.suptitle("01 / Fault severity boundaries", x=0.03, ha="left", fontsize=20, y=0.97)
    fig.text(
        0.03,
        0.88,
        "Preview baseline • PASS requires contact RMS <20 µm AND peak |ė| <2 mm/s\nNominal: "
        + summary["nominal"]["status"]
        + " • F6 is simulated; hardware timing remains unverified.",
        fontsize=10,
    )
    save(fig, "fig1_fault_severity_heatmap")

    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.subplots_adjust(left=0.10, right=0.72, bottom=0.15, top=0.84)
    for fault, chosen in matrix["figure4_selection"].items():
        chosen_rows = subset(base, fault=fault, level=chosen["level"])
        onsets = sorted({r["scenario"]["onset_ms"] for r in chosen_rows})
        vals = [
            max(r["contact"]["rms_e_um"] for r in subset(chosen_rows, onset_ms=t)) for t in onsets
        ]
        ax.plot(
            [t / 1000 for t in onsets],
            vals,
            marker="o",
            label=f"{fault}: {chosen['level']:g} {UNITS[fault]}",
        )
    ax.axhline(20, color="#777", linestyle="--", lw=1, label="RMS threshold (not sole test)")
    ax.set(xlabel="Injection onset (s)", ylabel="Maximum contact RMS over seeds (µm)", yscale="log")
    ax.grid(alpha=0.15)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    changes = [
        summary["baseline_margins"][f]["max_abs_rms_difference_from_nominal_nm"]
        for f in ("F2", "F3", "F8")
    ]
    ax.text(
        1.03,
        0.40,
        "F2 / F3 / F8 overlap.\nAcross their full grids,\nmax absolute RMS change\n"
        f"from nominal: {changes[0]:.2f} / {changes[1]:.2f} /\n{changes[2]:.2f} nm, respectively.",
        transform=ax.transAxes,
        fontsize=9,
        va="top",
        color="#526169",
    )
    fig.suptitle("02 / Timing changes the result", x=0.03, ha="left", fontsize=20)
    fig.text(
        0.03,
        0.88,
        "Same preregistered selection as Figure 4. F5 is a single point at 2 s.",
        fontsize=10,
    )
    save(fig, "fig2_rms_vs_inject_time")

    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.22, right=0.97, bottom=0.20, top=0.82)
    for y, ablation in enumerate(ABLATIONS):
        for x, fault in enumerate(specs()):
            counts = summary["predictions"]["P5"]["ablations"][ablation]["faults"][fault]
            pf, fp = counts.get("PASS->FAIL", 0), counts.get("FAIL->PASS", 0)
            ax.add_patch(
                Rectangle(
                    (x - 0.47, y - 0.4),
                    0.94,
                    0.8,
                    color="#ca7966" if pf else "#9ccfc0" if fp else "#e6e7e2",
                )
            )
            ax.text(x, y, f"{pf + fp}\n{pf} P→F / {fp} F→P", ha="center", va="center", fontsize=8)
    ax.set(
        xlim=(-0.6, 7.6),
        ylim=(4.6, -0.6),
        xticks=range(8),
        xticklabels=specs(),
        yticks=range(5),
        yticklabels=ABLATIONS,
    )
    for s in ax.spines.values():
        s.set_visible(False)
    fig.suptitle("03 / Ablations that reverse a verdict", x=0.03, ha="left", fontsize=20)
    fig.text(
        0.03,
        0.87,
        (
            "Preview • per-run comparisons with matched baseline • no nominal / "
            "Figure 4 rows\nDisabled-fault identities are intentional; no-noise "
            "changes nothing because nominal noise is zero."
        ),
        fontsize=10,
    )
    fig.text(
        0.23,
        0.13,
        "No-delay nominal already FAILS: fixed-delay estimator interface effect, "
        "not a latency benefit test.",
        fontsize=8,
    )
    fig.text(
        0.23,
        0.09,
        "Counts include each registered onset and seed. INVALID pairs never count as flips.",
        fontsize=9,
    )
    save(fig, "fig3_ablation_flips")

    fig, ax = plt.subplots(figsize=(12, 5.8))
    fig.subplots_adjust(left=0.25, right=0.97, bottom=0.23, top=0.80)
    controllers = ["lab_frame_pd", "delayed_feedback", "delayed_feedback_offsetfree", "preview"]
    for y, controller in enumerate(controllers):
        for x, (fault, chosen) in enumerate(matrix["figure4_selection"].items()):
            rows = subset(
                matrix["runs"], controller=controller, ablation="baseline", fault=fault, **chosen
            )
            status = aggregate(rows)
            ax.add_patch(Rectangle((x - 0.47, y - 0.4), 0.94, 0.8, color=COLORS[status]))
            ax.text(x, y, status, ha="center", va="center", color="white", fontsize=9)
    ax.set(
        xlim=(-0.6, 7.6),
        ylim=(3.6, -0.6),
        yticks=range(4),
        yticklabels=[
            c
            + "\n(nominal "
            + subset(matrix["runs"], controller=c, ablation="baseline", fault="none")[0]["verdict"][
                "status"
            ]
            + ")"
            for c in controllers
        ],
        xticks=range(8),
        xticklabels=[
            f"{f}\n{v['level']:g} {UNITS[f]}" for f, v in matrix["figure4_selection"].items()
        ],
    )
    for s in ax.spines.values():
        s.set_visible(False)
    fig.suptitle("04 / Same disturbance, four controllers", x=0.03, ha="left", fontsize=20)
    fig.text(
        0.03,
        0.86,
        (
            "Selection: preview first FAIL at 2.4 s; strongest if no FAIL. F5 "
            "onset=2 s.\nF2/F3 pool five seeds; others use seed 42. No gains or "
            "thresholds retuned."
        ),
        fontsize=10,
    )
    save(fig, "fig4_controllers_vs_faults")

    fig, ax = plt.subplots(figsize=(11, 6.3))
    ax.axis("off")
    fig.suptitle("05 / What SIL cannot establish", x=0.04, ha="left", fontsize=21)
    entries = [
        (
            "F9 / Serial CRC corruption",
            (
                "HIL-only. Inject damaged packets; observe rejection, recovery and safe "
                "command handling."
            ),
        ),
        (
            "F10 / Board–PC clock drift",
            "HIL-only. Measure timestamp alignment, drift accumulation and stale-frame handling.",
        ),
        (
            "F6 / Actual missed deadlines",
            (
                "SIL skips controller calls and holds force. Real ISR timing must be "
                "measured on hardware.\nFrozen C32 rejects tick gaps: 96 attempted cases "
                "are INVALID, not task FAIL."
            ),
        ),
        (
            "Scope of equivalence",
            (
                "Both full-matrix controllers use the Python injector. Rust is "
                "separately byte-checked.\nNo Rust closed-loop, hardware, clinical or "
                "cross-platform full-matrix claim."
            ),
        ),
    ]
    for i, (title, body) in enumerate(entries):
        y = 0.86 - i * 0.22
        ax.text(0, y, title, transform=ax.transAxes, fontsize=14, weight="bold", color="#233c52")
        ax.text(0, y - 0.055, body, transform=ax.transAxes, fontsize=10, va="top", linespacing=1.7)
    fig.subplots_adjust(left=0.05, right=0.97, top=0.89, bottom=0.07)
    save(fig, "fig5_hil_only")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/c1"))
    args = parser.parse_args()
    matrix, digest = load_sealed(args.root)
    summary = assess(matrix, digest)
    (args.root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    figures(matrix, summary, args.root)
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("c32_comparison", "video_selection")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
