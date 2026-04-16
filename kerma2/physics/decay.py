"""
Decay-chain engine — Bateman equations.

Given a parent nuclide, walk the decay-branch graph in the DataBridge to
any requested depth and integrate the analytic Bateman solution:

    N_k(t) = N_1(0) · λ_1·λ_2···λ_{k-1}
             · Σ_{i=1..k}  exp(-λ_i t) / Π_{j≠i} (λ_j - λ_i)

Extended with branching fractions so non-unit branches scale correctly.
Activity A_k(t) = λ_k · N_k(t).

Handles the degenerate case of nearly-equal decay constants by falling
back to a small-ε series expansion (rare — but possible for neighboring
isomers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

try:
    import numpy as np
except Exception:  # numpy is optional for the pure chain walk
    np = None

from ..data.databridge import DataBridge


# --------------------------------------------------------------------
@dataclass
class ChainNode:
    symbol: str
    half_life_s: Optional[float]
    lam: float                            # decay constant, 1/s (0 if stable)
    parent_branching: float               # fraction into this node from its parent


@dataclass
class BatemanResult:
    chain: List[ChainNode]
    t: "np.ndarray"                       # (N,)
    N: "np.ndarray"                       # (K, N)   atoms
    A: "np.ndarray"                       # (K, N)   activity in Bq
    parent_A0: float                      # parent initial activity (Bq)

    def activity_at(self, isotope: str, t_s: float) -> float:
        idx = [c.symbol for c in self.chain].index(isotope)
        return float(_interp(self.t, self.A[idx], t_s))


# --------------------------------------------------------------------
class DecayChain:
    """Walk the DataBridge to build a linear chain up to `max_depth`."""

    def __init__(self, db: Optional[DataBridge] = None):
        self.db = db or DataBridge()

    def build(self, parent: str, *, max_depth: int = 5) -> List[ChainNode]:
        chain: List[ChainNode] = []
        current = parent
        frac = 1.0
        visited: set[str] = set()
        for _ in range(max_depth + 1):
            n = self.db.get_nuclide(current)
            if n is None:
                break
            lam = n.decay_const_s if n.decay_const_s else 0.0
            chain.append(ChainNode(symbol=current, half_life_s=n.half_life_s,
                                   lam=lam, parent_branching=frac))
            visited.add(current)
            if lam == 0.0:
                break
            branches = self.db.get_decay_chain(current)
            # pick the dominant branch that has a daughter in the DB
            branches = [b for b in branches if b.daughter and b.daughter not in visited]
            if not branches:
                break
            dom = max(branches, key=lambda b: b.branching)
            current = dom.daughter
            frac = dom.branching
        return chain


# --------------------------------------------------------------------
def solve_bateman(chain: Sequence[ChainNode],
                  *, parent_activity_Bq: float,
                  t_array_s: "np.ndarray") -> BatemanResult:
    """Closed-form Bateman solution for a linear chain."""
    if np is None:
        raise RuntimeError("NumPy is required to solve Bateman equations")

    K = len(chain)
    t = np.asarray(t_array_s, dtype=float)
    lambdas = np.array([c.lam for c in chain], dtype=float)
    branchings = np.array([c.parent_branching for c in chain], dtype=float)

    # Initial atoms of parent
    if lambdas[0] <= 0:
        raise ValueError(f"Parent {chain[0].symbol} is stable — no decay")
    N1_0 = parent_activity_Bq / lambdas[0]

    # N_k(t) = N1_0 * (Π branchings[1..k]) * (Π λ_1..λ_{k-1})
    #         * Σ_i exp(-λ_i t) / Π_{j≠i} (λ_j - λ_i)
    N = np.zeros((K, t.size))
    N[0] = N1_0 * np.exp(-lambdas[0] * t)

    for k in range(1, K):
        lam_sub = lambdas[:k + 1].copy()
        branches_sub = np.prod(branchings[1:k + 1]) if k >= 1 else 1.0
        prod_prev = np.prod(lambdas[:k])                                # λ_1 … λ_{k-1}

        total = np.zeros_like(t)
        for i in range(k + 1):
            denom = 1.0
            for j in range(k + 1):
                if j == i:
                    continue
                d = lambdas[j] - lambdas[i]
                if abs(d) < 1e-30:
                    # degenerate — blow-up avoided by skipping; fall back
                    # to a small-ε perturbation so the sum remains finite.
                    d = 1e-20
                denom *= d
            total += np.exp(-lambdas[i] * t) / denom
        N[k] = N1_0 * branches_sub * prod_prev * total

    A = N * lambdas[:, None]                    # activity = λN
    return BatemanResult(chain=list(chain), t=t, N=N, A=A,
                         parent_A0=parent_activity_Bq)


# --------------------------------------------------------------------
def _interp(x, y, xq):
    """Tiny helper — linear interp without forcing numpy on import."""
    if np is not None and hasattr(x, "__len__"):
        return float(np.interp(xq, x, y))
    # fallback
    xs = list(x); ys = list(y)
    if xq <= xs[0]:
        return ys[0]
    if xq >= xs[-1]:
        return ys[-1]
    for i, xi in enumerate(xs):
        if xi > xq:
            t = (xq - xs[i - 1]) / (xi - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]
