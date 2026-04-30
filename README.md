# NIFTY Options Algorithmic Trading Bot

A real-time algorithmic trading system for NIFTY index options (straddle strategy) with live dashboard, indicator calculations, and position tracking.

## Overview

This bot automates:
- **Straddle Strategy**: Long on ITM1/OTM1, Short on ATM simultaneously
- **Real-time Data**: 3-min candles via Fyers API v3
- **Technical Indicators**: RSI, ROC, EMA, VWMA, VWAP, DMI (Wilder's), CHOP
- **Position Management**: Entry/exit signals, target hits, time-based exits, trailing stops
- **Dashboard**: Live P&L tracking, indicator heatmaps, account summary

## Key Features

### Trading Logic
- **Straddle Premium**: Combined CE + PE prices as single instrument
- **Correct H/L Calculation**: `max(CE_H + PE_L, CE_L + PE_H, O, C)` — accounts for inverse CE/PE movement
- **Signal Detection**: Crossover-based entry (3-bar confirmation window), target-based exits
- **Risk Management**: 
  - Fixed stop loss (configurable)
  - Profit targets (ITM1/OTM1 = 10 pts target)
  - Time-based hard exits (15:15 for shorts, 14:30 for longs)
  - Trailing stop loss on ATM short (configurable trigger + distance)

### Dashboard (Streamlit)
- **Market Overview**: Strike-wise OHLC, LTP, indicators per strike
- **ATM Indicators**: Real-time RSI, ROC, +DI, -DI, ADX, CHOP
- **P&L Table**: Per-strike entry/exit times, points, rupees, trigger reason
- **Account Summary**: Capital, day P&L, floating P&L, trade history
- **Controls**: Refresh, Reset Day, Dry Run, Timeframe selector (3/5 min)

## Installation

### Prerequisites
- Python 3.8+
- macOS/Linux/Windows
- Fyers API access (https://api.fyers.in)

### Setup

```bash
# Clone repository
git clone https://github.com/yuvrajkalshetti1990-byte/My_Algo_Bot.git
cd My_Algo_Bot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt  # (if exists, else manually):
pip install fyers-apiv3 pandas streamlit ta-lib

# Configure API credentials
cp config.example.py config.py
# Edit config.py with your real Fyers credentials (CLIENT_ID, SECRET_KEY)
# ⚠️ NEVER commit config.py to git — it's excluded via .gitignore

# Login & get API token
python3 1_login_test.py
# Follow Fyers OAuth flow, token saved to access_token.txt

# Start dashboard
bash run_dashboard.sh
# Or manually:
streamlit run yuvi_dashboard.py --server.port 8502
```

Navigate to `http://localhost:8502`

## 🔐 Security

**Protected Files** (excluded via `.gitignore`):
- `config.py` — Contains CLIENT_ID, SECRET_KEY for Fyers API
- `access_token.txt` — OAuth access token (auto-refreshed)
- `*.log` — May contain API responses

**Setup Instructions**:
1. Copy `config.example.py` → `config.py`
2. Add your real Fyers API credentials to `config.py`
3. NEVER commit `config.py` or `access_token.txt` to git

**⚠️ IMPORTANT**: If you accidentally committed credentials:
1. **Immediately** rotate/invalidate them on Fyers Dashboard
2. Update `config.py` with new credentials locally
3. Verify `.gitignore` excludes `config.py`
4. Consider cleaning git history: `git filter-branch` or BFG Repo-Cleaner

## Configuration

Edit [strategy_config.py](strategy_config.py):

```python
# Index & Expiry
INDEX_NAME = "NIFTY"
EXP_YY = "26"  # 2026
EXP_MM = "05"  # May
EXP_DD = "05"  # Day 5
STRIKES = [23900, 24000, 24100, 24200, 24300]  # ATM at index 2

# Timeframe & Data
TIMEFRAME = "3"  # 3-min candles (or "5" for 5-min)
CROSSOVER_WINDOW = 5  # bars for confirmation

# Indicator Periods
RSI_LEN = 14
ROC_LEN = 9      # Matches Sensibull's default
DMI_LEN = 14
EMA_LEN = 20
VWMA_LEN = 15
CHOP_LEN = 14

# Trading Scope (per-strike)
LONG_SCOPE = [False, True, False, True, False]   # ITM1, OTM1
SHORT_SCOPE = [False, False, True, False, False] # ATM only

# Position Sizing
LOT_SIZE = 65
LOTS_LONG = 6
LOTS_SHORT = 6
MAX_LONG_TRADES = 1  # Max 1 long trade per day

# Targets & Stops
LONG_TARGET = 10.0          # pts
LONG_SL = 50.0              # pts (disabled if 0)
SHORT_SL_POINTS = 50.0      # pts

# P&L Tracking
INIT_CAPITAL = 2_300_000.0  # ₹

# Exit Times
LONG_START_TIME = "09:30"
HARD_EXIT_HOUR_SHORT = 15
HARD_EXIT_MIN_SHORT = 15    # 3:15 PM
HARD_EXIT_HOUR_LONG = 14
HARD_EXIT_MIN_LONG = 30     # 2:30 PM

# Trailing Stop Loss (ATM short only)
USE_SHORT_TSL = True
TSL_SHORT_TRIGGER = 20.0    # pts profit to activate TSL
TSL_SHORT_DIST = 15.0       # pts behind peak to exit
```

## File Structure

```
My_Algo_Bot/
├── yuvi_dashboard.py          # Streamlit UI, replay logic, rendering
├── yuvi_data.py               # Fyers API, OHLCV fetch, straddle combine
├── yuvi_indicators.py         # RSI, ROC, DMI (Wilder's), CHOP, VWAP
├── yuvi_trade_manager.py      # Signal detection, position tracking
├── strategy_config.py         # All trading parameters
├── config.py                  # API credentials (CLIENT_ID)
├── 1_login_test.py            # Fyers OAuth flow, token refresh
├── 2_strategy_engine.py       # Legacy strategy (reference)
├── 3_dashboard.py             # Legacy dashboard (reference)
├── run_dashboard.sh           # Launcher script
└── .gitignore                 # Protect access_token.txt, logs
```

## Recent Fixes (v1.0 — fyers-hl-fix branch)

### Straddle High/Low Formula Fix
**Problem**: Previous formula `max(open, close)` / `min(open, close)` ignored CE/PE individual intrabar extremes, making True Range ~10x too small.

**Root Cause**: CE and PE move inversely. When Nifty is at intrabar HIGH, CE peaks while PE troughs (and vice versa). A naive `CE_H + PE_H` would triple-count the movement.

**Solution**: Correct formula captures all edge cases:
```python
_h1 = CE_high + PE_low   # Nifty at HIGH: CE ↑, PE ↓
_h2 = CE_low + PE_high   # Nifty at LOW: CE ↓, PE ↑
straddle_high = max(_h1, _h2, open, close)
straddle_low = min(_h1, _h2, open, close)
```

**Impact**: DMI/CHOP now match Sensibull within <1 unit
- +DI: 32.0 → **25.4** (Sensibull: 24.82) ✓
- -DI: 39.2 → **35.3** (Sensibull: 36.19) ✓
- CHOP: 40.3 → **42.5** (Sensibull: 41.69) ✓

### ROC Period: 14 → 9
Sensibull chart labels "ROC 9". Changed config default to match.

### Timeframe Default: 5-min → 3-min
Chart data uses 3-min candles. Added radio toggle in sidebar to switch 3/5-min on-the-fly.

### ATM Label Fix
Previously baked into `last_data` at fetch time. Now recomputed at render time using current `cfg.ATM_IDX`.

## Usage

### Live Trading
```bash
# Terminal 1: Start dashboard
streamlit run yuvi_dashboard.py --server.port 8502

# Terminal 2: Monitor logs
tail -f /tmp/dash_log.txt
```

1. **Refresh**: Fetches latest data, runs full intraday replay from 09:15, processes bars, executes live signals
2. **Dry Run**: Same as Refresh but no orders sent (test signals)
3. **Reset Day**: Clears all trades/state, starts fresh

### Indicators Section
**ATM Indicators** shows the latest bar values for the current straddle:
- Green = bullish signal
- Red = bearish signal

### P&L Table
| Column | Meaning |
|--------|---------|
| STRIKE | Strike symbol (ATM/ITM1/OTM1) |
| ENTRY | Entry time (HH:MM) |
| EXIT | Exit time or "OPEN" |
| LOTS | Contracts traded |
| PRICE | Entry price |
| PTS | Points profit/loss |
| P&L | Rupee profit/loss |
| TRIG | Signal trigger (BUY-V, OLD, TGT HIT, etc.) |
| S | Short trade count |
| B | Long trade count |

## Data Sources

### Fyers API v3
- **Resolution**: Minute candles (1, 3, 5, 15, 60)
- **Range**: Last 5 days (rolling)
- **Timezone**: Asia/Kolkata (IST)
- **Alignment**: Common timestamps across CE/PE via `df.align(..., join='inner')`

### Symbol Format
```
NSE:NIFTY{YY}{MCODE}{DD}{STRIKE}{CE|PE}
Example: NSE:NIFTY2650524000CE  (May 5 2026, 24000 CE)
```

## Technical Indicators & Formulas

All indicators are calculated on the **straddle combined OHLCV** (not individual CE/PE). Implementation details below for anyone implementing a chart or replicating these calculations.

### 1. Relative Strength Index (RSI)

**Period**: 14 bars (configurable via `RSI_LEN`)  
**Source**: Close prices

**Formula**:
```
Gain = max(Close[i] - Close[i-1], 0)
Loss = max(Close[i-1] - Close[i], 0)

AvgGain = SMA(Gain, 14)
AvgLoss = SMA(Loss, 14)

RS = AvgGain / AvgLoss
RSI = 100 - (100 / (1 + RS))

Range: 0-100
Overbought: RSI > 70
Oversold: RSI < 30
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L50)):
```python
def calc_rsi(df, length=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(span=length, adjust=False).mean()
    avg_loss = loss.ewm(span=length, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
```

**Charting**:
- **Y-axis Range**: 0-100
- **Midline**: 50 (neutral)
- **Overbought Band**: 70 (red dashed)
- **Oversold Band**: 30 (blue dashed)
- **Color**: Purple line

---

### 2. Rate of Change (ROC)

**Period**: 9 bars (configurable via `ROC_LEN`)  
**Source**: Close prices

**Formula**:
```
ROC = ((Close[i] - Close[i-9]) / Close[i-9]) × 100

Range: -100 to +∞ (typically -20 to +20 for options)
Bullish: ROC > 0
Bearish: ROC < 0
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L70)):
```python
def calc_roc(df, length=9):
    return ((df['close'] - df['close'].shift(length)) / df['close'].shift(length)) * 100
```

**Charting**:
- **Y-axis Range**: -10 to +10 (typical)
- **Midline**: 0 (zero line)
- **Color**: Blue line
- **Signal**: Positive ROC = momentum up, Negative = momentum down

---

### 3. Exponential Moving Average (EMA)

**Period**: 20 bars (configurable via `EMA_LEN`)  
**Source**: Close prices

**Formula**:
```
Multiplier = 2 / (Length + 1) = 2 / 21 = 0.0952

EMA[1] = SMA(first 20 closes)
EMA[i] = Close[i] × Multiplier + EMA[i-1] × (1 - Multiplier)
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L85)):
```python
def calc_ema(df, length=20):
    return df['close'].ewm(span=length, adjust=False).mean()
```

**Charting**:
- **Color**: Teal/cyan line
- **Overlay**: Plot directly on candlestick chart
- **Signal**: Price > EMA = uptrend, Price < EMA = downtrend

---

### 4. Volume-Weighted Moving Average (VWMA)

**Period**: 15 bars (configurable via `VWMA_LEN`)  
**Source**: Close × Volume

**Formula**:
```
VWMA = Σ(Close[i] × Volume[i]) / Σ(Volume[i])   [last 15 bars]

Gives more weight to high-volume bars
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L100)):
```python
def calc_vwma(df, length=15):
    return (df['close'] * df['volume']).rolling(length).sum() / df['volume'].rolling(length).sum()
```

