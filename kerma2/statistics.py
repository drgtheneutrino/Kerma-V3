"""
Kerma Statistics — radiation-counting and general-purpose statistical tests.

This module is oriented around the day-to-day problems of a Health Physicist:
counting statistics (Poisson, binomial), detection limits (Currie, MARLAP),
instrument quality-control (chi-squared, control charts), and classical
hypothesis testing used in calibration / intercomparison work.

All public functions return plain dataclasses or floats so they are trivially
serialisable from the notebook. Where appropriate we expose BOTH a classical
(normal-approximation) form and the exact/small-count form — the former is
what MARLAP actually recommends, but the exact form is included for audit
and teaching.

References
----------
* MARLAP (2004), Multi-Agency Radiological Laboratory Analytical Protocols
* Currie, L.A. (1968), Anal. Chem. 40, 586
* Knoll, G.F. (2010), Radiation Detection and Measurement, 4e
* NCRP 58 (1985), A Handbook of Radioactivity Measurements Procedures
* ISO 11929 (2019), Determination of the characteristic limits
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


# ──────────────────────────────────────────────────────────────────────
#  Low-level distributional helpers (no SciPy dependency)
# ──────────────────────────────────────────────────────────────────────
_SQRT2 = math.sqrt(2.0)

def _norm_cdf(z: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + math.erf(z / _SQRT2))

def _norm_sf(z: float) -> float:
    return 1.0 - _norm_cdf(z)

def _norm_ppf(p: float) -> float:
    """Inverse normal CDF — Beasley-Springer-Moro."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie in (0, 1)")
    # Acklam 2003 rational approximation
    a = [-3.969683028665376e+01,  2.209460984245205e+02,
         -2.759285104469687e+02,  1.383577518672690e+02,
         -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02,
         -1.556989798598866e+02,  6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
          4.374664141464968e+00,  2.938163982698783e+00]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,
          2.445134137142996e+00,  3.754408661907416e+00]
    plow  = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _chi2_sf(x: float, k: int) -> float:
    """Upper-tail survival function of χ²(k). Regularized upper incomplete Γ.

    χ²(k) survival at x equals Q(k/2, x/2), so we scale x by ½ before running
    the usual NR §6.2 incomplete-gamma kernel.
    """
    if x <= 0:
        return 1.0
    # Q(a, x/2): χ² density is Γ(k/2, 2) so sf(x) = Q(k/2, x/2).
    x = x / 2.0
    a = k / 2.0
    if x < a + 1:
        # series
        ap, sum_, del_ = a, 1.0/a, 1.0/a
        for _ in range(200):
            ap += 1.0
            del_ *= x / ap
            sum_ += del_
            if abs(del_) < abs(sum_) * 1e-12:
                break
        return 1.0 - sum_ * math.exp(-x + a*math.log(x) - math.lgamma(a))
    # continued fraction
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300: d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300: c = 1e-300
        d = 1.0 / d
        dlt = d * c
        h *= dlt
        if abs(dlt - 1.0) < 1e-12:
            break
    return math.exp(-x + a*math.log(x) - math.lgamma(a)) * h


