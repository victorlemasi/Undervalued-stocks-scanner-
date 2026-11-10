"""
Undervalued Stocks Scanner  v1.2
=================================
Scans anywhere from a curated 34-stock list up to ALL publicly listed US stocks
(~8,000+ tickers from NASDAQ, NYSE, AMEX) using Yahoo Finance data.

Scan modes
----------
1. Quick Scan       — 34 hand-picked blue-chips          (~1–2 min)
2. S&P 500          — 500 largest US companies           (~10–15 min)
3. NASDAQ Listed    — ~3,300 NASDAQ common stocks        (~1–2 hours)
4. All US Stocks    — NASDAQ + NYSE + AMEX (~8,000+)    (~3–6 hours)
5. Custom           — paste tickers or point to a file

For large scans a progress bar with ETA is shown and results are
checkpointed to disk so an interrupted run can be resumed.
"""

import warnings
warnings.simplefilter(action='ignore')
warnings.filterwarnings("ignore")

# ── stdlib ──────────────────────────────────────────────────────────────────
import sys, os, json, time, traceback, threading
import concurrent.futures
import urllib.request
from datetime import datetime, timedelta

# ── third-party ─────────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
import yfinance as yf

warnings.simplefilter(action='ignore')
warnings.filterwarnings("ignore")

# ============================================================================
# CONSTANTS
# ============================================================================

VERSION = "1.2"

CURATED_US_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSM',  'ASML',
    'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM',  'QCOM', 'INTC', 'AMD',
    'JPM',  'BAC',  'WFC',  'GS',   'MS',   'C',    'BRK-B','V',   'MA',
    'JNJ',  'PFE',  'MRK',  'ABBV', 'LLY',  'NVS',  'PG',   'KO',  'PEP',
]

MX_TICKERS = [
    'WALMEX.MX', 'AMXL.MX', 'FEMSAUBD.MX', 'GFNORTEO.MX',
    'GMEXICOB.MX', 'CEMEXCPO.MX', 'TLEVISACPO.MX',
]

DEFAULT_THRESHOLDS = {
    'max_pe':              15,
    'max_pb':              2,
    'min_profit_margin':   0.10,
    'min_current_ratio':   1.5,
    'max_debt_equity':     100,
    'min_operating_margin':15,
    'max_peg':             1.5,
    'min_earnings_growth': 10,
    'min_div_yield':       2.5,
    'min_roa':             10,
    'min_roe':             15,
    'min_distance_from_high': 20,
    'max_price_to_ma200':  -10,
}

# Checkpoint directory (next to the script)
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_DIR = os.path.join(SCRIPT_DIR, '.scan_checkpoints')

# ============================================================================
# VALUATION HELPERS
# ============================================================================

def calculate_graham_number(eps, bvps):
    """√(22.5 × EPS × BVPS)"""
    return float(np.sqrt(22.5 * eps * bvps)) if eps > 0 and bvps > 0 else 0.0


def calculate_peg_ratio(pe, growth_pct):
    return pe / growth_pct if growth_pct > 0 else float('inf')


def get_dividend_yield(info):
    """
    Return dividend yield as a proper percentage (e.g. 2.5 for 2.5%).

    yfinance stores dividendYield as a decimal fraction (0.005 = 0.5%).
    However it sometimes returns values that look like percentages (0.5 for 0.5%).
    We disambiguate: if the raw value is > 0.25 (25%) we treat it as already
    in percent form (a 25%+ dividend is essentially impossible for large caps).

    Falls back to computing yield from trailingAnnualDividendRate / price.
    """
    raw = info.get('dividendYield')
    if raw and raw > 0:
        # Very high raw values (> 0.25) are almost certainly already in % form
        if raw > 0.25:
            return min(raw, 100.0)          # already a percentage, just cap
        return raw * 100.0                  # normal decimal → percent

    # Fallback: compute from trailing annual dividend / current price
    annual_div = info.get('trailingAnnualDividendRate') or 0
    price      = (info.get('currentPrice') or
                  info.get('regularMarketPrice') or
                  info.get('previousClose') or 0)
    if annual_div > 0 and price > 0:
        return (annual_div / price) * 100.0
    return 0.0


