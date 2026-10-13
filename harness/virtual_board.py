"""Managed C virtual board; same wire codec/control core, no fabricated timing."""

import json
import queue
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

from sim.run import REPO, sha256


@contextmanager
def launch(build, evidence):
    build = Path(build).resolve()
    metadata = json.loads((build / "build.json").read_text())
    executable = build / metadata["virtual"]["executable"]
    if sha256(executable.read_bytes()) != metadata["virtual"]["sha256"]:
        raise ValueError("virtual-board executable checksum mismatch")
    if metadata["virtual"]["numerical_build_sha256"] != metadata["numerical_build_sha256"]:
        raise ValueError("virtual-board numerical build mismatch")
    for name, expected in metadata["virtual"]["sources"].items():
        if sha256((REPO / name).read_bytes()) != expected:
            raise ValueError("stale virtual-board source")
    evidence.mkdir(parents=True, exist_ok=False)
    with (evidence / "stderr.log").open("wb") as errors:
        process = subprocess.Popen([str(executable)], stdout=subprocess.PIPE, stderr=errors)
        ready = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=lambda: ready.put(process.stdout.readline(256)), daemon=True
        )
        reader.start()
        try:
            try:
                line = ready.get(timeout=5)
            except queue.Empty as exc:
                raise ValueError("virtual board startup timeout") from exc
            (evidence / "startup.json").write_bytes(line)
            if not line.endswith(b"\n"):
                raise ValueError("invalid virtual-board startup response")
            port = json.loads(line)["port"]
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("invalid virtual-board port")
            yield f"127.0.0.1:{port}", metadata["virtual"]
            if process.wait(timeout=5):
                raise ValueError("virtual board session failed")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            reader.join(timeout=1)
            process.stdout.close()
