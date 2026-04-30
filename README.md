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

# Login & get API token
python3 1_login_test.py
# Follow Fyers OAuth flow, token saved to access_token.txt

# Start dashboard
bash run_dashboard.sh
# Or manually:
streamlit run yuvi_dashboard.py --server.port 8502
```

Navigate to `http://localhost:8502`

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