# ============================================================================
# TICKER LIST FETCHERS
# ============================================================================

def _clean_tickers(raw_list):
    """Remove invalid / special-character symbols."""
    bad = {'^', '/', '$', ' ', '+', '~'}
    return sorted({
        t.strip() for t in raw_list
        if t and len(t.strip()) <= 5          # real tickers are ≤ 5 chars
        and not any(c in t for c in bad)
        and 'File' not in t
        and t.strip().isalpha()               # letters only (no digits/dots in symbol)
    })


def _fetch_json(url, timeout=15):
    """Download JSON from a URL, returning parsed object or None."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _fetch_text_csv(url, sep='|', timeout=20):
    """Download a pipe/csv delimited text file into a DataFrame."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = r.read().decode('utf-8', errors='replace')
    from io import StringIO
    return pd.read_csv(StringIO(content), sep=sep, on_bad_lines='skip')


# ── Source registry (tried in order until one works) ────────────────────────
# S&P 500
_SP500_SOURCES = [
    # GitHub mirror (most reliable, no bot-block)
    ('github_sp500',
     'https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv',
     'csv', 'Symbol'),
    # Slickcharts mirror via requests (plain CSV)
    ('datahub_sp500',
     'https://pkgstore.datahub.io/core/s-and-p-500-companies/constituents_json/data/64dd3e9582b936b0352fdd826ecd3c95/constituents_json.json',
     'json_symbols', None),
]

# All NASDAQ
_NASDAQ_SOURCES = [
    ('github_nasdaq',
     'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nasdaq/nasdaq_tickers.json',
     'json_list', None),
    ('nasdaqtrader',
     'https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt',
     'pipe', 'Symbol'),
]

# NYSE / AMEX
_NYSE_SOURCES = [
    ('github_nyse',
     'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nyse/nyse_tickers.json',
     'json_list', None),
    ('nasdaqtrader_other',
     'https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt',
     'pipe', 'ACT Symbol'),
]

# All US (combined) – GitHub doesn't host a single combined file, so we keep
# this list empty; fetch_all_us_tickers() falls through to per-exchange fetching
_ALL_SOURCES = []

# SEC EDGAR fallback (always works, has all registered companies)
_SEC_TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'


def _try_sources(source_list, label):
    """
    Try each source in order; return the first successful ticker list.
    source format: (name, url, fmt, column)
      fmt: 'csv' | 'pipe' | 'json_list' | 'json_symbols'
    """
    for name, url, fmt, col in source_list:
        try:
            if fmt in ('csv', 'pipe'):
                sep = '|' if fmt == 'pipe' else ','
                df  = _fetch_text_csv(url, sep=sep)
                if col and col in df.columns:
                    return df[col].dropna().astype(str).tolist()
            elif fmt == 'json_list':
                data = _fetch_json(url)
                if isinstance(data, list):
                    return [str(x) for x in data]
            elif fmt == 'json_symbols':
                data = _fetch_json(url)
                if isinstance(data, list):
                    return [d.get('Symbol', d.get('symbol', '')) for d in data if isinstance(d, dict)]
        except Exception as exc:
            print(f" [{name}] failed: {exc}", end='')
            continue
    return []


def _sec_fallback():
    """Return all SEC-registered tickers as last resort (slow – ~7k tickers)."""
    try:
        data = _fetch_json(_SEC_TICKERS_URL)
        return [v['ticker'] for v in data.values() if isinstance(v, dict) and v.get('ticker')]
    except Exception as exc:
        print(f" [SEC] failed: {exc}")
        return []


def fetch_sp500_tickers():
    """S&P 500 constituent list – tries multiple mirrors."""
    print("  ↳ Fetching S&P 500 tickers…", end='', flush=True)
    tickers = _try_sources(_SP500_SOURCES, 'S&P 500')
    if not tickers:
        print(" all sources failed – using built-in 34-stock list.")
        return []
    tickers = _clean_tickers(tickers)
    print(f" {len(tickers)} tickers.")
    return tickers


