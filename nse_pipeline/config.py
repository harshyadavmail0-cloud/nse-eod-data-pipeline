"""Configuration for the NSE/BSE EOD data pipeline."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "data" / "output"

# Risk-free rate used for Black-Scholes (annualised, decimal).
# Keep this close to the 91-day T-bill / MIBOR rate. Update monthly.
RISK_FREE_RATE = 0.065

# Trading calendar: we simply skip days where NSE has no bhavcopy (404).

# NSE UDiFF bhavcopy URLs (format in force since July 2024)
NSE_CM_URL = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{date}_F_0000.csv.zip"
)
NSE_FO_URL = (
    "https://nsearchives.nseindia.com/content/fo/"
    "BhavCopy_NSE_FO_0_0_0_{date}_F_0000.csv.zip"
)
# All-indices EOD file (Nifty 50 & friends)
NSE_INDEX_URL = (
    "https://nsearchives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
)
# BSE bhavcopy (for Sensex constituents OHLC)
BSE_CM_URL = (
    "https://www.bseindia.com/download/BhavCopy/Equity/"
    "BhavCopy_BSE_CM_0_0_0_{date}_F_0000.CSV"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}