def _chi2_ppf(p: float, k: int) -> float:
    """Inverse χ²(k) CDF — Wilson-Hilferty + one Newton step."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie in (0, 1)")
    z = _norm_ppf(p)
    # Wilson-Hilferty
    x = k * (1.0 - 2.0/(9*k) + z*math.sqrt(2.0/(9*k)))**3
    # one bisection refinement in case of small k
    lo, hi = 1e-6, max(x*4, 50.0)
    for _ in range(60):
        mid = 0.5*(lo+hi)
        if 1.0 - _chi2_sf(mid, k) < p: lo = mid
        else: hi = mid
    return 0.5*(lo+hi)


def _poisson_sf(k: int, mu: float) -> float:
    """P(X ≥ k) for X ~ Poisson(µ)."""
    if k <= 0:
        return 1.0
    # relation to chi-squared: P(X ≥ k | µ) = P(χ²(2k) ≤ 2µ)
    return 1.0 - _chi2_sf(2*mu, 2*k)

def _poisson_cdf(k: int, mu: float) -> float:
    return 1.0 - _poisson_sf(k+1, mu)


def _student_t_sf(t: float, df: float) -> float:
    """Upper tail of Student-t via incomplete beta."""
    x = df / (df + t*t)
    # regularized incomplete beta I_x(df/2, 1/2) — Press NR §6.4
    a, b = df/2.0, 0.5
    if x == 0 or x == 1:
        bt = 0.0
    else:
        bt = math.exp(math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
                      + a*math.log(x) + b*math.log(1.0-x))
    # continued fraction
    if x < (a+1)/(a+b+2):
        # I_x via CF on x
        qab, qap, qam = a+b, a+1.0, a-1.0
        c, d = 1.0, 1.0 - qab*x/qap
        if abs(d) < 1e-30: d = 1e-30
        d = 1.0/d; h = d
        for m in range(1, 200):
            m2 = 2*m
            aa = m*(b-m)*x/((qam+m2)*(a+m2))
            d = 1.0 + aa*d
            if abs(d) < 1e-30: d = 1e-30
            c = 1.0 + aa/c
            if abs(c) < 1e-30: c = 1e-30
            d = 1.0/d; h *= d*c
            aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
            d = 1.0 + aa*d
            if abs(d) < 1e-30: d = 1e-30
            c = 1.0 + aa/c
            if abs(c) < 1e-30: c = 1e-30
            d = 1.0/d; dlt = d*c; h *= dlt
            if abs(dlt-1.0) < 1e-12: break
        I = bt*h/a
    else:
        I = 1.0 - _student_t_sf_flip(1.0-x, b, a, bt)
    # Two-sided version: caller divides/multiplies by 2 as needed
    p = 0.5 * I
    return p if t > 0 else 1.0 - p

def _student_t_sf_flip(x, a, b, bt):
    # helper mirroring of the CF, used above
    qab, qap, qam = a+b, a+1.0, a-1.0
    c, d = 1.0, 1.0 - qab*x/qap
    if abs(d) < 1e-30: d = 1e-30
    d = 1.0/d; h = d
    for m in range(1, 200):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1.0 + aa*d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa/c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0/d; h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1.0 + aa*d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa/c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0/d; dlt = d*c; h *= dlt
        if abs(dlt-1.0) < 1e-12: break
    return bt*h/a


# ══════════════════════════════════════════════════════════════════════
#  Public result dataclasses
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class TestResult:
    """Classical hypothesis-test result — mirrors scipy's namedtuples."""
    statistic: float
    p_value:   float
    reject_null: bool
    note: str = ""

    def __repr__(self) -> str:
        return (f"TestResult(stat={self.statistic:.4g}, p={self.p_value:.4g}, "
                f"reject_H0={self.reject_null})")


@dataclass(frozen=True)
class DetectionLimits:
    """Critical level L_C, detection limit L_D, quantification limit L_Q.
    All in *counts* unless the caller supplied a count-rate and conversion."""
    L_C: float
    L_D: float
    L_Q: float
    method: str
    k_alpha: float
    k_beta:  float


@dataclass(frozen=True)
class ConfidenceInterval:
    low: float
    high: float
    level: float

    def contains(self, x: float) -> bool:
        return self.low <= x <= self.high

    def __repr__(self) -> str:
        return f"CI[{self.level:.0%}]({self.low:.4g}, {self.high:.4g})"


# ══════════════════════════════════════════════════════════════════════
#  1.  Counting statistics — Poisson / binomial
# ══════════════════════════════════════════════════════════════════════
def poisson_ci(counts: int, level: float = 0.95) -> ConfidenceInterval:
    """Exact (Garwood) two-sided confidence interval for a Poisson mean."""
    if counts < 0:
        raise ValueError("counts must be ≥ 0")
    alpha = 1.0 - level
    lo = 0.0 if counts == 0 else 0.5 * _chi2_ppf(alpha/2, 2*counts)
    hi = 0.5 * _chi2_ppf(1 - alpha/2, 2*(counts + 1))
    return ConfidenceInterval(lo, hi, level)


def poisson_test(observed: int, expected: float, *, alpha: float = 0.05,
                 alternative: str = "two-sided") -> TestResult:
    """Exact test H₀: λ = expected vs observed counts.

    `alternative` ∈ {"two-sided", "greater", "less"}.
    """
    if expected <= 0:
        raise ValueError("expected must be > 0")
    if alternative == "greater":
        p = _poisson_sf(observed, expected)
    elif alternative == "less":
        p = _poisson_cdf(observed, expected)
    else:
        # two-sided — method of small p-value (Kim 2006)
        p_right = _poisson_sf(observed, expected)
        p_left  = _poisson_cdf(observed, expected)
        p = min(1.0, 2.0 * min(p_right, p_left))
    return TestResult(observed, p, p < alpha,
                      note=f"Poisson exact · H1={alternative}")