def fetch_nasdaq_listed_tickers():
    """Common stocks on NASDAQ – tries GitHub mirror first, then NASDAQ FTP."""
    print("  ↳ Fetching NASDAQ tickers…", end='', flush=True)
    tickers = _try_sources(_NASDAQ_SOURCES, 'NASDAQ')
    if not tickers:
        print(" all sources failed.")
        return []
    tickers = _clean_tickers(tickers)
    print(f" {len(tickers)} tickers.")
    return tickers


def fetch_all_us_tickers():
    """
    All US-listed common stocks (NASDAQ + NYSE + AMEX).
    Tries a combined GitHub source first, then per-exchange, then SEC EDGAR.
    """
    all_raw = []

    # Try the combined GitHub list first
    print("  ↳ Fetching all-US combined list…", end='', flush=True)
    combined = _try_sources(_ALL_SOURCES, 'All-US')
    if combined:
        all_raw += combined
        print(f" {len(combined)} raw tickers.")
    else:
        print(" not available – trying per-exchange.")
        # NASDAQ
        print("  ↳ Fetching NASDAQ…", end='', flush=True)
        t1 = _try_sources(_NASDAQ_SOURCES, 'NASDAQ')
        all_raw += t1
        print(f" {len(t1)}.")
        # NYSE/AMEX
        print("  ↳ Fetching NYSE/AMEX…", end='', flush=True)
        t2 = _try_sources(_NYSE_SOURCES, 'NYSE')
        all_raw += t2
        print(f" {len(t2)}.")

    if not all_raw:
        print("  ↳ All network sources failed – falling back to SEC EDGAR…",
              end='', flush=True)
        all_raw = _sec_fallback()
        print(f" {len(all_raw)}.")

    tickers = _clean_tickers(all_raw)
    print(f"  ↳ After cleanup: {len(tickers):,} unique tickers.")
    return tickers


def fetch_custom_tickers():
    """
    Let the user paste tickers inline or point to a plain-text file
    (one ticker per line, or comma/space separated).
    """
    print("\n  Enter ticker symbols separated by commas/spaces,")
    print("  OR enter a file path to a .txt/.csv with one ticker per line.")
    raw = input("  > ").strip()

    if os.path.isfile(raw):
        with open(raw, 'r') as f:
            content = f.read()
    else:
        content = raw

    # Split on commas, spaces, newlines, semicolons
    import re
    tokens = re.split(r'[\s,;]+', content.upper())
    return _clean_tickers(tokens)


# ============================================================================
# PROGRESS TRACKER  (thread-safe)
# ============================================================================

class ProgressTracker:
    """Thread-safe progress bar with ETA, printed by a background thread."""

    def __init__(self, total, bar_width=35):
        self.total     = total
        self.bar_width = bar_width
        self.done      = 0
        self.found     = 0
        self.errors    = 0
        self.lock      = threading.Lock()
        self.start_t   = time.time()
        self._stop_evt = threading.Event()
        self._thread   = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def increment(self, found=False, error=False):
        with self.lock:
            self.done  += 1
            if found:  self.found  += 1
            if error:  self.errors += 1

    def _render_loop(self):
        while not self._stop_evt.is_set():
            self._render()
            time.sleep(0.5)
        self._render()   # final update
        print()          # newline after bar

    def _render(self):
        with self.lock:
            done  = self.done
            found = self.found
            errs  = self.errors
            total = self.total

        elapsed = time.time() - self.start_t
        pct     = done / total if total else 0
        filled  = int(self.bar_width * pct)
        bar     = '█' * filled + '░' * (self.bar_width - filled)

        if done > 0 and pct < 1.0:
            eta_s = elapsed / done * (total - done)
            eta   = str(timedelta(seconds=int(eta_s)))
        else:
            eta = '--:--'

        speed = done / elapsed if elapsed > 0 else 0
        line  = (f"\r  [{bar}] {pct*100:5.1f}%"
                 f"  {done}/{total}"
                 f"  ✅{found}"
                 f"  ⚠{errs}"
                 f"  {speed:.1f}/s"
                 f"  ETA {eta}  ")
        print(line, end='', flush=True)

    def stop(self):
        self._stop_evt.set()
        self._thread.join()


