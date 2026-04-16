"""
DataBridge — single point of access to the Kerma Nuclear Data Warehouse.

The warehouse is a local SQLite database (`nuclear.db`). By default it is
stored inside this package directory; if that location is not writable
(read-only install, OneDrive lock, etc.), it falls back to a per-user
cache directory (`%LOCALAPPDATA%\\Kerma` on Windows, `~/.cache/Kerma`
elsewhere).

It is built lazily on first use from the seed loaders in
`kerma2.data.loaders`, so the user never has to supply their own data
files for standard Health Physics work.

Usage
-----
>>> from kerma2.data import DataBridge
>>> db = DataBridge()                       # opens / creates nuclear.db
>>> db.get_attenuation("Lead", 0.662)       # → μ/ρ (cm²/g) at 662 keV
0.1084...
>>> db.get_half_life("Cs-137")              # seconds
949062000.0
>>> db.get_emissions("Co-60")
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------
# Dataclasses for public return types
# --------------------------------------------------------------------
@dataclass(frozen=True)
class Nuclide:
    symbol: str
    Z: int
    A: int
    meta: str
    half_life_s: Optional[float]
    decay_const_s: Optional[float]
    atomic_mass_u: Optional[float]
    q_value_MeV: Optional[float]


@dataclass(frozen=True)
class Emission:
    radiation_type: str
    energy_MeV: float
    yield_per_decay: float


@dataclass(frozen=True)
class DecayBranch:
    mode: str
    daughter: Optional[str]
    branching: float
    q_value_MeV: Optional[float]


@dataclass(frozen=True)
class Material:
    name: str
    symbol: Optional[str]
    density_g_cm3: float
    Z_eff: Optional[float]
    composition: Dict[str, float]
    category: str


# --------------------------------------------------------------------
class DataBridgeError(Exception):
    pass


# --------------------------------------------------------------------
# Path helpers (module-level so tests / facade can reuse them)
# --------------------------------------------------------------------
def _user_cache_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "Kerma"


def _bundled_path() -> Path:
    return Path(__file__).with_name("nuclear.db")


def _pick_default_path() -> Path:
    """Prefer the bundled location; else fall back to a user-cache dir."""
    bundled = _bundled_path()
    try:
        bundled.parent.mkdir(parents=True, exist_ok=True)
        probe = bundled.parent / ".kerma_write_probe"
        with open(probe, "wb") as f:
            f.write(b"ok")
            f.flush()
            os.fsync(f.fileno())
        os.remove(probe)
        # Probe SQLite compatibility — OneDrive sometimes allows writes
        # but breaks sqlite's file-locking. Open a scratch DB nearby:
        scratch = bundled.parent / ".kerma_sqlite_probe"
        try:
            c = sqlite3.connect(scratch)
            c.execute("CREATE TABLE IF NOT EXISTS t(x INTEGER)")
            c.commit()
            c.close()
        finally:
            try:
                os.remove(scratch)
            except FileNotFoundError:
                pass
        return bundled
    except Exception:
        cache = _user_cache_dir()
        cache.mkdir(parents=True, exist_ok=True)
        return cache / "nuclear.db"


# --------------------------------------------------------------------
class DataBridge:
    """Thread-safe SQLite accessor with auto-seeding and log-log interpolation."""

    DEFAULT_DB_PATH = _bundled_path()

    def __init__(self, db_path: Optional[os.PathLike] = None, *, autoseed: bool = True):
        self.db_path = Path(db_path) if db_path else _pick_default_path()
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

        needs_seed = not self.db_path.exists()
        try:
            self._open()
        except sqlite3.OperationalError:
            # Retry from user cache
            self.db_path = _user_cache_dir() / "nuclear.db"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            needs_seed = not self.db_path.exists()
            self._open()

        if needs_seed and autoseed:
            self.rebuild(verbose=False)

    # ---- connection management -------------------------------------
    def _open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_path, check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self._conn.executescript(schema)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- housekeeping ----------------------------------------------
    def rebuild(self, *, verbose: bool = False) -> None:
        from .loaders import seed_all
        with self._lock:
            assert self._conn is not None
            c = self._conn
            for table in ("dcf", "gp_buildup", "xcom", "emission",
                          "decay_branch", "nuclide", "material", "meta"):
                c.execute(f"DELETE FROM {table}")
            c.commit()
            seed_all(c, verbose=verbose)
            c.commit()

    def meta(self, key: str) -> Optional[str]:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    # ─── Nuclide lookups ────────────────────────────────────────────
    def get_nuclide(self, symbol: str) -> Optional[Nuclide]:
        row = self._conn.execute(
            "SELECT * FROM nuclide WHERE symbol=? COLLATE NOCASE", (symbol,)
        ).fetchone()
        if not row:
            return None
        return Nuclide(
            symbol=row["symbol"], Z=row["Z"], A=row["A"],
            meta=row["meta_state"] or "",
            half_life_s=row["half_life_s"], decay_const_s=row["decay_const_s"],
            atomic_mass_u=row["atomic_mass_u"], q_value_MeV=row["q_value_MeV"],
        )

    def get_half_life(self, symbol: str) -> float:
        n = self.get_nuclide(symbol)
        if n is None:
            raise DataBridgeError(f"Unknown nuclide: {symbol}")
        if n.half_life_s is None:
            raise DataBridgeError(f"{symbol} is stable (no half-life)")
        return n.half_life_s

    def get_decay_constant(self, symbol: str) -> float:
        n = self.get_nuclide(symbol)
        if n is None or n.decay_const_s is None:
            raise DataBridgeError(f"No decay constant for {symbol}")
        return n.decay_const_s

    def get_emissions(self, symbol: str, *, radiation: Optional[str] = None) -> List[Emission]:
        nid = self._nuclide_id(symbol)
        q = "SELECT radiation_type,energy_MeV,yield_per_decay FROM emission WHERE nuclide_id=?"
        params: list = [nid]
        if radiation:
            q += " AND radiation_type=?"
            params.append(radiation)
        q += " ORDER BY yield_per_decay DESC"
        return [Emission(r["radiation_type"], r["energy_MeV"], r["yield_per_decay"])
                for r in self._conn.execute(q, params).fetchall()]

    def get_decay_chain(self, symbol: str) -> List[DecayBranch]:
        nid = self._nuclide_id(symbol)
        rows = self._conn.execute(
            """SELECT db.mode, n.symbol AS daughter, db.branching, db.q_value_MeV
               FROM decay_branch db
               LEFT JOIN nuclide n ON n.nuclide_id = db.daughter_id
               WHERE db.parent_id = ?""", (nid,)
        ).fetchall()
        return [DecayBranch(r["mode"], r["daughter"], r["branching"], r["q_value_MeV"])
                for r in rows]

    def list_nuclides(self) -> List[str]:
        return [r["symbol"] for r in self._conn.execute(
            "SELECT symbol FROM nuclide ORDER BY symbol").fetchall()]

    # ─── Material / attenuation lookups ─────────────────────────────
    def get_material(self, name: str) -> Optional[Material]:
        row = self._conn.execute(
            "SELECT * FROM material WHERE name=? COLLATE NOCASE OR symbol=? COLLATE NOCASE",
            (name, name)
        ).fetchone()
        if not row:
            return None
        try:
            comp = json.loads(row["composition"]) if row["composition"] else {}
        except (TypeError, json.JSONDecodeError):
            comp = {}
        return Material(
            name=row["name"], symbol=row["symbol"],
            density_g_cm3=row["density_g_cm3"], Z_eff=row["Z_eff"],
            composition=comp, category=row["category"] or "",
        )

    def list_materials(self) -> List[str]:
        return [r["name"] for r in self._conn.execute(
            "SELECT name FROM material ORDER BY name").fetchall()]

    def get_attenuation(self, material: str, energy_MeV: float, *,
                        kind: str = "mu_over_rho") -> float:
        if kind not in ("mu_over_rho", "mu_en_over_rho"):
            raise ValueError("kind must be 'mu_over_rho' or 'mu_en_over_rho'")
        mid = self._material_id(material)
        rows = self._conn.execute(
            f"SELECT energy_MeV, {kind} FROM xcom "
            f"WHERE material_id=? AND {kind} IS NOT NULL "
            f"ORDER BY energy_MeV", (mid,)
        ).fetchall()
        if not rows:
            raise DataBridgeError(f"No {kind} data for material '{material}'")
        xs = [r["energy_MeV"] for r in rows]
        ys = [r[kind] for r in rows]
        return _loglog_interp(energy_MeV, xs, ys)

    def get_linear_attenuation(self, material: str, energy_MeV: float) -> float:
        mat = self.get_material(material)
        if mat is None:
            raise DataBridgeError(f"Unknown material: {material}")
        return self.get_attenuation(material, energy_MeV) * mat.density_g_cm3

    def get_gp_coefficients(self, material: str,
                            energy_MeV: float) -> Tuple[float, float, float, float, float]:
        mid = self._material_id(material)
        rows = self._conn.execute(
            "SELECT energy_MeV,b,c,a,X_k,d FROM gp_buildup WHERE material_id=? ORDER BY energy_MeV",
            (mid,)
        ).fetchall()
        if not rows:
            raise DataBridgeError(f"No G-P buildup coefficients for '{material}'")
        energies = [r["energy_MeV"] for r in rows]
        def interp(col: str) -> float:
            return _linear_interp_logx(energy_MeV, energies, [r[col] for r in rows])
        return (interp("b"), interp("c"), interp("a"), interp("X_k"), interp("d"))

    # ─── Dose Conversion Factors ────────────────────────────────────
    def get_dcf(self, nuclide: str, *, pathway: str,
                source: Optional[str] = None, target: Optional[str] = None,
                age_group: Optional[str] = None) -> List[Dict[str, Any]]:
        nid = self._nuclide_id(nuclide)
        q = ("SELECT source,pathway,target,age_group,value,unit,notes "
             "FROM dcf WHERE nuclide_id=? AND pathway=?")
        params: list = [nid, pathway]
        if source:    q += " AND source=?";    params.append(source)
        if target:    q += " AND target=?";    params.append(target)
        if age_group: q += " AND age_group=?"; params.append(age_group)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    # ─── internal helpers ───────────────────────────────────────────
    def _nuclide_id(self, symbol: str) -> int:
        row = self._conn.execute(
            "SELECT nuclide_id FROM nuclide WHERE symbol=? COLLATE NOCASE", (symbol,)
        ).fetchone()
        if not row:
            raise DataBridgeError(f"Unknown nuclide: {symbol}")
        return row["nuclide_id"]

    def _material_id(self, name: str) -> int:
        row = self._conn.execute(
            "SELECT material_id FROM material WHERE name=? COLLATE NOCASE OR symbol=? COLLATE NOCASE",
            (name, name)
        ).fetchone()
        if not row:
            raise DataBridgeError(f"Unknown material: {name}")
        return row["material_id"]

    def sql(self, query: str, params: Sequence = ()) -> List[sqlite3.Row]:
        if not query.strip().lower().startswith("select"):
            raise DataBridgeError("Only SELECT queries allowed through .sql()")
        return list(self._conn.execute(query, params).fetchall())


# Interpolation helpers live in a sibling module to keep this file small
from ._interp import loglog_interp as _loglog_interp
from ._interp import linear_interp_logx as _linear_interp_logx