def binomial_ci(successes: int, n: int, level: float = 0.95,
                method: str = "wilson") -> ConfidenceInterval:
    """Wilson-score (default) or Clopper-Pearson CI."""
    if n <= 0 or successes < 0 or successes > n:
        raise ValueError("bad inputs")
    alpha = 1.0 - level
    z = _norm_ppf(1 - alpha/2)
    if method == "wilson":
        p̂ = successes / n
        denom = 1 + z*z/n
        centre = (p̂ + z*z/(2*n)) / denom
        half   = z*math.sqrt(p̂*(1-p̂)/n + z*z/(4*n*n)) / denom
        return ConfidenceInterval(max(0, centre-half), min(1, centre+half), level)
    elif method == "clopper-pearson":
        lo = 0.0 if successes == 0 else _beta_ppf(alpha/2, successes, n-successes+1)
        hi = 1.0 if successes == n else _beta_ppf(1-alpha/2, successes+1, n-successes)
        return ConfidenceInterval(lo, hi, level)
    raise ValueError(f"unknown method: {method}")


def _beta_ppf(p, a, b):
    # quick bisection — adequate for CI work
    lo, hi = 0.0, 1.0
    for _ in range(80):
        m = 0.5*(lo+hi)
        # regularised incomplete beta via relation to F
        if _beta_cdf(m, a, b) < p: lo = m
        else: hi = m
    return 0.5*(lo+hi)

def _beta_cdf(x, a, b):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
                  + a*math.log(x) + b*math.log(1.0-x))
    if x < (a+1)/(a+b+2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0-x) / b

def _betacf(a, b, x):
    qab, qap, qam = a+b, a+1.0, a-1.0
    c, d = 1.0, 1.0 - qab*x/qap
    if abs(d) < 1e-30: d = 1e-30
    d = 1.0/d; h = d
    for m in range(1, 200):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1.0 + aa*d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa/c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0/d; h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1.0 + aa*d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa/c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0/d; dlt = d*c; h *= dlt
        if abs(dlt-1.0) < 1e-12: break
    return h


# ══════════════════════════════════════════════════════════════════════
#  2.  Detection limits — Currie L_C/L_D/L_Q and MARLAP/ISO 11929 variants
# ══════════════════════════════════════════════════════════════════════
def currie_limits(background_counts: float, *,
                  k_alpha: float = 1.645, k_beta: float = 1.645,
                  quant_k: float = 10.0) -> DetectionLimits:
    """Classical Currie (1968) paired-count detection limits (net counts).

    L_C = k_α √(2B)
    L_D = k_α² + 2 k_α √(2B)      (for k_α = k_β, approx)
    L_Q = quant_k · σ_Q  with σ_Q ≈ √(2B)
    """
    B = max(0.0, background_counts)
    sigma_B = math.sqrt(2.0 * B)
    L_C = k_alpha * sigma_B
    if k_alpha == k_beta:
        L_D = k_alpha*k_alpha + 2.0*k_alpha*sigma_B
    else:
        L_D = (k_alpha + k_beta) * sigma_B + k_alpha*k_beta
    L_Q = quant_k * sigma_B
    return DetectionLimits(L_C, L_D, L_Q, method="Currie-1968",
                           k_alpha=k_alpha, k_beta=k_beta)


def mda(background_cpm: float, count_time_min: float,
        efficiency: float = 1.0, yield_: float = 1.0,
        *, k: float = 1.645) -> float:
    """Minimum Detectable Activity (Bq). Matches MARLAP Eq. 20.74
    for paired counts with equal sample/background times."""
    B = background_cpm * count_time_min          # background counts
    net = 2.71 + 4.65 * k * math.sqrt(B) / 1.645  # Currie net counts at k=1.645
    if k != 1.645:
        net = k*k + 2.0*k*math.sqrt(2.0*B)
    cps_to_Bq = 60.0 / (count_time_min * efficiency * yield_)
    return net * cps_to_Bq / 60.0


def iso11929_decision_threshold(background_counts: float,
                                k_alpha: float = 1.645) -> float:
    """ISO 11929 decision threshold y* (counts)."""
    return k_alpha * math.sqrt(background_counts * 2.0)


# ══════════════════════════════════════════════════════════════════════
#  3.  Chi-squared goodness-of-fit (instrument QC)
# ══════════════════════════════════════════════════════════════════════
def chi2_gof(observed: Sequence[float], expected: Sequence[float] | None = None,
             *, alpha: float = 0.05) -> TestResult:
    """Pearson χ² goodness-of-fit. If `expected` is None we test the counts
    against their own mean — this is exactly the classic instrument QC test
    (10 × one-minute background counts, χ² should be 5.7–16.9 for df=9)."""
    n = len(observed)
    if n < 2:
        raise ValueError("need ≥2 observations")
    if expected is None:
        mean = sum(observed) / n
        expected = [mean] * n
        df = n - 1
    else:
        if len(expected) != n:
            raise ValueError("size mismatch")
        df = n - 1
    chi2 = sum((o - e)**2 / e for o, e in zip(observed, expected) if e > 0)
    p = _chi2_sf(chi2, df)
    return TestResult(chi2, p, p < alpha, note=f"χ² GoF · df={df}")