# ============================================================================
# CHECKPOINT  (save / load partial results)
# ============================================================================

def checkpoint_path(scan_label):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() else '_' for c in scan_label)
    return os.path.join(CHECKPOINT_DIR, f"ckpt_{safe}.json")


def load_checkpoint(scan_label):
    path = checkpoint_path(scan_label)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)   # dict: ticker → result_dict | null
    return {}


def _json_default(obj):
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if pd.isna(obj):
        return None
    return str(obj)


def save_checkpoint(scan_label, done_map):
    path = checkpoint_path(scan_label)
    with open(path, 'w') as f:
        json.dump(done_map, f, default=_json_default)


# ============================================================================
# SINGLE-STOCK ANALYSIS  (runs inside each worker thread)
# ============================================================================

def analyze_single_stock(ticker, thresholds, min_market_cap):
    """
    Fetch and analyse one ticker.
    Returns a result dict on success, None if skipped, raises on hard error.
    """
    stock = yf.Ticker(ticker)
    info  = stock.info

    # Bail out if Yahoo returned an empty / error response
    if not info or info.get('quoteType') is None:
        return None

    market_cap = info.get('marketCap') or 0
    if market_cap < min_market_cap:
        return None     # below threshold – skip silently

    # ── Fundamental metrics ─────────────────────────────────────────────────
    pe_ratio      = info.get('forwardPE')       or float('inf')
    pb_ratio      = info.get('priceToBook')     or float('inf')
    profit_margin = info.get('profitMargins')   or 0.0
    current_ratio = info.get('currentRatio')    or 0.0
    debt_to_equity= info.get('debtToEquity')    or float('inf')

    eps           = info.get('trailingEps')     or 0.0
    bvps          = info.get('bookValue')       or 0.0
    graham_number = calculate_graham_number(eps, bvps)

    dividend_yield  = get_dividend_yield(info)
    earnings_growth = (info.get('earningsGrowth') or 0.0) * 100.0
    peg_ratio       = calculate_peg_ratio(pe_ratio, earnings_growth)

    ev              = info.get('enterpriseValue') or 0
    ebitda          = info.get('ebitda')          or 0
    ev_to_ebitda    = ev / ebitda if ebitda else float('inf')

    operating_margin= (info.get('operatingMargins')  or 0.0) * 100.0
    roa             = (info.get('returnOnAssets')     or 0.0) * 100.0
    roe             = (info.get('returnOnEquity')     or 0.0) * 100.0

    # ── Historical price data ────────────────────────────────────────────────
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=365)
    hist     = stock.history(start=start_dt, end=end_dt)

    if hist.empty:
        return None

    high_52w     = hist['High'].max()
    current_price= hist['Close'].iloc[-1]
    dist_from_high = ((high_52w - current_price) / high_52w) * 100.0

    ma200_series = hist['Close'].rolling(window=200).mean()
    last_ma200   = ma200_series.iloc[-1]
    price_to_ma200 = ((current_price / last_ma200) - 1) * 100.0 if not np.isnan(last_ma200) else 0.0

    # ── Criteria evaluation ──────────────────────────────────────────────────
    criteria = {
        'Traditional Value': (
            pe_ratio       < thresholds['max_pe']              and
            pb_ratio       < thresholds['max_pb']              and
            profit_margin  > thresholds['min_profit_margin']
        ),
        'Quality Metrics': (
            current_ratio  > thresholds['min_current_ratio']   and
            debt_to_equity < thresholds['max_debt_equity']     and
            operating_margin > thresholds['min_operating_margin']
        ),
        'Growth at Reasonable Price': (
            peg_ratio      < thresholds['max_peg']             and
            earnings_growth> thresholds['min_earnings_growth']
        ),
        'Graham Style': (
            graham_number  > current_price                     and
            dividend_yield > thresholds['min_div_yield']
        ),
        'Profitability': (
            roa  > thresholds['min_roa']                       and
            roe  > thresholds['min_roe']
        ),
        'Technical Factors': (
            dist_from_high > thresholds['min_distance_from_high'] and
            price_to_ma200 < thresholds['max_price_to_ma200']
        ),
    }

    return {
        'Ticker':          str(ticker),
        'Company':         str(info.get('longName', 'N/A')),
        'Market Cap (B)':  round(float(market_cap) / 1e9, 2),
        'Criteria Met':    int(sum(criteria.values())),
        'P/E Ratio':       round(float(pe_ratio),       2) if pe_ratio       != float('inf') else None,
        'P/B Ratio':       round(float(pb_ratio),       2) if pb_ratio       != float('inf') else None,
        'EV/EBITDA':       round(float(ev_to_ebitda),   2) if ev_to_ebitda   != float('inf') else None,
        'PEG Ratio':       round(float(peg_ratio),      2) if peg_ratio      != float('inf') else None,
        'Earnings Growth (%)':  round(float(earnings_growth), 2),
        'Dividend Yield (%)':   round(float(dividend_yield),  2),
        'Operating Margin (%)': round(float(operating_margin),2),
        'ROE (%)':         round(float(roe),             2),
        'ROA (%)':         round(float(roa),             2),
        'Current Ratio':   round(float(current_ratio),   2),
        'Debt/Equity':     round(float(debt_to_equity),  2) if debt_to_equity != float('inf') else None,
        'Dist 52w High (%)':    round(float(dist_from_high),  2),
        'Price vs 200MA (%)':   round(float(price_to_ma200),  2),
        'Graham Number':   round(float(graham_number),   2),
        'Current Price':   round(float(current_price),   2),
        'Industry':        str(info.get('industry', 'N/A')),
        'Sector':          str(info.get('sector',   'N/A')),
        '_criteria':       {str(k): bool(v) for k, v in criteria.items() if v},   # internal
    }


