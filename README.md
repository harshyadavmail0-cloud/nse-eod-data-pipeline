# NSE/BSE EOD Market Data Pipeline

Downloads official exchange-published end-of-day files (NSE UDiFF bhavcopies +
all-indices file + BSE bhavcopy), cleans them, computes implied volatility and
option Greeks (Black-Scholes-Merton), and writes consistent, deduplicated CSVs.

## Output files (data/output/)

| File | Contents |
|---|---|
| `index_ohlc_YYYYMMDD.csv` | Nifty 50 + every NSE index: OHLC, volume |
| `stocks_ohlc_YYYYMMDD.csv` | All listed stocks (EQ/BE/BZ): OHLC, volume, trades |
| `futures_YYYYMMDD.csv` | Index + stock futures: OHLC, settle, volume, OI, change in OI |
| `options_YYYYMMDD.csv` | Index + stock options: strike, expiry, type, OHLC, settle, volume, OI, **IV, Delta, Gamma, Theta, Vega, Rho** |

Guarantees: consistent headers across every day, duplicates removed,
key columns validated non-null, rows sorted.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python run_daily.py                                 # today's EOD files
python run_daily.py --date 2026-11-07               # a specific date
python run_daily.py --from 2024-01-01 --to 2026-11-07   # historical backfill
```

Backfill note: NSE moved to the UDiFF bhavcopy format in July 2024. For dates
before that, the older URL patterns need to be added in `download.py`
(straightforward; column mapping differs slightly).

## Daily automation (cron, after market close)

```
0 19 * * 1-5 cd /path/to/nifty_pipeline && python run_daily.py >> logs/run.log 2>&1
```

## Greeks methodology

- Model: Black-Scholes-Merton (European), spot = `UndrlygPric` from the FO
  bhavcopy, risk-free rate configurable in `config.py` (default 6.5%,
  keep near the 91-day T-bill rate).
- IV solved numerically (Brent) from the traded close premium;
  contracts with zero premium / below-intrinsic quotes get `NaN` instead of
  garbage values.
- Conventions: Theta per calendar day, Vega & Rho per 1% move -- the same
  conventions trading platforms display.
- Verified against standard reference values (see `tests/test_pipeline.py`).

## Tests

```bash
python tests/test_pipeline.py
```

Covers: option pricing vs textbook values, IV round-trip recovery,
edge cases (expired/zero-premium/below-intrinsic), end-to-end processing
with schema + dedupe checks.