def instrument_chi_square(counts: Sequence[int], alpha: float = 0.05) -> TestResult:
    """Detector-stability chi-squared test (Knoll 3.5). For Poisson data the
    reduced χ² = (n-1)·s²/x̄ ~ χ²(n-1). Shortcut wrapper around chi2_gof."""
    return chi2_gof(counts, alpha=alpha)


# ══════════════════════════════════════════════════════════════════════
#  4.  Student-t (means & calibration) & paired-t
# ══════════════════════════════════════════════════════════════════════
def mean_ci(data: Sequence[float], level: float = 0.95) -> ConfidenceInterval:
    n = len(data)
    if n < 2:
        raise ValueError("need ≥2 samples")
    m = sum(data)/n
    s = math.sqrt(sum((x-m)**2 for x in data)/(n-1))
    alpha = 1 - level
    t = _t_ppf(1 - alpha/2, n-1)
    half = t * s / math.sqrt(n)
    return ConfidenceInterval(m-half, m+half, level)


def _t_ppf(p: float, df: float) -> float:
    lo, hi = -50.0, 50.0
    for _ in range(80):
        m = 0.5*(lo+hi)
        if 1.0 - _student_t_sf(m, df) < p: lo = m
        else: hi = m
    return 0.5*(lo+hi)


def one_sample_t(data: Sequence[float], mu0: float,
                 alpha: float = 0.05) -> TestResult:
    n = len(data)
    m = sum(data)/n
    s = math.sqrt(sum((x-m)**2 for x in data)/(n-1))
    t = (m - mu0) / (s / math.sqrt(n))
    p = 2.0 * (1.0 - _student_t_sf(-abs(t), n-1))
    return TestResult(t, p, p < alpha, note=f"one-sample t · df={n-1}")


def two_sample_t(a: Sequence[float], b: Sequence[float], *,
                 equal_var: bool = False, alpha: float = 0.05) -> TestResult:
    n1, n2 = len(a), len(b)
    m1, m2 = sum(a)/n1, sum(b)/n2
    v1 = sum((x-m1)**2 for x in a)/(n1-1)
    v2 = sum((x-m2)**2 for x in b)/(n2-1)
    if equal_var:
        sp2 = ((n1-1)*v1 + (n2-1)*v2)/(n1+n2-2)
        t = (m1 - m2) / math.sqrt(sp2*(1/n1 + 1/n2))
        df = n1 + n2 - 2
    else:
        t = (m1 - m2) / math.sqrt(v1/n1 + v2/n2)
        df = (v1/n1 + v2/n2)**2 / ((v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1))
    p = 2.0 * (1.0 - _student_t_sf(-abs(t), df))
    return TestResult(t, p, p < alpha,
                      note=f"{'Student' if equal_var else 'Welch'} t · df={df:.1f}")


def paired_t(a: Sequence[float], b: Sequence[float], alpha: float = 0.05) -> TestResult:
    if len(a) != len(b):
        raise ValueError("unequal lengths")
    d = [x-y for x, y in zip(a, b)]
    return one_sample_t(d, 0.0, alpha=alpha)


# ══════════════════════════════════════════════════════════════════════
#  5.  Propagation of uncertainty
# ══════════════════════════════════════════════════════════════════════
def combine_uncertainty(*components: float, method: str = "quadrature") -> float:
    """Combine independent standard uncertainties. `method` ∈
    {"quadrature", "linear"}."""
    if method == "quadrature":
        return math.sqrt(sum(u*u for u in components))
    if method == "linear":
        return sum(abs(u) for u in components)
    raise ValueError("method must be 'quadrature' or 'linear'")


def propagate_ratio(num: float, u_num: float, den: float, u_den: float,
                    *, cov: float = 0.0) -> tuple[float, float]:
    """Uncertainty of r = num/den via first-order Taylor (GUM §5.1)."""
    r = num / den
    var = (u_num/den)**2 + (num*u_den/den/den)**2 - 2*num*cov/den**3
    return r, math.sqrt(max(0.0, var))


def propagate_product(u_rel: Sequence[float]) -> float:
    """Relative standard uncertainty of a product of independent factors."""
    return math.sqrt(sum(r*r for r in u_rel))