# ============================================================================
# PARALLEL SCAN ORCHESTRATOR
# ============================================================================

def analyze_stocks_parallel(tickers, min_market_cap, criteria_threshold,
                             custom_thresholds, max_workers, scan_label,
                             resume=False):
    """
    Analyze a list of tickers in parallel.

    Parameters
    ----------
    tickers            : list of ticker symbols
    min_market_cap     : skip stocks below this market cap
    criteria_threshold : minimum criteria sets to flag as undervalued
    custom_thresholds  : dict overriding DEFAULT_THRESHOLDS values
    max_workers        : number of parallel threads
    scan_label         : used for checkpoint filename
    resume             : if True, skip tickers already in the checkpoint

    Returns
    -------
    pd.DataFrame of qualifying stocks (sorted best-first)
    """
    thresholds = {**DEFAULT_THRESHOLDS, **(custom_thresholds or {})}

    # ── Load checkpoint ──────────────────────────────────────────────────────
    done_map = load_checkpoint(scan_label) if resume else {}
    if done_map:
        already = sum(1 for v in done_map.values() if v is not None)
        print(f"  Resuming: {len(done_map)} tickers already processed "
              f"({already} had results).")

    pending = [t for t in tickers if t not in done_map]
    total   = len(tickers)

    # Pre-collected results from checkpoint
    qualified = [v for v in done_map.values()
                 if v and v.get('Criteria Met', 0) >= criteria_threshold]

    if not pending:
        print("  All tickers already processed (checkpoint complete).")
    else:
        progress = ProgressTracker(total=total)
        progress.done  = len(done_map)   # offset progress for already-done
        progress.found = len(qualified)
        lock      = threading.Lock()
        ckpt_ctr  = [0]                  # mutable counter for checkpoint saves

        def _worker(ticker):
            try:
                result = analyze_single_stock(ticker, thresholds, min_market_cap)
            except Exception:
                result = None
                progress.increment(error=True)
            else:
                found = result is not None and result.get('Criteria Met', 0) >= criteria_threshold
                progress.increment(found=found)
                result = result if found else None   # only keep qualifiers

            # Save to checkpoint map (None = processed but not qualified)
            with lock:
                done_map[ticker] = result
                ckpt_ctr[0]     += 1
                # Write checkpoint every 100 tickers
                if ckpt_ctr[0] % 100 == 0:
                    save_checkpoint(scan_label, done_map)

            if result and result.get('Criteria Met', 0) >= criteria_threshold:
                with lock:
                    qualified.append(result)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_worker, t): t for t in pending}
            try:
                concurrent.futures.wait(futures)
            except KeyboardInterrupt:
                print("\n\n  ⚠  Scan interrupted! Saving checkpoint…")
                ex.shutdown(wait=False, cancel_futures=True)

        progress.stop()
        save_checkpoint(scan_label, done_map)   # final save
        ckpt_file = checkpoint_path(scan_label)
        print(f"  Checkpoint saved → {ckpt_file}")

    # ── Build & sort DataFrame ───────────────────────────────────────────────
    if not qualified:
        return pd.DataFrame()

    df = pd.DataFrame(qualified)
    df = df.sort_values(['Criteria Met', 'Market Cap (B)'], ascending=[False, False])
    df = df.reset_index(drop=True)
    return df