**Charting**:
- **Color**: Orange line
- **Overlay**: Plot on candlestick chart
- **Signal**: VWMA helps identify support/resistance levels weighted by volume

---

### 5. Volume-Weighted Average Price (VWAP)

**Period**: Daily reset (resets at 09:15)  
**Source**: Cumulative OHLC × Volume

**Formula**:
```
Typical Price = (High + Low + Close) / 3
Cumulative TP×Vol = Σ(Typical Price[i] × Volume[i])
Cumulative Vol = Σ(Volume[i])

VWAP = Cumulative TP×Vol / Cumulative Vol

Resets daily at market open (09:15)
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L115)):
```python
def calc_vwap(df):
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_vol'] = df['typical_price'] * df['volume']
    
    df['date'] = df.index.date
    df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
    df['cum_vol'] = df.groupby('date')['volume'].cumsum()
    
    vwap = df['cum_tp_vol'] / df['cum_vol']
    return vwap
```

**Charting**:
- **Color**: Yellow/gold line
- **Overlay**: Plot on candlestick chart
- **Reset**: Daily at 09:15 (market open)
- **Signal**: Price > VWAP = strong buyers, Price < VWAP = strong sellers

---

### 6. Directional Movement Index (DMI) & Average Directional Index (ADX)

**Period**: 14 bars (configurable via `DMI_LEN`)  
**Smoothing**: Wilder's RMA (not EMA)

**Formula (Part 1: Directional Movement)**:
```
Up Move = High[i] - High[i-1]
Down Move = Low[i-1] - Low[i]

