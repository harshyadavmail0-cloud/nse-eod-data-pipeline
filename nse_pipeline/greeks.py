"""Black-Scholes-Merton pricing, implied volatility and Greeks.

Conventions used (industry standard):
  - delta: per 1 unit move in underlying
  - gamma: change in delta per 1 unit move in underlying
  - theta: per CALENDAR DAY (annual theta / 365)
  - vega : per 1% change in volatility (annual vega / 100)
  - rho  : per 1% change in interest rate (annual rho / 100)
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float):
    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return d1, d2


def bs_price(s: float, k: float, t: float, r: float, sigma: float, opt: str) -> float:
    """Black-Scholes-Merton European option price (no dividends)."""
    if t <= 0 or sigma <= 0:
        intrinsic = max(s - k, 0.0) if opt == "CE" else max(k - s, 0.0)
        return intrinsic
    d1, d2 = _d1_d2(s, k, t, r, sigma)
    if opt == "CE":
        return s * norm.cdf(d1) - k * math.exp(-r * t) * norm.cdf(d2)
    return k * math.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1)


def implied_vol(
    price: float, s: float, k: float, t: float, r: float, opt: str
) -> float:
    """Solve for implied volatility from a traded premium.

    Returns np.nan when no solution exists (e.g. premium below intrinsic,
    expired contract, or zero premium).
    """
    if t <= 0 or price <= 0 or s <= 0 or k <= 0:
        return np.nan
    intrinsic = max(s - k, 0.0) if opt == "CE" else max(k - s, 0.0)
    # Premium at/below discounted intrinsic has no BS solution.
    if price <= intrinsic * math.exp(-r * t) + 1e-10:
        return np.nan
    try:
        return brentq(
            lambda sig: bs_price(s, k, t, r, sig, opt) - price,
            1e-4,
            5.0,
            maxiter=200,
            xtol=1e-8,
        )
    except ValueError:
        return np.nan


def greeks(
    s: float, k: float, t: float, r: float, sigma: float, opt: str
) -> dict[str, float]:
    """Delta, Gamma, Theta (per day), Vega (per 1%), Rho (per 1%)."""
    if t <= 0 or not np.isfinite(sigma) or sigma <= 0:
        return {g: np.nan for g in ("delta", "gamma", "theta", "vega", "rho")}
    d1, d2 = _d1_d2(s, k, t, r, sigma)
    pdf_d1 = norm.pdf(d1)
    sqrt_t = math.sqrt(t)
    disc = math.exp(-r * t)

    gamma = pdf_d1 / (s * sigma * sqrt_t)
    vega = s * pdf_d1 * sqrt_t / 100.0  # per 1 vol point

    if opt == "CE":
        delta = norm.cdf(d1)
        theta_yr = -s * pdf_d1 * sigma / (2 * sqrt_t) - r * k * disc * norm.cdf(d2)
        rho = k * t * disc * norm.cdf(d2) / 100.0
    else:
        delta = norm.cdf(d1) - 1.0
        theta_yr = -s * pdf_d1 * sigma / (2 * sqrt_t) + r * k * disc * norm.cdf(-d2)
        rho = -k * t * disc * norm.cdf(-d2) / 100.0

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta_yr / 365.0, 4),  # per calendar day
        "vega": round(vega, 4),
        "rho": round(rho, 4),
    }
