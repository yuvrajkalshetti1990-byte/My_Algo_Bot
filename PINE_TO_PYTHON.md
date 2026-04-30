# Pine Script to Python Bot Implementation Guide

## Overview

Pine Script (used in TradingView) is a Domain-Specific Language (DSL) for technical analysis. This guide shows how to convert Pine Script strategies into Python bots by mapping Pine concepts to Python/Pandas equivalents.

## Table of Contents

1. [Pine Script Fundamentals](#fundamentals)
2. [Python/Pandas Equivalents](#equivalents)
3. [Variable & Data Type Mapping](#data-types)
4. [Built-in Functions Mapping](#functions)
5. [Strategy Directives Mapping](#directives)
6. [Line-by-Line Conversion Template](#template)
7. [Common Patterns & Conversions](#patterns)

---

## Pine Script Fundamentals

### Basic Structure

```pinescript
//@version=5
strategy("Strategy Name", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

// Input variables
length = input(14, title="RSI Length")

// Indicator calculation
rsi = ta.rsi(close, length)

// Signals
buySignal = rsi < 30
sellSignal = rsi > 70

// Strategy entry/exit
if buySignal
    strategy.entry("Long", strategy.long)
if sellSignal
    strategy.close("Long")
```

---

## Python/Pandas Equivalents

### Data Structures

| Pine Script | Python/Pandas | Notes |
|---|---|---|
| `close` (array) | `df['close']` | Series of close prices |
| `high` (array) | `df['high']` | Series of highs |
| `low` (array) | `df['low']` | Series of lows |
| `volume` (array) | `df['volume']` | Series of volumes |
| `time` (array) | `df.index` | DatetimeIndex |
| Current bar value | `df.iloc[-1]['close']` | Latest value |
| Previous bar value | `df.iloc[-2]['close']` | One bar ago |
| Historical values | `df['close'].iloc[i:j]` | Range of values |

### Built-in Variables

| Pine Script | Python Equivalent | Notes |
|---|---|---|
| `bar_index` | `df.index` or `range(len(df))` | Bar position |
| `barstate.isclose` | `i == len(df) - 1` | Is current bar? |
| `barstate.isconfirmed` | `i < len(df) - 1` | Is bar closed? |
| `open`, `high`, `low`, `close` | `df['open']`, `df['high']`, etc | OHLC data |

---

## Variable & Data Type Mapping

### Pine Script Types → Python Types

```
Pine Script → Python

int → int
float → float
bool → bool
string → str
array[int] → list[int] or pd.Series
array[float] → list[float] or pd.Series
array[bool] → list[bool] or pd.Series
```

### Variable Declaration

**Pine Script**:
```pinescript
var cumulative_value = 0.0  // Persistent across bars
high_value = high           // Regular variable (resets each bar)
```

**Python**:
```python
cumulative_value = 0.0  # Store in class or session_state
high_value = df['high'].iloc[-1]  # Current bar value
```

---

## Built-in Functions Mapping

### Technical Indicator Functions

| Pine Script | Python Implementation | Notes |
|---|---|---|
| `ta.rsi(close, length)` | `calc_rsi(df, length)` | RSI calculation (see yuvi_indicators.py) |
| `ta.ema(close, length)` | `df['close'].ewm(span=length, adjust=False).mean()` | Exponential MA |
| `ta.sma(close, length)` | `df['close'].rolling(length).mean()` | Simple MA |
| `ta.roc(close, length)` | `(df['close'] - df['close'].shift(length)) / df['close'].shift(length) * 100` | Rate of Change |
| `ta.highest(close, length)` | `df['close'].rolling(length).max()` | Highest in range |
| `ta.lowest(close, length)` | `df['close'].rolling(length).min()` | Lowest in range |
| `ta.tr(true)` | `calc_true_range(df)` | True Range (custom) |
| `math.sum(close, length)` | `df['close'].rolling(length).sum()` | Sum over range |
| `math.avg(close, length)` | `df['close'].rolling(length).mean()` | Average |

### Math Functions

| Pine Script | Python | Notes |
|---|---|---|
| `math.max(a, b)` | `max(a, b)` or `np.maximum(a, b)` | Maximum |
| `math.min(a, b)` | `min(a, b)` or `np.minimum(a, b)` | Minimum |
| `math.abs(x)` | `abs(x)` or `np.abs(x)` | Absolute value |
| `math.sqrt(x)` | `math.sqrt(x)` or `np.sqrt(x)` | Square root |
| `math.log(x)` | `math.log(x)` or `np.log(x)` | Natural log |
| `math.log10(x)` | `math.log10(x)` or `np.log10(x)` | Log base 10 |
| `math.pow(x, y)` | `x ** y` or `math.pow(x, y)` | Power |

### Conditional & Control Flow

| Pine Script | Python | Notes |
|---|---|---|
| `if condition` | `if condition:` | If statement |
| `else` | `else:` | Else clause |
| `and` | `and` | Logical AND |
| `or` | `or` | Logical OR |
| `not` | `not` | Logical NOT |
| `?` (ternary) | `a if cond else b` | Ternary operator |

### Array Functions

| Pine Script | Python |
|---|---|
| `array.new<float>()` | `[]` or `np.array([])` |
| `array.push(arr, value)` | `arr.append(value)` |
| `array.get(arr, index)` | `arr[index]` |
| `array.set(arr, index, value)` | `arr[index] = value` |
| `array.size(arr)` | `len(arr)` |
| `array.last(arr)` | `arr[-1]` |

---

## Strategy Directives Mapping

### Entry & Exit Signals

**Pine Script**:
```pinescript
if buySignal
    strategy.entry("Long", strategy.long, qty=1)

if sellSignal
    strategy.exit("Exit Long", from_entry="Long", profit=10, loss=20)

if timeToClose
    strategy.close_all()
```

**Python** (via yuvi_trade_manager.py):
```python
if buy_signal:
    events.append(self._evt(strike_state, "LONG_ENTRY", price, ts, reason="BUY-SIG"))

if sell_signal:
    events.append(self._evt(strike_state, "LONG_EXIT", price, ts, reason="EXIT"))

if time_to_close:
    events.append(self._evt(strike_state, "LONG_EXIT", price, ts, reason="TIME EXIT"))
```

### Position Management

| Pine Script | Python Equivalent |
|---|---|
| `strategy.entry()` | Record `LONG_ENTRY` / `SHORT_ENTRY` event |
| `strategy.exit()` | Record `LONG_EXIT` / `SHORT_EXIT` event |
| `strategy.close()` | Record exit event |
| `strategy.position_size` | Track `s.long_qty`, `s.short_qty` in StrikeState |
| `strategy.openprofit` | Calculate from `entry_price` vs `current_price` |

---

## Line-by-Line Conversion Template

### Example 1: Simple RSI Strategy

**Pine Script**:
```pinescript
//@version=5
strategy("RSI Trading", overlay=false)

// Input
length = input(14, "RSI Length")
overbought = input(70, "Overbought")
oversold = input(30, "Oversold")

// Calculation
rsi = ta.rsi(close, length)

// Signals
buySignal = rsi < oversold
sellSignal = rsi > overbought

// Entry/Exit
if buySignal and barstate.isconfirmed
    strategy.entry("Buy", strategy.long)

if sellSignal and barstate.isconfirmed
    strategy.close("Buy")

plot(rsi, "RSI", color=color.blue)
plot(overbought, "Overbought", color=color.red, linewidth=1, linestyle=hline.dashed)
plot(oversold, "Oversold", color=color.green, linewidth=1, linestyle=hline.dashed)
```

**Python Conversion**:

```python
# ─── 1. Imports ───────────────────────────────────────────────
import pandas as pd
import numpy as np
from yuvi_indicators import calc_rsi  # Custom RSI function
from yuvi_trade_manager import TradeManager

# ─── 2. Configuration (input equivalent) ────────────────────
cfg_rsi_length = 14
cfg_overbought = 70
cfg_oversold = 30

# ─── 3. Data Loading ──────────────────────────────────────
# Pine Script processes bars sequentially from API
# Python loads all bars upfront
df = fetch_ohlcv(fyers, symbol)  # DataFrame with OHLCV

# ─── 4. Indicator Calculation (equivalent to ta.rsi) ───────
df['rsi'] = calc_rsi(df, cfg_rsi_length)

# ─── 5. Signal Generation ─────────────────────────────────
# Pine Script: evaluates condition on each bar
# Python: vectorized or loop through bars
df['buy_signal'] = df['rsi'] < cfg_oversold
df['sell_signal'] = df['rsi'] > cfg_overbought

# ─── 6. Strategy Logic (entry/exit) ────────────────────────
trade_manager = TradeManager()
trade_log = []

for i in range(1, len(df)):  # Start from bar 1 (previous bar exists)
    row = df.iloc[i]
    prev_row = df.iloc[i-1]
    ts = df.index[i]
    
    # Bar confirmed = previous bar (not current bar)
    if prev_row['buy_signal'] and not trade_manager.is_long:
        events = trade_manager.enter_long(row['close'], ts, reason="RSI_OVERSOLD")
        trade_log.extend(events)
    
    if prev_row['sell_signal'] and trade_manager.is_long:
        events = trade_manager.exit_long(row['close'], ts, reason="RSI_OVERBOUGHT")
        trade_log.extend(events)

# ─── 7. Plotting / Visualization ───────────────────────────
# Pine Script: automatic via strategy.plotXxx()
# Python: Streamlit for dashboard
import streamlit as st
st.line_chart(df['rsi'])
```

### Example 2: Moving Average Crossover

**Pine Script**:
```pinescript
//@version=5
strategy("MA Cross", overlay=true)

// Inputs
fastLen = input(20, "Fast MA")
slowLen = input(50, "Slow MA")

// Calculation
fast = ta.ema(close, fastLen)
slow = ta.ema(close, slowLen)

// Signals
bullish = fast > slow
bearish = fast < slow

// Strategy
if bullish and not bullish[1]
    strategy.entry("Long", strategy.long)

if bearish and not bearish[1]
    strategy.close("Long")

plot(fast, "Fast EMA", color=color.blue)
plot(slow, "Slow EMA", color=color.orange)
```

**Python Conversion**:

```python
# ─── Configuration ────────────────────────────────────────
fast_len = 20
slow_len = 50

# ─── Calculations (ta.ema equivalent) ─────────────────────
df['fast_ema'] = df['close'].ewm(span=fast_len, adjust=False).mean()
df['slow_ema'] = df['close'].ewm(span=slow_len, adjust=False).mean()

# ─── Signals ──────────────────────────────────────────────
df['bullish'] = df['fast_ema'] > df['slow_ema']
df['bearish'] = df['fast_ema'] < df['slow_ema']

# Crossover detection (not bullish[1] equivalent)
df['bullish_cross'] = df['bullish'] & ~df['bullish'].shift(1)
df['bearish_cross'] = df['bearish'] & ~df['bearish'].shift(1)

# ─── Strategy Logic ───────────────────────────────────────
for i in range(2, len(df)):  # Need 2 bars for crossover
    if df.iloc[i-1]['bullish_cross']:  # Confirmed crossover
        # Execute buy
        pass
    
    if df.iloc[i-1]['bearish_cross']:  # Confirmed crossover
        # Execute sell
        pass

# ─── Dashboard ─────────────────────────────────────────────
st.line_chart(df[['fast_ema', 'slow_ema']])
```

---

## Common Patterns & Conversions

### Pattern 1: Previous Bar Values

**Pine Script**:
```pinescript
prev_close = close[1]  // Refer to 1 bar ago
change = close - prev_close
```

**Python**:
```python
prev_close = df['close'].shift(1)  # 1 bar ago
change = df['close'] - prev_close
# Or for specific index i:
prev_close_i = df['close'].iloc[i-1]
```

### Pattern 2: Crossovers

**Pine Script**:
```pinescript
bullish = fast > slow
bearish = fast < slow
buy_cross = bullish and not bullish[1]  // Crossover detection
sell_cross = bearish and not bearish[1]
```

**Python**:
```python
bullish = df['fast'] > df['slow']
bearish = df['fast'] < df['slow']

buy_cross = bullish & ~bullish.shift(1)
sell_cross = bearish & ~bearish.shift(1)

# Or in loop:
if df['fast'].iloc[i] > df['slow'].iloc[i] and \
   df['fast'].iloc[i-1] <= df['slow'].iloc[i-1]:
    # Bullish crossover detected
    pass
```

### Pattern 3: Conditional Entry/Exit

**Pine Script**:
```pinescript
if signal and close > ema20 and volume > avgVolume
    strategy.entry("Long", strategy.long, qty=position_size)

if highestHigh > upperBand
    strategy.exit("Long", profit=targetPts, loss=stopPts)
```

**Python**:
```python
if signal and df['close'].iloc[i] > df['ema20'].iloc[i] and \
   df['volume'].iloc[i] > df['avg_volume'].iloc[i]:
    # Entry logic
    trade_manager.enter_long(df['close'].iloc[i], ts, qty=position_size)

if df['high'].iloc[i] > df['upper_band'].iloc[i]:
    # Exit logic with profit/loss targets
    profit_pts = target_pts
    loss_pts = stop_pts
    trade_manager.exit_long(...)
```

### Pattern 4: State Variables (var keyword)

**Pine Script**:
```pinescript
var entryPrice = 0.0
var tradeCount = 0

if buySignal
    entryPrice := close
    tradeCount := tradeCount + 1
```

**Python**:
```python
# Use class attributes or Streamlit session_state
class TradeState:
    entry_price = 0.0
    trade_count = 0

# Or in loop with persistent storage:
if buy_signal:
    trade_state.entry_price = df['close'].iloc[i]
    trade_state.trade_count += 1

# Or Streamlit:
if 'entry_price' not in st.session_state:
    st.session_state.entry_price = 0.0
```

### Pattern 5: Time-based Conditions

**Pine Script**:
```pinescript
sessionStart = time(timeframe.period, "09:15")
isSessionOpen = time >= sessionStart

if buySignal and isSessionOpen
    strategy.entry("Long", strategy.long)
```

**Python**:
```python
from datetime import time, datetime

def is_session_open(bar_time, start_time="09:15"):
    hour, minute = map(int, start_time.split(":"))
    bar_hour = bar_time.hour
    bar_minute = bar_time.minute
    return (bar_hour * 60 + bar_minute) >= (hour * 60 + minute)

for i, row in df.iterrows():
    if buy_signal and is_session_open(row.name):
        # Execute trade
        pass
```

### Pattern 6: Target & Stop Loss

**Pine Script**:
```pinescript
strategy.exit("Exit", from_entry="Long", profit=targetPts, loss=stopPts)
```

**Python**:
```python
def calc_exit_signal(entry_price, current_price, target_pts, stop_pts):
    pnl = current_price - entry_price
    return pnl >= target_pts or pnl <= -stop_pts

# In loop:
if position_open:
    if calc_exit_signal(entry_price, df['close'].iloc[i], target_pts, stop_pts):
        trade_manager.exit_long(df['close'].iloc[i], ts, reason="TARGET_STOP")
```

---

## Step-by-Step Conversion Checklist

When converting any Pine Script, follow this checklist:

```
□ 1. Extract inputs/parameters (input() functions)
□ 2. Map OHLCV data to DataFrame
□ 3. Identify all indicators used → map to Python functions
□ 4. Create signal generation logic (vectorized or loop)
□ 5. Implement entry conditions
□ 6. Implement exit conditions (profit targets, stops, time-based)
□ 7. Track position state (open/closed, entry price, qty)
□ 8. Calculate P&L
□ 9. Add position management (max positions, scaling, etc.)
□ 10. Implement logging/dashboard visualization
□ 11. Backtest on historical data
□ 12. Paper trade before live execution
```

---

## Key Differences: Pine Script vs Python

| Aspect | Pine Script | Python | Impact |
|--------|-----------|--------|--------|
| **Execution** | Bar-by-bar (real-time) | Batch processing | Python needs replay logic for historical bars |
| **Arrays** | Circular (oldest data at end) | Sequential (oldest at start) | Use `.shift()` and `.iloc[i-1]` carefully |
| **Time** | Built-in `time` function | Use `datetime` module | Need explicit timezone handling |
| **Orders** | Automatic position tracking | Manual state management | Use TradeManager class to track state |
| **Plotting** | Built-in `plot()` | Streamlit/Matplotlib | Need separate visualization layer |
| **Performance** | Single-threaded real-time | Vectorized Pandas operations | Python is faster for backtesting |

---

## Debugging Tips

### Compare Pin Script vs Python output:

```python
# Export Pine Script values for comparison
pine_values = {
    'rsi': [...],  # From TradingView export
    'ema': [...],
    'signals': [...]
}

# Calculate same in Python
py_rsi = calc_rsi(df, 14)
py_ema = calc_ema(df, 20)

# Compare (should match within 1-2 units due to data timing)
diff = abs(pine_values['rsi'] - py_rsi.values)
print(f"Max RSI difference: {diff.max()}")
```

### Common issues:

1. **Off-by-one errors**: Pine uses `[1]` for previous bar, Python uses `.shift(1)` (more intuitive)
2. **Indicator divergence**: Check smoothing method (EMA vs SMA, Wilder's vs exponential)
3. **Signal timing**: Pine confirms on closed bar, Python needs explicit confirmation check
4. **Time zones**: Pine auto-converts, Python needs manual conversion via `pytz`

---

## Next Steps

1. **Paste your Pine Script** below for line-by-line analysis
2. **Map each function** to Python equivalent using this guide
3. **Implement in Python** using template structure
4. **Backtest** using historical data
5. **Deploy** to TradeManager (see yuvi_trade_manager.py)

---

**Ready to convert your Pine Script? Share it below for detailed line-by-line analysis.**
