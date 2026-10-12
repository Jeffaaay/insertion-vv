"""Truth-only evaluation; registered contract is loaded before simulation."""

import json
import math
from pathlib import Path

import numpy as np

CONTRACT_PATH = Path(__file__).with_name("verdict_contract.json")
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def window_metrics(rows: list[dict], start: int, end: int) -> dict:
    selected = [r for r in rows if start <= r["time_us"] < end]
    if not selected:
        return {
            "samples": 0,
            "rms_e_um": None,
            "peak_abs_edot_mm_s": None,
            "peak_contact_force_mn": None,
        }
    e = np.asarray([r["e_m"] for r in selected])
    edot = np.asarray([r["edot_m_s"] for r in selected])
    force = np.asarray([r["contact_force_n"] for r in selected])
    return {
        "samples": len(selected),
        "rms_e_um": float(np.sqrt(np.mean(e * e)) * 1e6),
        "peak_abs_edot_mm_s": float(np.max(np.abs(edot)) * 1e3),
        "peak_contact_force_mn": float(np.max(force) * 1e3),
    }


def verdict(contact: dict, *, complete: bool, reproducible: bool, safety_stop: bool) -> dict:
    values = [contact.get(k) for k in ("rms_e_um", "peak_abs_edot_mm_s", "peak_contact_force_mn")]
    if (
        not complete
        or not reproducible
        or not contact.get("samples")
        or any(v is None or not math.isfinite(v) for v in values)
    ):
        return {
            "status": "INVALID",
            "reasons": ["incomplete, missing, nonfinite, or unverified data"],
        }
    reasons = []
    if contact["rms_e_um"] >= CONTRACT["contact_rms_e_um_strictly_less_than"]:
        reasons.append("contact_rms_e_um >= 20")
    if contact["peak_abs_edot_mm_s"] >= CONTRACT["contact_peak_abs_edot_mm_s_strictly_less_than"]:
        reasons.append("contact_peak_abs_edot_mm_s >= 2")
    if safety_stop:
        reasons.append("safety_stop")
    return {"status": "FAIL" if reasons else "PASS", "reasons": reasons}
