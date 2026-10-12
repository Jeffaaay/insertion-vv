"""Time-only task schedule, independent of the plant and tissue waveform."""


def _smooth(start: float, end: float, u: float, duration_s: float) -> tuple[float, float]:
    blend = u * u * (3 - 2 * u)
    speed = (end - start) * 6 * u * (1 - u) / duration_s
    return start + (end - start) * blend, speed


def reference(time_us: int, initial: float, hover: float, depth: float) -> tuple[float, float]:
    """Return desired gap and velocity; z up, negative gap means penetration."""
    t = time_us / 1e6
    if t < 1:
        return _smooth(initial, hover, t, 1)
    if t < 2:
        return hover, 0.0
    if t < 2.5:
        return _smooth(hover, -depth, (t - 2) / 0.5, 0.5)
    return -depth, 0.0