True Range (TR) = max(
    High[i] - Low[i],
    High[i] - Close[i-1],
    Close[i-1] - Low[i]
)

+DM = Up Move if Up Move > Down Move and Up Move > 0, else 0
-DM = Down Move if Down Move > Up Move and Down Move > 0, else 0
```

**Formula (Part 2: Wilder's Smoothing — CRITICAL)**:
```
Unlike EMA, Wilder's RMA uses:
RMA[1] = SMA(first 14 values)
RMA[i] = (RMA[i-1] × (length-1) + Value[i]) / length

This is DIFFERENT from EMA's exponential smoothing.
```

**Formula (Part 3: Directional Indicators)**:
```
+DI = 100 × RMA(+DM, 14) / RMA(TR, 14)
-DI = 100 × RMA(-DM, 14) / RMA(TR, 14)

Range: 0-100
Bullish: +DI > -DI
Bearish: -DI > +DI
```

**Formula (Part 4: ADX)**:
```
DI Diff = |+DI - -DI|
DI Sum = +DI + -DI

DX = 100 × (DI Diff / DI Sum)
ADX = RMA(DX, 14)   [Wilder's smoothing]

Range: 0-100
Strong Trend: ADX > 25
Weak Trend: ADX < 20
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L160)):
```python
def calc_dmi(df, length=14):
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()
    
    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    
    tr = calc_true_range(df)
    
    # Wilder's RMA (critical — NOT EMA)
    def rma(values, length):
        rma_vals = np.zeros(len(values))
        rma_vals[:length] = np.mean(values[:length])
        for i in range(length, len(values)):
            rma_vals[i] = (rma_vals[i-1] * (length-1) + values[i]) / length
        return rma_vals
    
    plus_di_raw = rma(plus_dm, length) / rma(tr, length) * 100
    minus_di_raw = rma(minus_dm, length) / rma(tr, length) * 100
    
    di_diff = np.abs(plus_di_raw - minus_di_raw)
    di_sum = plus_di_raw + minus_di_raw
    dx = (di_diff / di_sum) * 100
    adx = rma(dx, length)
    
    return plus_di_raw, minus_di_raw, adx
```

