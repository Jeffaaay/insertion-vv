import json

from sim.platform_info import platform_fingerprint
from tools.compare_traces import FULL_FINGERPRINT_KEYS


def test_full_fingerprint_has_stable_runtime_backend_and_no_machine_identifiers():
    first = platform_fingerprint()
    assert first == platform_fingerprint()
    assert first.keys() == FULL_FINGERPRINT_KEYS
    assert first["fingerprint_version"] == "2"
    assert first["cpu_model"] and first["os_release"] and first["os_version"]
    assert "AVX2=" in first["cpu_isa"] and "FMA3=" in first["cpu_isa"]
    backend = json.loads(first["blas_lapack"])
    assert set(backend["build"]) == {"blas", "lapack"}
    assert backend["runtime"]
    for library in backend["runtime"]:
        assert library["internal_api"] and library["version"]
        assert library["num_threads"] >= 1
    assert "filepath" not in first["blas_lapack"]
    assert "node" not in first and "hostname" not in first