# ============================================================================
# OUTPUT & RECOMMENDATIONS
# ============================================================================

def print_recommendations(df, top_n=5):
    top = df.head(top_n)
    for _, row in top.iterrows():
        criteria = row.get('_criteria', {})
        label_list = ', '.join(criteria.keys()) if criteria else 'N/A'

        pe_str    = f"{row['P/E Ratio']}"    if row['P/E Ratio']    is not None else 'N/A'
        pb_str    = f"{row['P/B Ratio']}"    if row['P/B Ratio']    is not None else 'N/A'
        peg_str   = f"{row['PEG Ratio']}"    if row['PEG Ratio']    is not None else 'N/A'
        ev_str    = f"{row['EV/EBITDA']}"    if row['EV/EBITDA']    is not None else 'N/A'
        de_str    = f"{row['Debt/Equity']}"  if row['Debt/Equity']  is not None else 'N/A'
        div_str   = f"{row['Dividend Yield (%)']:.2f}%" if row['Dividend Yield (%)'] > 0 else 'None'
        ma_dir    = 'below' if row['Price vs 200MA (%)'] < 0 else 'above'

        print(f"\n── {row['Ticker']}  |  {row['Company']}  |  {row['Sector']} ──")
        print(f"""
  Meets {row['Criteria Met']} / 6 criteria: {label_list}

  Valuation
    P/E: {pe_str}   P/B: {pb_str}   EV/EBITDA: {ev_str}   PEG: {peg_str}
    Graham Number: {row['Graham Number']}   Current Price: ${row['Current Price']}
    Dividend Yield: {div_str}   Earnings Growth: {row['Earnings Growth (%)']:.1f}%

  Profitability
    ROE: {row['ROE (%)']:.2f}%   ROA: {row['ROA (%)']:.2f}%
    Operating Margin: {row['Operating Margin (%)']}%

  Financial Health
    Current Ratio: {row['Current Ratio']}   Debt/Equity: {de_str}

  Technical
    {row['Dist 52w High (%)']:.1f}% below 52-week high
    {abs(row['Price vs 200MA (%)']):.1f}% {ma_dir} 200-day moving average

  Market Cap: ${row['Market Cap (B)']}B   |   Industry: {row['Industry']}

  ⚠  Not financial advice – do your own due diligence.
""")


def save_results(df, suffix=''):
    """Save results to a timestamped CSV (drops internal columns)."""
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(SCRIPT_DIR, f"scan_results_{ts}{suffix}.csv")
    export   = df.drop(columns=['_criteria'], errors='ignore')
    export.to_csv(filename, index=False)
    print(f"\n  ✅ Results saved → {filename}")


# ============================================================================
# USER-INPUT HELPERS
# ============================================================================