**Charting**:
- **+DI Line**: Blue line (bullish)
- **-DI Line**: Red/orange line (bearish)
- **ADX Line**: Yellow line (trend strength)
- **Y-axis Range**: 0-100
- **Strong Trend Band**: 25 (dashed gray)
- **Overlay**: Plot below candlestick chart
- **Signal**: +DI crossover -DI = BUY, -DI crossover +DI = SELL

---

### 7. Choppiness Index (CHOP)

**Period**: 14 bars (configurable via `CHOP_LEN`)  
**Source**: High, Low, Close

**Formula**:
```
Highest High = max(High[i-13...i])
Lowest Low = min(Low[i-13...i])

Sum of TR = Σ(True Range[i-13...i])

CHOP = 100 × log10(Sum of TR / (Highest High - Lowest Low)) / log10(14)

Range: 0-100
Choppy Market: CHOP > 50
Trending Market: CHOP < 50
Strong Trend: CHOP < 30
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L200)):
```python
def calc_chop(df, length=14):
    tr = calc_true_range(df)
    highest_high = df['high'].rolling(window=length).max()
    lowest_low = df['low'].rolling(window=length).min()
    
    sum_tr = tr.rolling(window=length).sum()
    range_val = highest_high - lowest_low
    
    chop = 100 * np.log10(sum_tr / range_val) / np.log10(length)
    return chop
