"""
Dosimetry — simple wrapper over DataBridge DCF lookups.

Typical Health-Physics use: "What's the effective dose from ingesting
3.7 kBq of Cs-137?"   →   Dosimetry(db).effective_dose("Cs-137",
pathway="ingestion", intake_Bq=3.7e3)
"""

from __future__ import annotations

from typing import Optional

from ..data.databridge import DataBridge, DataBridgeError


class Dosimetry:
    def __init__(self, db: Optional[DataBridge] = None):
        self.db = db or DataBridge()

    def effective_dose(self, nuclide: str, *, pathway: str, intake_Bq: float,
                       source: Optional[str] = None,
                       age_group: str = "adult") -> float:
        """Return effective dose in Sv."""
        rows = self.db.get_dcf(nuclide, pathway=pathway, source=source,
                               target="effective", age_group=age_group)
        if not rows:
            raise DataBridgeError(
                f"No DCF for {nuclide} / {pathway} / effective / {age_group}")
        # prefer the most recent source
        pri = {"ICRP119": 3, "ICRP116": 2, "FGR13": 2, "FGR12": 1, "FGR11": 1}
        rows.sort(key=lambda r: pri.get(r["source"], 0), reverse=True)
        return rows[0]["value"] * intake_Bq
