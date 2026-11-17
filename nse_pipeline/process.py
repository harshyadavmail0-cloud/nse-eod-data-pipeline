"""Transform raw bhavcopies into clean, consistent, deduplicated CSVs.

Outputs (per trade date, in data/output/):
  index_ohlc_YYYYMMDD.csv    date,index,open,high,low,close,volume
  stocks_ohlc_YYYYMMDD.csv   date,symbol,series,open,high,low,close,volume,trades
  futures_YYYYMMDD.csv       date,symbol,instrument,expiry,open,high,low,close,
                             settle,volume,open_interest,chg_in_oi,underlying
  options_YYYYMMDD.csv       futures columns + strike,option_type,iv,
                             delta,gamma,theta,vega,rho
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .greeks import greeks, implied_vol

# NSE UDiFF instrument codes
FUT_CODES = {"STF", "IDF"}  # stock futures, index futures
OPT_CODES = {"STO", "IDO"}  # stock options, index options


def _finish(df: pd.DataFrame, keys: list[str], out: Path) -> Path:
    """Dedupe, sort, validate, write."""
    before = len(df)
    df = df.drop_duplicates(subset=keys).sort_values(keys).reset_index(drop=True)
    if before != len(df):
        print(f"  [clean] removed {before - len(df)} duplicate rows for {out.name}")
    if df[keys].isna().any().any():
        raise ValueError(f"Null values found in key columns of {out.name}")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"  [ok] {out.name}: {len(df)} rows")
    return out


def process_indices(raw_csv: Path, d: date) -> Path:
    df = pd.read_csv(raw_csv)
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Index Date"], dayfirst=True).dt.date,
            "index": df["Index Name"].str.strip(),
            "open": pd.to_numeric(df["Open Index Value"], errors="coerce"),
            "high": pd.to_numeric(df["High Index Value"], errors="coerce"),
            "low": pd.to_numeric(df["Low Index Value"], errors="coerce"),
            "close": pd.to_numeric(df["Closing Index Value"], errors="coerce"),
            "volume": pd.to_numeric(df.get("Volume"), errors="coerce"),
        }
    )
    return _finish(out, ["date", "index"], config.OUT_DIR / f"index_ohlc_{d:%Y%m%d}.csv")


def process_stocks(raw_csv: Path, d: date) -> Path:
    df = pd.read_csv(raw_csv)
    df = df[df["SctySrs"].isin(["EQ", "BE", "BZ"])]  # cash-market series only
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["TradDt"]).dt.date,
            "symbol": df["TckrSymb"].str.strip(),
            "series": df["SctySrs"].str.strip(),
            "open": df["OpnPric"],
            "high": df["HghPric"],
            "low": df["LwPric"],
            "close": df["ClsPric"],
            "volume": df["TtlTradgVol"],
            "trades": df["TtlNbOfTxsExctd"],
        }
    )
    return _finish(
        out, ["date", "symbol", "series"], config.OUT_DIR / f"stocks_ohlc_{d:%Y%m%d}.csv"
    )


def _base_fo_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(df["TradDt"]).dt.date,
            "symbol": df["TckrSymb"].str.strip(),
            "instrument": df["FinInstrmTp"].str.strip(),
            "expiry": pd.to_datetime(df["XpryDt"]).dt.date,
            "open": df["OpnPric"],
            "high": df["HghPric"],
            "low": df["LwPric"],
            "close": df["ClsPric"],
            "settle": df["SttlmPric"],
            "volume": df["TtlTradgVol"],
            "open_interest": df["OpnIntrst"],
            "chg_in_oi": df["ChngInOpnIntrst"],
            "underlying": df["UndrlygPric"],
        }
    )


def process_fo(raw_csv: Path, d: date, risk_free: float = config.RISK_FREE_RATE):
    df = pd.read_csv(raw_csv, low_memory=False)

    # ---- futures ----
    fut = _base_fo_frame(df[df["FinInstrmTp"].isin(FUT_CODES)])
    fut_path = _finish(
        fut,
        ["date", "symbol", "expiry"],
        config.OUT_DIR / f"futures_{d:%Y%m%d}.csv",
    )

    # ---- options: IV + Greeks ----
    o = df[df["FinInstrmTp"].isin(OPT_CODES)].copy()
    opt = _base_fo_frame(o)
    opt["strike"] = pd.to_numeric(o["StrkPric"].values, errors="coerce")
    opt["option_type"] = o["OptnTp"].str.strip().values  # CE / PE

    t_years = (
        pd.to_datetime(opt["expiry"]) - pd.to_datetime(opt["date"])
    ).dt.days.to_numpy() / 365.0
    # expiry-day contracts: give them half a trading day of time value
    t_years = np.where(t_years <= 0, 0.5 / 365.0, t_years)

    ivs, rows = [], []
    for (s, k, t, px, typ) in zip(
        opt["underlying"].to_numpy(),
        opt["strike"].to_numpy(),
        t_years,
        opt["close"].to_numpy(),
        opt["option_type"].to_numpy(),
    ):
        iv = implied_vol(px, s, k, t, risk_free, typ)
        ivs.append(round(iv, 4) if np.isfinite(iv) else np.nan)
        rows.append(greeks(s, k, t, risk_free, iv, typ))

    opt["iv"] = ivs
    gdf = pd.DataFrame(rows)
    for col in ("delta", "gamma", "theta", "vega", "rho"):
        opt[col] = gdf[col].to_numpy()

    opt_path = _finish(
        opt,
        ["date", "symbol", "expiry", "strike", "option_type"],
        config.OUT_DIR / f"options_{d:%Y%m%d}.csv",
    )
    return fut_path, opt_path