def get_user_input(prompt, default, vtype=float):
    raw = input(f"  {prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return vtype(raw)
    except ValueError:
        print(f"  Invalid input – using default: {default}")
        return default


def parse_market_cap(raw, default=1_000_000_000):
    raw = raw.strip().upper()
    if not raw:
        return default
    mults = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}
    try:
        if raw[-1] in mults:
            return float(raw[:-1]) * mults[raw[-1]]
        return float(raw)
    except (ValueError, IndexError):
        print(f"  Invalid format – using default: {default:,.0f}")
        return default


# ============================================================================
# MAIN
# ============================================================================

SCAN_MODES = {
    '1': ('Quick Scan',     'curated 34-stock blue-chip list     (~1–2 min)'),
    '2': ('S&P 500',        '500 largest US companies            (~10–15 min)'),
    '3': ('NASDAQ Listed',  '~3,300 NASDAQ common stocks         (~1–2 hrs)'),
    '4': ('All US Stocks',  'NASDAQ + NYSE + AMEX  (~8,000+ tickers, ~3–6 hrs)'),
    '5': ('Custom',         'paste tickers or load from a file'),
}


def choose_scan_mode(suffix):
    """Let the user pick a scan mode; returns (label, tickers_list)."""

    # For non-US markets, 'all' modes don't apply
    if suffix and suffix.upper() != '.MX':
        print("\n  Non-US market detected.")
        print("  Enter tickers manually (comma-separated) or press Enter to use defaults:")
        raw = input("  > ").strip()
        if raw:
            tokens = [t.strip().upper() for t in raw.replace(',', ' ').split()]
            tickers = [t + suffix if not t.endswith(suffix) else t for t in tokens]
        else:
            tickers = [t + suffix for t in CURATED_US_TICKERS]
        return f'custom_{suffix}', tickers

    if suffix.upper() == '.MX':
        return 'mx', MX_TICKERS

    # US market scan-mode selection
    print("\n┌─ Select Scan Mode " + "─" * 36 + "┐")
    for k, (name, desc) in SCAN_MODES.items():
        print(f"│  {k}. {name:<20} {desc:<40}│")
    print("└" + "─" * 55 + "┘")

    choice = input("\n  Enter choice [1]: ").strip() or '1'
    if choice not in SCAN_MODES:
        print("  Invalid choice – using Quick Scan.")
        choice = '1'

    mode_name = SCAN_MODES[choice][0]

    if choice == '1':
        return mode_name, CURATED_US_TICKERS

    elif choice == '2':
        tickers = fetch_sp500_tickers()
        if not tickers:
            print("  Fallback: using curated list.")
            return 'Quick Scan (fallback)', CURATED_US_TICKERS
        return mode_name, tickers

    elif choice == '3':
        tickers = fetch_nasdaq_listed_tickers()
        if not tickers:
            print("  Fallback: using curated list.")
            return 'Quick Scan (fallback)', CURATED_US_TICKERS
        return mode_name, tickers

    elif choice == '4':
        tickers = fetch_all_us_tickers()
        if not tickers:
            print("  Fallback: using curated list.")
            return 'Quick Scan (fallback)', CURATED_US_TICKERS
        return mode_name, tickers

    elif choice == '5':
        tickers = fetch_custom_tickers()
        if not tickers:
            print("  No tickers entered – using curated list.")
            return 'Quick Scan (fallback)', CURATED_US_TICKERS
        return mode_name, tickers

    return 'Quick Scan', CURATED_US_TICKERS