# ══════════════════════════════════════════════════════════════════════
#  6.  Control-chart limits (Shewhart, Poisson)
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ControlLimits:
    centre: float
    warning_lo: float
    warning_hi: float
    action_lo: float
    action_hi: float


def shewhart_limits(data: Sequence[float]) -> ControlLimits:
    """Classical Shewhart x̄ chart with warning (±2σ) and action (±3σ) bands."""
    n = len(data)
    m = sum(data)/n
    s = math.sqrt(sum((x-m)**2 for x in data)/(n-1))
    return ControlLimits(m, m-2*s, m+2*s, m-3*s, m+3*s)


def poisson_limits(mean_counts: float) -> ControlLimits:
    """Control limits for a Poisson process with known mean."""
    s = math.sqrt(mean_counts)
    return ControlLimits(mean_counts,
                         mean_counts - 2*s, mean_counts + 2*s,
                         mean_counts - 3*s, mean_counts + 3*s)


# ══════════════════════════════════════════════════════════════════════
#  7.  Linear regression (calibration curves)
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float
    r_squared: float
    u_slope: float
    u_intercept: float
    residual_std: float
    n: int

    def predict(self, x: float) -> float:
        return self.slope*x + self.intercept

    def inverse(self, y: float) -> float:
        return (y - self.intercept) / self.slope


def linear_fit(x: Sequence[float], y: Sequence[float]) -> LinearFit:
    """Ordinary least squares — returns slope, intercept, r², std errors."""
    n = len(x)
    if n < 2 or n != len(y):
        raise ValueError("need ≥2 matched points")
    xm = sum(x)/n; ym = sum(y)/n
    Sxx = sum((xi-xm)**2 for xi in x)
    Sxy = sum((xi-xm)*(yi-ym) for xi, yi in zip(x, y))
    Syy = sum((yi-ym)**2 for yi in y)
    slope = Sxy / Sxx
    intercept = ym - slope*xm
    ss_res = sum((yi - (slope*xi + intercept))**2 for xi, yi in zip(x, y))
    r2 = 1.0 - ss_res/Syy if Syy > 0 else 1.0
    s = math.sqrt(ss_res / (n-2)) if n > 2 else 0.0
    u_slope = s / math.sqrt(Sxx) if Sxx > 0 else 0.0
    u_int = s * math.sqrt(1.0/n + xm*xm/Sxx) if Sxx > 0 else 0.0
    return LinearFit(slope, intercept, r2, u_slope, u_int, s, n)


# ══════════════════════════════════════════════════════════════════════
#  8.  Bayes-factor shortcut for source-vs-background
# ══════════════════════════════════════════════════════════════════════
def bayes_factor_source(gross: int, background: int, *,
                        prior_ratio: float = 1.0) -> float:
    """Jeffreys-style Bayes factor for H₁ (source present) vs H₀ (bkg only),
    assuming equal count times and Jeffreys prior on the source rate."""
    if gross < background:
        return 0.0
    # marginal likelihoods under Γ(½, 0) Jeffreys prior
    net = gross - background
    if net <= 0:
        return prior_ratio
    return prior_ratio * math.exp(
        math.lgamma(gross + 0.5)
        - math.lgamma(background + 0.5)
        - 0.5 * math.log(gross + 1)
    )


# ──────────────────────────────────────────────────────────────────────
#  Convenience — the one-liner summary a HP actually wants
# ──────────────────────────────────────────────────────────────────────
def summary(data: Sequence[float]) -> dict:
    """Quick descriptive summary: n, mean, sd, se, 95 % CI, min, max."""
    n = len(data)
    m = sum(data)/n
    s = math.sqrt(sum((x-m)**2 for x in data)/(n-1)) if n > 1 else 0.0
    se = s/math.sqrt(n) if n > 0 else 0.0
    ci = mean_ci(data) if n > 1 else None
    return {
        "n": n, "mean": m, "sd": s, "se": se,
        "ci95": ci, "min": min(data), "max": max(data),
    }


__all__ = [
    "TestResult", "DetectionLimits", "ConfidenceInterval", "ControlLimits",
    "LinearFit",
    "poisson_ci", "poisson_test", "binomial_ci",
    "currie_limits", "mda", "iso11929_decision_threshold",
    "chi2_gof", "instrument_chi_square",
    "mean_ci", "one_sample_t", "two_sample_t", "paired_t",
    "combine_uncertainty", "propagate_ratio", "propagate_product",
    "shewhart_limits", "poisson_limits",
    "linear_fit", "bayes_factor_source", "summary",
]