```

**Charting**:
- **Y-axis Range**: 0-100
- **Midline**: 50 (trend/chop boundary)
- **Choppy Zone**: > 50 (light blue shading)
- **Trending Zone**: < 50 (light gray shading)
- **Color**: Blue line
- **Signal**: Low CHOP = strong trend (good for momentum trades)

---

### 8. True Range (TR)

**Used by**: DMI, CHOP, ATR  
**Source**: High, Low, Close

**Formula**:
```
TR = max(
    High[i] - Low[i],
    |High[i] - Close[i-1]|,
    |Close[i-1] - Low[i]|
)
```

**Implementation** ([yuvi_indicators.py](yuvi_indicators.py#L50)):
```python
def calc_true_range(df):
    tr = pd.DataFrame()
    tr['h_l'] = df['high'] - df['low']
    tr['h_c'] = np.abs(df['high'] - df['close'].shift())
    tr['l_c'] = np.abs(df['low'] - df['close'].shift())
    
    return tr[['h_l', 'h_c', 'l_c']].max(axis=1)
```

---

### 9. Straddle High/Low (CRITICAL FIX)

**Problem**: Naive `max(O,C)` / `min(O,C)` ignores CE/PE intrabar movement.

**Root Cause**: CE and PE move inversely:
- When Nifty is at intrabar HIGH → CE peaks, PE troughs
- When Nifty is at intrabar LOW → CE troughs, PE peaks

**Correct Formula**:
```
_h1 = CE_High + PE_Low    (Nifty at HIGH)
_h2 = CE_Low + PE_High    (Nifty at LOW)

