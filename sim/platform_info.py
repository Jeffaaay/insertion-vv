"""Read-only numerical-platform provenance; never changes dispatch or thread limits."""

import json
import platform
from pathlib import Path

import mujoco
import numpy as np
from threadpoolctl import threadpool_info


def cpu_model() -> str:
    if platform.system() == "Windows":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    if platform.system() == "Linux":
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith(("model name", "hardware")) and ":" in line:
                return line.split(":", 1)[1].strip()
    model = platform.processor().strip()
    if not model:
        raise RuntimeError("Cannot determine CPU model for the determinism fingerprint")
    return model


def platform_fingerprint() -> dict[str, str]:
    machine = platform.machine().lower()
    architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    # These are the same detected CPU flags used by numpy.show_runtime(). NumPy
    # is pinned; read them only, without editing dispatch or performing QR work.
    from numpy._core._multiarray_umath import __cpu_features__

    features = ",".join(f"{key}={int(value)}" for key, value in sorted(__cpu_features__.items()))
    config = np.show_config(mode="dicts")["Build Dependencies"]
    builds = {
        name: {key: config[name].get(key) for key in ("name", "version", "openblas configuration")}
        for name in ("blas", "lapack")
    }
    backends = [
        {
            key: library.get(key)
            for key in ("internal_api", "version", "architecture", "threading_layer", "num_threads")
        }
        for library in threadpool_info()
        if library["user_api"] == "blas"
    ]
    if not backends:
        raise RuntimeError("Cannot determine loaded BLAS backend for the determinism fingerprint")
    backends.sort(key=lambda value: json.dumps(value, sort_keys=True))
    return {
        "fingerprint_version": "2",
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": architecture,
        "cpu_model": cpu_model(),
        "cpu_isa": features,
        "blas_lapack": json.dumps({"build": builds, "runtime": backends}, sort_keys=True),
        "python": platform.python_version(),
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
    }