def main():
    print()
    print("=" * 57)
    print(f"   📈  Undervalued Stocks Scanner  v{VERSION}")
    print("=" * 57)

    # ── Market suffix ────────────────────────────────────────────────────────
    print("\n--- Market ---")
    suffix_raw = input("  Market suffix (.MX, .L, etc.)  [blank = US]: ").strip()
    if suffix_raw.upper() in ('US', 'USA', ''):
        suffix = ''
        print("  → US market")
    elif suffix_raw.startswith('.'):
        suffix = suffix_raw
        print(f"  → {suffix}")
    else:
        suffix = '.' + suffix_raw
        print(f"  → Interpreted as {suffix}")

    # ── Scan mode & ticker list ──────────────────────────────────────────────
    scan_label, tickers = choose_scan_mode(suffix)
    print(f"\n  Scan: {scan_label}  |  {len(tickers):,} tickers to process")

    # ── Resume from checkpoint? ──────────────────────────────────────────────
    ckpt = load_checkpoint(scan_label)
    resume = False
    if ckpt:
        pct_done = len(ckpt) / len(tickers) * 100 if tickers else 0
        print(f"\n  ⚡ Checkpoint found: {len(ckpt):,} / {len(tickers):,} tickers"
              f" already done ({pct_done:.0f}%).")
        ans = input("  Resume from checkpoint? [Y/n]: ").strip().lower()
        resume = ans not in ('n', 'no')
        if not resume:
            # Clear checkpoint so we start fresh
            save_checkpoint(scan_label, {})
            ckpt = {}

    # ── Thresholds ───────────────────────────────────────────────────────────
    print("\n--- Valuation Thresholds ---")
    custom_thresholds = {
        'max_pe':          get_user_input("Max P/E Ratio",         15),
        'max_pb':          get_user_input("Max P/B Ratio",          2),
        'min_div_yield':   get_user_input("Min Dividend Yield (%)", 2.5),
        'min_roe':         get_user_input("Min ROE (%)",           15),
        'max_debt_equity': get_user_input("Max Debt/Equity",       100),
    }

    criteria_threshold = get_user_input(
        "\nMin criteria sets to qualify (1–6)", 3, int)

    # ── Market cap ───────────────────────────────────────────────────────────
    print("\n--- Market Cap Filter ---")
    print("  Shorthand: 500K  50M  1B  1.5T  or  raw number")
    raw_cap      = input("  Min Market Cap [1B]: ").strip()
    min_market_cap = parse_market_cap(raw_cap, 1_000_000_000)

    # ── Workers ──────────────────────────────────────────────────────────────
    print("\n--- Parallel Workers ---")
    print("  More workers = faster scan but higher chance of Yahoo rate-limiting.")
    print("  Recommended: 10 for large scans, up to 20 for quick scans.")
    max_workers = get_user_input("Number of parallel workers", 10, int)
    max_workers = max(1, min(max_workers, 50))

    # ── Confirm & go ─────────────────────────────────────────────────────────
    print()
    print("─" * 57)
    print(f"  Scan label   : {scan_label}")
    print(f"  Tickers      : {len(tickers):,}")
    print(f"  Min Mkt Cap  : ${min_market_cap:,.0f}")
    print(f"  Criteria ≥   : {criteria_threshold} / 6")
    print(f"  Workers      : {max_workers}")
    print("─" * 57)
    go = input("\n  Start scan? [Y/n]: ").strip().lower()
    if go in ('n', 'no'):
        print("  Aborted.")
        return

    print(f"\n  Scanning… (Ctrl+C to pause and save checkpoint)\n")

    start = time.time()
    results = analyze_stocks_parallel(
        tickers          = tickers,
        min_market_cap   = min_market_cap,
        criteria_threshold = criteria_threshold,
        custom_thresholds  = custom_thresholds,
        max_workers        = max_workers,
        scan_label         = scan_label,
        resume             = resume,
    )
    elapsed = time.time() - start

    # ── Results ──────────────────────────────────────────────────────────────
    print(f"\n  Scan complete in {timedelta(seconds=int(elapsed))}")
    print("=" * 57)

    if results.empty:
        print("\n  No stocks met the undervalued criteria.")
        print("  Try lowering criteria_threshold or relaxing thresholds.\n")
        return

    print(f"\n  ✅  {len(results):,} potentially undervalued stock(s) found.\n")

    # Display table (hide internal column)
    display_df = results.drop(columns=['_criteria'], errors='ignore')
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_rows', None)
    print(display_df.to_string(index=False))

    # Detailed top-picks
    top_n_input = get_user_input(
        "\nHow many top picks to show in detail", min(5, len(results)), int)
    print_recommendations(results, top_n=top_n_input)

    # Save to CSV
    save_q = input("\n  Save full results to CSV? [Y/n]: ").strip().lower()
    if save_q not in ('n', 'no'):
        save_results(results)


if __name__ == "__main__":
    main()