Straddle_High = max(_h1, _h2, Open, Close)
Straddle_Low = min(_h1, _h2, Open, Close)
```

**Implementation** ([yuvi_data.py](yuvi_data.py#L95)):
```python
_h1 = ce_df["high"] + pe_df["low"]
_h2 = ce_df["low"]  + pe_df["high"]
combined["high"] = pd.concat(
    [combined["open"], combined["close"], _h1, _h2], 
    axis=1
).max(axis=1)
combined["low"] = pd.concat(
    [combined["open"], combined["close"], _h1, _h2], 
    axis=1
).min(axis=1)
```

**Impact**:
- True Range now accurately reflects straddle volatility
- DMI/CHOP within 1 unit of professional charts (Sensibull)
- Before fix: DMI off by 7-10 units, CHOP off by 1-2 units

---

## Implementation Guide for Charting

To implement a similar chart (TradingView Pine Script, JavaScript, etc.):

1. **Fetch straddle data**: CE + PE OHLCV combined (see Formula 9)
2. **Calculate indicators in order**:
   - First: True Range (dependency for DMI, CHOP)
   - Then: RSI, ROC, EMA, VWMA, VWAP, DMI (Wilder's RMA critical!), CHOP
3. **Candlestick overlay**:
   - OHLC candles + EMA(20) + VWMA(15) + VWAP (daily reset)
4. **Sub-panels**:
   - Top: RSI (0-100)
   - Middle: ROC (-∞ to +∞)
   - Bottom: DMI (+DI, -DI, ADX) + CHOP (0-100)

**Key Points**:
- ✅ Use Wilder's RMA for DMI/ADX, NOT EMA
- ✅ Reset VWAP daily at 09:15
- ✅ Use correct straddle H/L formula (not `CE_H+PE_H`)
- ✅ All calculations on combined close, not individual CE/PE

---

## Troubleshooting

### Dashboard shows old data
**Solution**: Click **Refresh** button. Replay key includes timeframe — changing 3/5 min triggers full replay.

### Missing trades in P&L
**Root Cause**: `MAX_LONG_TRADES=1` limits to 1 long trade/day. After ITM1 enters, OTM1 is blocked.
**Fix**: Increase `MAX_LONG_TRADES` or adjust `LONG_SCOPE`.

### Indicator mismatch vs Sensibull
- **Small gap (<1 unit)**: Data feed difference (Fyers vs NSE live feed settle bar close at slightly different prices)
- **Large gap (>5 units)**: Check H/L formula is using correct CE_H+PE_L / CE_L+PE_H logic

### API Token expired
```bash
python3 1_login_test.py
# Follow OAuth flow again, token auto-updates
```

## Performance Metrics (2026-04-30)

| Metric | Value |
|--------|-------|
| Day P&L | +₹22,191 |
| Trades | 3 (1 LONG: OTM1, 1 LONG: ITM1, 2 SHORT: ATM) |
| Avg Points/Trade | +18.97 pts |
| Capital Used | ₹2.3M |
| Return | +0.96% |

## Technical Stack

- **Framework**: Streamlit (real-time web dashboard)
- **Data**: Fyers API v3 (NSE NIFTY options)
- **Indicators**: Custom RSI/ROC/DMI (Wilder's smoothing), TA-Lib for CHOP/VWAP
- **Language**: Python 3.8+
- **Deployment**: Local machine (no cloud)

## Next Steps

1. **Paper Trading**: Run on demo account first
2. **Backtest**: Replay historical data before going live
3. **Risk Limits**: Set max daily loss, position size caps
4. **Monitoring**: Log all trades, review daily P&L
5. **Optimization**: Fine-tune indicator periods per market conditions

## Disclaimer

This is an **educational/experimental** trading bot. Use at your own risk. Options trading involves significant risk of loss. Not financial advice.

## Support

- **Fyers Docs**: https://api.fyers.in/docs
- **Issues**: Check `.log` files in `~/.fyers/` for API errors
- **Logs**: `fyersApi.log`, `fyersRequests.log` (excluded from git)

---

**Last Updated**: 2026-04-30  
**Branch**: `fyers-hl-fix`  
**Status**: ✅ H/L fix validated, indicator accuracy improved
