"""Interpolation helpers for the DataBridge."""

from __future__ import annotations

import math
from typing import Sequence


def loglog_interp(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Log-log linear interpolation — standard for photon cross-sections."""
    if x <= 0:
        raise ValueError("energy must be > 0")
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i, xi in enumerate(xs):
        if xi == x:
            return ys[i]
        if xi > x:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            if y0 <= 0 or y1 <= 0:
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
            lx0 = math.log(x0)
            lx1 = math.log(x1)
            ly0 = math.log(y0)
            ly1 = math.log(y1)
            t = (math.log(x) - lx0) / (lx1 - lx0)
            return math.exp(ly0 + t * (ly1 - ly0))
    return ys[-1]


def linear_interp_logx(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Linear interp in log(x), linear in y (for G-P coefficients)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i, xi in enumerate(xs):
        if xi == x:
            return ys[i]
        if xi > x:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            t = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0))
            return y0 + t * (y1 - y0)
    return ys[-1]
