"""Run the preregistered matrix locally and retain lossless per-run evidence."""

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sim.platform_info import platform_fingerprint
from sim.run import canonical, sha256

from .faults import ABLATIONS, ROOT, definitions
from .runner import measured_run, run_id, scenario


def inventory():
    cases = []
    for controller in ("preview", "preview_c32"):
        for ablation in ABLATIONS:
            cases.append(scenario(controller=controller, ablation=ablation))
            for fault, spec in definitions().items():
                for level in spec["levels"]:
                    for onset in spec["onsets_ms"]:
                        for seed in spec["seeds"]:
                            cases.append(scenario(controller, fault, level, onset, seed, ablation))
    assert len(cases) == 3564 and len({run_id(c) for c in cases}) == len(cases)
    return cases


def aggregate(rows):
    statuses = {r["verdict"]["status"] for r in rows}
    if not rows or "INVALID" in statuses:
        return "INVALID"
    return "FAIL" if "FAIL" in statuses else "PASS"


def select_levels(rows):
    result = {}
    for fault, spec in definitions().items():
        onset = 2000 if fault == "F5" else 2400
        chosen = spec["levels"][-1]
        for level in spec["levels"]:
            subset = [
                r
                for r in rows
                if r["scenario"]
                == {
                    **r["scenario"],
                    "controller": "preview",
                    "ablation": "baseline",
                    "fault": fault,
                    "level": level,
                    "onset_ms": onset,
                }
            ]
            if aggregate(subset) == "FAIL":
                chosen = level
                break
        result[fault] = {"level": chosen, "onset_ms": onset}
    return result


def identity_checks(rows):
    lookup = {run_id(r["scenario"]): r for r in rows}
    for row in rows:
        c = row["scenario"]
        expected = None
        if c["ablation"] == "no-noise":
            expected = {**c, "ablation": "baseline"}
        elif (
            (c["fault"] == "F2" and c["ablation"] == "no-dropped-frame-model")
            or (c["fault"] == "F3" and c["ablation"] == "no-jitter-model")
            or (c["fault"] == "F8" and c["ablation"] == "no-quantization")
            or (c["fault"] == "F4" and c["level"] == 1000)
            or (c["fault"] == "F7" and c["level"] == 100)
        ):
            expected = scenario(controller=c["controller"], ablation=c["ablation"])
        if expected is not None:
            target = lookup[run_id(expected)]
            passed = all(
                row[f"{stem}_sha256"] == target[f"{stem}_sha256"] for stem in ("trace", "truth")
            )
            row["identity_check"] = {"reference_run_id": target["run_id"], "passed": passed}
            if not passed:
                row["verdict"] = {"status": "INVALID", "reasons": ["identity invariant mismatch"]}


def task(args):
    return measured_run(*args)


def run_batch(cases, nominals, output, build, provenance, workers):
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                task, (c, output, build, nominals.get((c["controller"], c["ablation"])), provenance)
            ): c
            for c in cases
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            n = len(results)
            if n == 1 or n % 100 == 0 or n == len(cases):
                print(
                    json.dumps(
                        {
                            "completed": n,
                            "total": len(cases),
                            "last": result["run_id"],
                            "verdict": result["verdict"]["status"],
                        }
                    ),
                    flush=True,
                )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/c1"))
    parser.add_argument("--build", type=Path, default=Path("artifacts/c1-build"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    for env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        if os.environ.get(env) != "1":
            raise SystemExit(f"Set {env}=1 before running")
    relevant = ["c1", "faults", "sim", "firmware", "harness", "tools/build_controller.py"]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *relevant], cwd=ROOT):
        raise SystemExit("Commit all implementation/spec files before the full matrix")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = subprocess.check_output(
        ["git", "ls-files", "--", *relevant], cwd=ROOT, text=True
    ).splitlines()
    file_hashes = {p: sha256((ROOT / p).read_bytes()) for p in files}
    platform = platform_fingerprint()
    build = json.loads((args.build / "build.json").read_text(encoding="utf-8"))
    provenance = {
        "implementation_commit": commit,
        "registration_sha256": sha256((ROOT / "docs/C1_PREREG.md").read_bytes()),
        "source_inventory_sha256": sha256(canonical(file_hashes)),
        "platform_sha256": sha256(canonical(platform)),
        "c32_numerical_build_sha256": build["numerical_build_sha256"],
    }
    metadata = {
        "provenance": provenance,
        "platform_fingerprint": platform,
        "source_files": file_hashes,
        "controller_build": build,
        "registered_main_count": 3564,
        "registered_total_count": 3615,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "execution-manifest.json"
    if manifest.exists() and json.loads(manifest.read_text()) != metadata:
        raise SystemExit("Existing output provenance differs; preserve it and choose new output")
    manifest.write_bytes(canonical(metadata))
    cases = inventory()
    nominal_cases = [c for c in cases if c["fault"] == "none"]
    rows = run_batch(nominal_cases, {}, args.output, args.build, provenance, args.workers)
    nominal = {(r["scenario"]["controller"], r["scenario"]["ablation"]): r for r in rows}
    if any(r["verdict"]["status"] == "INVALID" for r in rows):
        raise SystemExit("Invalid nominal calibration; diagnose before fault matrix")
    rows += run_batch(
        [c for c in cases if c["fault"] != "none"],
        nominal,
        args.output,
        args.build,
        provenance,
        args.workers,
    )
    identity_checks(rows)
    selection = select_levels(rows)
    extra_controllers = ("lab_frame_pd", "delayed_feedback", "delayed_feedback_offsetfree")
    extra_nominals = run_batch(
        [scenario(controller=c) for c in extra_controllers],
        {},
        args.output,
        args.build,
        provenance,
        args.workers,
    )
    nominal.update({(r["scenario"]["controller"], "baseline"): r for r in extra_nominals})
    extra = []
    for controller in extra_controllers:
        for fault, spec in definitions().items():
            for seed in spec["seeds"]:
                chosen = selection[fault]
                extra.append(scenario(controller, fault, chosen["level"], chosen["onset_ms"], seed))
    rows += extra_nominals + run_batch(
        extra, nominal, args.output, args.build, provenance, args.workers
    )
    identity_checks(rows)
    rows.sort(key=lambda r: r["run_id"])
    assert len(rows) == 3615 and len({r["run_id"] for r in rows}) == 3615
    # Per-run evidence stays immutable; matrix adds derived identity assessments.
    result = {"schema": "c1-sil-v1", **metadata, "figure4_selection": selection, "runs": rows}
    data = canonical(result)
    (args.output / "matrix.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (args.output / "matrix.sha256").write_text(digest + "  matrix.json\n", encoding="ascii")
    print(
        json.dumps(
            {
                "matrix_sha256": digest,
                "run_count": len(rows),
                "identity_failures": sum(
                    not r.get("identity_check", {}).get("passed", True) for r in rows
                ),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
