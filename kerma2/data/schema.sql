-- ======================================================================
-- Kerma Nuclear Data Warehouse — SQLite Schema
-- ======================================================================
-- Sources (when fully populated):
--   * ICRP 107 — Nuclear Decay Data for Dosimetric Calculations
--   * NIST XCOM — Photon Cross-Sections Database
--   * ICRP 116 — External Radiation Dose Conversion Coefficients
--   * ICRP 119 — Compendium of Dose Coefficients
--   * FGR 11 / 12 / 13 — EPA Federal Guidance Reports
-- ======================================================================

PRAGMA foreign_keys = ON;

-- ─── Nuclides ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS nuclide (
    nuclide_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL UNIQUE,     -- e.g. "Cs-137"
    element         TEXT NOT NULL,            -- "Cs"
    Z               INTEGER NOT NULL,         -- atomic number
    A               INTEGER NOT NULL,         -- mass number
    meta_state      TEXT DEFAULT '',          -- 'm', 'm1', ...
    half_life_s     REAL,                     -- half-life in seconds (NULL = stable)
    decay_const_s   REAL,                     -- λ = ln(2)/T½
    atomic_mass_u   REAL,
    q_value_MeV     REAL,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_nuclide_symbol ON nuclide(symbol);

-- ─── Decay branches (parent → daughter with branching fractions) ─────
CREATE TABLE IF NOT EXISTS decay_branch (
    branch_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id       INTEGER NOT NULL REFERENCES nuclide(nuclide_id),
    daughter_id     INTEGER REFERENCES nuclide(nuclide_id),  -- nullable if stable / off-chart
    mode            TEXT NOT NULL,            -- 'B-', 'B+', 'EC', 'A', 'IT', 'SF', ...
    branching       REAL NOT NULL,            -- fraction 0..1
    q_value_MeV     REAL
);
CREATE INDEX IF NOT EXISTS idx_branch_parent ON decay_branch(parent_id);

-- ─── Photon emissions per nuclide (gamma / x-ray lines) ──────────────
CREATE TABLE IF NOT EXISTS emission (
    emission_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nuclide_id      INTEGER NOT NULL REFERENCES nuclide(nuclide_id),
    radiation_type  TEXT NOT NULL,            -- 'G' gamma, 'X' x-ray, 'AE' auger, 'B-', 'B+', 'A', 'CE'
    energy_MeV      REAL NOT NULL,
    yield_per_decay REAL NOT NULL,            -- intensity / decay
    uncertainty     REAL
);
CREATE INDEX IF NOT EXISTS idx_emission_nuc ON emission(nuclide_id);

-- ─── Materials for attenuation (elements, mixtures, alloys) ──────────
CREATE TABLE IF NOT EXISTS material (
    material_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,     -- "Lead", "Concrete (NBS)", "Water, Liquid"
    symbol          TEXT,                     -- "Pb" for pure elements
    density_g_cm3   REAL NOT NULL,
    Z_eff           REAL,
    A_eff           REAL,
    composition     TEXT,                     -- JSON: {"Pb":1.0} or {"H":0.111,"O":0.889}
    category        TEXT,                     -- 'element' | 'mixture' | 'alloy'
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_material_name ON material(name);

-- ─── NIST XCOM mass-attenuation coefficients ─────────────────────────
CREATE TABLE IF NOT EXISTS xcom (
    xcom_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id     INTEGER NOT NULL REFERENCES material(material_id),
    energy_MeV      REAL NOT NULL,
    mu_over_rho     REAL NOT NULL,            -- cm²/g total mass-attenuation
    mu_en_over_rho  REAL,                     -- mass energy-absorption (μ_en/ρ)
    UNIQUE(material_id, energy_MeV)
);
CREATE INDEX IF NOT EXISTS idx_xcom_mat ON xcom(material_id);

-- ─── ANSI / ANS-6.4.3 G-P Buildup-factor coefficients ────────────────
CREATE TABLE IF NOT EXISTS gp_buildup (
    gp_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id     INTEGER NOT NULL REFERENCES material(material_id),
    energy_MeV      REAL NOT NULL,
    b               REAL NOT NULL,
    c               REAL NOT NULL,
    a               REAL NOT NULL,
    X_k             REAL NOT NULL,
    d               REAL NOT NULL,
    UNIQUE(material_id, energy_MeV)
);
CREATE INDEX IF NOT EXISTS idx_gp_mat ON gp_buildup(material_id);

-- ─── Dose Conversion Factors ─────────────────────────────────────────
-- Unified table for FGR 11/12/13 and ICRP 116/119 coefficients.
CREATE TABLE IF NOT EXISTS dcf (
    dcf_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nuclide_id      INTEGER REFERENCES nuclide(nuclide_id),
    source          TEXT NOT NULL,            -- 'FGR11', 'FGR12', 'FGR13', 'ICRP116', 'ICRP119'
    pathway         TEXT NOT NULL,            -- 'inhalation', 'ingestion', 'submersion',
                                              -- 'ground', 'water', 'soil', 'external_AP', ...
    target          TEXT,                     -- 'whole_body', 'thyroid', 'lung', ...
    age_group       TEXT,                     -- 'adult','infant','1y','5y','10y','15y'
    value           REAL NOT NULL,            -- coefficient
    unit            TEXT NOT NULL,            -- 'Sv/Bq', 'Sv m3 / Bq s', 'Sv/(Bq s/m2)', ...
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_dcf_nuc ON dcf(nuclide_id);
CREATE INDEX IF NOT EXISTS idx_dcf_path ON dcf(pathway);

-- ─── Metadata ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);
