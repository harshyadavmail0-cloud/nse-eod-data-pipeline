"""Download official EOD bhavcopy files from NSE and BSE archives.

All files are exchange-published end-of-day files, available ~6:00-7:00 PM IST
on trading days. Weekends/holidays return 404 and are skipped gracefully.
"""
from __future__ import annotations

import io
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

from . import config


def _get(url: str, retries: int = 3, backoff: float = 2.0) -> bytes | None:
    """GET with retries. Returns None on 404 (holiday/not published yet)."""
    sess = requests.Session()
    sess.headers.update(config.HEADERS)
    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
            time.sleep(backoff * attempt)
    return None


def _save(content: bytes, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest


def _unzip_single_csv(blob: bytes, dest: Path) -> Path:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        return _save(zf.read(name), dest)


def fetch_nse_cm(d: date) -> Path | None:
    """NSE cash-market bhavcopy (all listed stocks OHLC+volume)."""
    url = config.NSE_CM_URL.format(date=d.strftime("%Y%m%d"))
    blob = _get(url)
    if blob is None:
        return None
    return _unzip_single_csv(blob, config.RAW_DIR / f"nse_cm_{d:%Y%m%d}.csv")


def fetch_nse_fo(d: date) -> Path | None:
    """NSE F&O bhavcopy (all futures + options contracts)."""
    url = config.NSE_FO_URL.format(date=d.strftime("%Y%m%d"))
    blob = _get(url)
    if blob is None:
        return None
    return _unzip_single_csv(blob, config.RAW_DIR / f"nse_fo_{d:%Y%m%d}.csv")


def fetch_nse_indices(d: date) -> Path | None:
    """NSE all-indices EOD file (Nifty 50 and every other NSE index)."""
    url = config.NSE_INDEX_URL.format(ddmmyyyy=d.strftime("%d%m%Y"))
    blob = _get(url)
    if blob is None:
        return None
    return _save(blob, config.RAW_DIR / f"nse_idx_{d:%Y%m%d}.csv")


def fetch_bse_cm(d: date) -> Path | None:
    """BSE equity bhavcopy (for Sensex constituents)."""
    url = config.BSE_CM_URL.format(date=d.strftime("%Y%m%d"))
    blob = _get(url)
    if blob is None:
        return None
    return _save(blob, config.RAW_DIR / f"bse_cm_{d:%Y%m%d}.csv")
