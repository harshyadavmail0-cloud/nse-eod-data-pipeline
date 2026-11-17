"""Render a dashboard-style PNG summary from the pipeline's REAL output CSVs.

Usage:
    python make_dashboard.py --date 2026-11-06

Reads data/output/{index_ohlc,stocks_ohlc,options}_YYYYMMDD.csv and produces
data/output/dashboard_YYYYMMDD.png -- every number on it comes from the
official NSE EOD files processed by the pipeline. No mock data.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parent / "data" / "output"

BG = "#0d1117"
PANEL = "#161b22"
FG = "#e6edf3"
GREEN = "#3fb950"
RED = "#f85149"
BLUE = "#58a6ff"
GRAY = "#8b949e"


def card(ax, title, value, sub="", color=FG):
    ax.set_facecolor(PANEL)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#30363d")
    ax.text(0.06, 0.74, title, fontsize=11, color=GRAY, transform=ax.transAxes)
    ax.text(0.06, 0.36, value, fontsize=20, fontweight="bold", color=color,
            transform=ax.transAxes)
    if sub:
        ax.text(0.06, 0.10, sub, fontsize=10, color=GRAY, transform=ax.transAxes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()
    d = datetime.strptime(args.date, "%Y-%m-%d").date()
    tag = d.strftime("%Y%m%d")

    idx = pd.read_csv(OUT / f"index_ohlc_{tag}.csv")
    stk = pd.read_csv(OUT / f"stocks_ohlc_{tag}.csv")
    opt = pd.read_csv(OUT / f"options_{tag}.csv")

    nifty = idx[idx["index"].str.strip().str.lower() == "nifty 50"].iloc[0]
    vix = idx[idx["index"].str.strip().str.lower() == "india vix"].iloc[0]

    # NIFTY options, nearest MONTHLY expiry (last weekly of the chain is fine:
    # pick the expiry with the highest total OI -> most liquid series)
    no = opt[(opt["symbol"] == "NIFTY") & (opt["instrument"] == "IDO")].copy()
    best_exp = no.groupby("expiry")["open_interest"].sum().idxmax()
    chain = no[no["expiry"] == best_exp]
    spot = float(chain["underlying"].iloc[0])
    near = chain[(chain["strike"] >= spot * 0.96) & (chain["strike"] <= spot * 1.04)]
    ce = near[near["option_type"] == "CE"].sort_values("strike")
    pe = near[near["option_type"] == "PE"].sort_values("strike")

    top = stk.nlargest(10, "volume")[::-1]

    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    gs = fig.add_gridspec(
        3, 4, left=0.05, right=0.97, top=0.86, bottom=0.07,
        hspace=0.55, wspace=0.25, height_ratios=[0.9, 2, 2]
    )

    fig.text(0.05, 0.955, "NIFTY ANALYZER - EOD DATA SNAPSHOT", fontsize=22,
             fontweight="bold", color=FG)
    fig.text(0.05, 0.915,
             f"Trade date: {d:%d %b %Y}  |  Source: official NSE EOD bhavcopy "
             f"files, processed by automated pipeline  |  All values real & "
             f"verifiable on nseindia.com", fontsize=11, color=GRAY)

    chg = nifty["close"] - nifty["open"]
    card(fig.add_subplot(gs[0, 0]), "NIFTY 50 CLOSE", f"{nifty['close']:,.2f}",
         f"O {nifty['open']:,.0f}  H {nifty['high']:,.0f}  L {nifty['low']:,.0f}",
         GREEN if chg >= 0 else RED)
    card(fig.add_subplot(gs[0, 1]), "INDIA VIX", f"{vix['close']:.2f}",
         f"H {vix['high']:.2f}  L {vix['low']:.2f}", BLUE)
    card(fig.add_subplot(gs[0, 2]), "STOCKS COVERED", f"{stk['symbol'].nunique():,}",
         "cash market, EOD OHLC + volume")
    card(fig.add_subplot(gs[0, 3]), "OPTION CONTRACTS", f"{len(opt):,}",
         "with IV + Delta Gamma Theta Vega Rho")

    # --- OI by strike ---
    ax1 = fig.add_subplot(gs[1, :2]); ax1.set_facecolor(PANEL)
    w = (ce["strike"].diff().median() or 50) * 0.4
    ax1.bar(ce["strike"] - w / 2, ce["open_interest"], width=w, color=GREEN,
            label="Call OI")
    ax1.bar(pe["strike"] + w / 2, pe["open_interest"], width=w, color=RED,
            label="Put OI")
    ax1.axvline(spot, color=BLUE, ls="--", lw=1.2)
    ax1.text(spot, ax1.get_ylim()[1] * 0.97, f" spot {spot:,.0f}", color=BLUE,
             fontsize=9, va="top")
    ax1.set_title(f"NIFTY Open Interest by Strike  (expiry {best_exp})",
                  color=FG, fontsize=12, pad=8)
    ax1.legend(facecolor=PANEL, labelcolor=FG, edgecolor="#30363d")

    # --- IV skew ---
    ax2 = fig.add_subplot(gs[1, 2:]); ax2.set_facecolor(PANEL)
    ax2.plot(ce["strike"], ce["iv"] * 100, "o-", color=GREEN, ms=4, label="Call IV")
    ax2.plot(pe["strike"], pe["iv"] * 100, "o-", color=RED, ms=4, label="Put IV")
    ax2.axvline(spot, color=BLUE, ls="--", lw=1.2)
    ax2.set_title("NIFTY Implied Volatility by Strike (%)", color=FG,
                  fontsize=12, pad=8)
    ax2.legend(facecolor=PANEL, labelcolor=FG, edgecolor="#30363d")

    # --- top volume stocks ---
    ax3 = fig.add_subplot(gs[2, :2]); ax3.set_facecolor(PANEL)
    ax3.barh(top["symbol"], top["volume"] / 1e6, color=BLUE)
    ax3.set_title("Top 10 Stocks by Traded Volume (millions of shares)",
                  color=FG, fontsize=12, pad=8)

    # --- ATM greeks table ---
    ax4 = fig.add_subplot(gs[2, 2:]); ax4.set_facecolor(PANEL)
    ax4.set_xticks([]); ax4.set_yticks([])
    atm = near.iloc[(near["strike"] - spot).abs().argsort()[:8]].sort_values(
        ["strike", "option_type"])
    cols = ["strike", "option_type", "close", "iv", "delta", "theta", "vega"]
    tbl = ax4.table(
        cellText=[[f"{r.strike:,.0f}", r.option_type, f"{r.close:,.2f}",
                   f"{r.iv:.1%}" if pd.notna(r.iv) else "-",
                   f"{r.delta:.3f}" if pd.notna(r.delta) else "-",
                   f"{r.theta:.2f}" if pd.notna(r.theta) else "-",
                   f"{r.vega:.2f}" if pd.notna(r.vega) else "-"]
                  for r in atm.itertuples()],
        colLabels=["Strike", "Type", "Premium", "IV", "Delta", "Theta", "Vega"],
        loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.5)
    for (row, _col), cell in tbl.get_celld().items():
        cell.set_facecolor(PANEL if row else "#21262d")
        cell.set_text_props(color=FG)
        cell.set_edgecolor("#30363d")
    ax4.set_title("ATM Option Chain - Computed Greeks (sample)", color=FG,
                  fontsize=12, pad=8)

    for ax in (ax1, ax2, ax3):
        ax.tick_params(colors=GRAY)
        for s in ax.spines.values():
            s.set_color("#30363d")

    out = OUT / f"dashboard_{tag}.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    print(f"[ok] dashboard written: {out}")


if __name__ == "__main__":
    main()
