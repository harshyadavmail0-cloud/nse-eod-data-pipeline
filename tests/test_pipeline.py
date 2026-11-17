"""Tests: Black-Scholes values vs textbook references + end-to-end processing."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from nse_pipeline.greeks import bs_price, greeks, implied_vol
from nse_pipeline import process, config


def test_bs_price_textbook():
    # Classic reference: S=100,K=100,T=1y,r=5%,sigma=20% -> call 10.4506, put 5.5735
    assert abs(bs_price(100, 100, 1, 0.05, 0.2, "CE") - 10.4506) < 1e-3
    assert abs(bs_price(100, 100, 1, 0.05, 0.2, "PE") - 5.5735) < 1e-3
    print("PASS bs_price matches textbook values")


def test_greeks_textbook():
    g = greeks(100, 100, 1, 0.05, 0.2, "CE")
    assert abs(g["delta"] - 0.6368) < 1e-3
    assert abs(g["gamma"] - 0.018762) < 1e-4
    assert abs(g["vega"] - 0.3752) < 1e-3          # per 1% vol
    assert abs(g["theta"] - (-6.414 / 365)) < 1e-3  # per day
    assert abs(g["rho"] - 0.5323) < 1e-3            # per 1%
    p = greeks(100, 100, 1, 0.05, 0.2, "PE")
    assert abs(p["delta"] - (-0.3632)) < 1e-3
    print("PASS greeks match textbook values (call & put)")


def test_iv_round_trip():
    # price an option at known vol, then recover that vol from the price
    for sigma in (0.12, 0.25, 0.60):
        for opt in ("CE", "PE"):
            px = bs_price(24500, 24800, 30 / 365, 0.065, sigma, opt)
            iv = implied_vol(px, 24500, 24800, 30 / 365, 0.065, opt)
            assert abs(iv - sigma) < 1e-4, (sigma, opt, iv)
    print("PASS implied vol round-trip (recovers known sigma)")


def test_iv_edge_cases():
    assert np.isnan(implied_vol(0.0, 24500, 24800, 0.1, 0.065, "CE"))   # zero premium
    assert np.isnan(implied_vol(10.0, 24500, 24800, 0.0, 0.065, "CE"))  # expired
    # deep ITM quoted below intrinsic -> no solution
    assert np.isnan(implied_vol(50.0, 25000, 24000, 0.1, 0.065, "CE"))
    print("PASS IV edge cases return NaN instead of crashing")


def test_process_fo_fixture():
    """End-to-end on a small synthetic UDiFF-format fixture (format demo only)."""
    d = date(2026, 11, 7)
    fixture = pd.DataFrame(
        {
            "TradDt": ["2026-11-07"] * 5,
            "FinInstrmTp": ["IDO", "IDO", "IDO", "IDF", "IDO"],
            "TckrSymb": ["NIFTY"] * 5,
            "XpryDt": ["2026-11-26"] * 5,
            "StrkPric": [24500, 24500, 25000, 0, 25000],
            "OptnTp": ["CE", "PE", "CE", "", "CE"],
            "OpnPric": [310, 150, 120, 24610, 120],
            "HghPric": [340, 175, 140, 24700, 140],
            "LwPric": [295, 140, 105, 24550, 105],
            "ClsPric": [325.5, 160.25, 118.0, 24655.0, 118.0],
            "SttlmPric": [325.5, 160.25, 118.0, 24655.0, 118.0],
            "OpnIntrst": [1_200_000, 950_000, 2_100_000, 14_000_000, 2_100_000],
            "ChngInOpnIntrst": [50_000, -20_000, 130_000, 250_000, 130_000],
            "TtlTradgVol": [800_000, 600_000, 1_500_000, 9_000_000, 1_500_000],
            "UndrlygPric": [24600.0] * 5,
        }
    )
    # NOTE: last row duplicates row 3 on purpose -> dedupe check
    raw = config.RAW_DIR / "fixture_fo.csv"
    raw.parent.mkdir(parents=True, exist_ok=True)
    fixture.to_csv(raw, index=False)

    fut_path, opt_path = process.process_fo(raw, d)
    fut = pd.read_csv(fut_path)
    opt = pd.read_csv(opt_path)

    assert len(fut) == 1 and len(opt) == 3          # duplicate removed
    assert list(opt.columns) == [
        "date", "symbol", "instrument", "expiry", "open", "high", "low",
        "close", "settle", "volume", "open_interest", "chg_in_oi",
        "underlying", "strike", "option_type", "iv", "delta", "gamma",
        "theta", "vega", "rho",
    ]
    ce = opt[(opt.strike == 24500) & (opt.option_type == "CE")].iloc[0]
    pe = opt[(opt.strike == 24500) & (opt.option_type == "PE")].iloc[0]
    assert 0.05 < ce["iv"] < 1.0, "IV should be a sane annualised number"
    assert 0.4 < ce["delta"] < 0.7, "near-ATM call delta ~0.5-0.6"
    assert -0.6 < pe["delta"] < -0.3, "near-ATM put delta ~-0.4"
    assert ce["theta"] < 0 and pe["theta"] < 0, "long options decay"
    print("PASS end-to-end FO processing: schema, dedupe, sane IV/Greeks")
    print("\nSample options output (synthetic fixture, format demo):")
    print(opt.to_string(index=False))


if __name__ == "__main__":
    test_bs_price_textbook()
    test_greeks_textbook()
    test_iv_round_trip()
    test_iv_edge_cases()
    test_process_fo_fixture()
    print("\nALL TESTS PASSED")
