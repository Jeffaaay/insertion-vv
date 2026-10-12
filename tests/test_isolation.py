import ast
from dataclasses import fields, replace
from pathlib import Path

from sim.contracts import Sensors
from sim.controllers import LabFramePD


def test_controller_modules_have_no_truth_or_plant_dependencies():
    root = Path(__file__).resolve().parents[1] / "sim"
    allowed = {"dataclasses", "contracts", "reference"}
    for name in ("controllers.py", "contracts.py", "reference.py", "preview.py"):
        module_allowed = (
            allowed | {"math", "numpy", "controllers"} if name == "preview.py" else allowed
        )
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in module_allowed
            if isinstance(node, ast.Import):
                assert all(alias.name in module_allowed for alias in node.names)
            if isinstance(node, ast.Name):
                assert node.id not in {"Truth", "MujocoPlant", "eval", "exec", "__import__"}
    assert {f.name for f in fields(Sensors)} == {
        "tick",
        "time_us",
        "needle_z_m",
        "needle_v_m_s",
        "surface_z_m",
        "surface_sample_time_us",
        "surface_sequence",
        "surface_fresh",
    }


def test_lab_frame_controller_ignores_surface_measurements():
    controller = LabFramePD(400, 0.8, 0.001, 0.0005, 0.0003)
    sensors = Sensors(4000, 4_000_000, -0.0002, 0, None, None, None, False)
    changed = replace(
        sensors,
        surface_z_m=100,
        surface_sample_time_us=3_985_000,
        surface_sequence=100,
        surface_fresh=True,
    )
    assert controller.command(sensors) == controller.command(changed)
