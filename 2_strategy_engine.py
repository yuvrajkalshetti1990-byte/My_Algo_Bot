import os
import time
import pandas as pd
import pandas_ta as ta
from fyers_apiv3 import fyersModel
import config

# ==========================================
# ⚙️ DEFAULT SETTINGS
# ==========================================
SYMBOL = "NSE:NIFTY50-INDEX"
TIMEFRAME = "5"   # Default
EMA_LEN = 20
VWMA_LEN = 35
RSI_LEN = 14
SUPERTREND_LEN = 10
SUPERTREND_MUL = 3.0

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================
def get_access_token():
    if not os.path.exists("access_token.txt"):
        print("❌ Token not found! Run 1_login_test.py first.")
        return None
    with open("access_token.txt", "r") as f:
        return f.read().strip()

# UPDATED: Now accepts 'resolution' as an input
def fetch_data(fyers, symbol, resolution="5"):
    # Fetch last 5 days
    data = {
        "symbol": symbol,
        "resolution": str(resolution),
        "date_format": "0",
        "range_from": int(time.time()) - (5 * 24 * 60 * 60), 
        "range_to": int(time.time()),
        "cont_flag": "1"
    }
    
    response = fyers.history(data=data)
    
    if "candles" not in response:
        return None
        
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(response["candles"], columns=cols)
    
    # Convert timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    df.set_index("timestamp", inplace=True)
    return df

# ==========================================
# 🧠 THE STRATEGY LOGIC
# ==========================================
def calculate_indicators(df):
    df['ema'] = ta.ema(df['close'], length=EMA_LEN)
    df['vwma'] = ta.vwma(df['close'], df['volume'], length=VWMA_LEN)
    df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    df['rsi'] = ta.rsi(df['close'], length=RSI_LEN)
    
    st = ta.supertrend(df['high'], df['low'], df['close'], length=SUPERTREND_LEN, multiplier=SUPERTREND_MUL)
    st_dir_col = f'SUPERTd_{SUPERTREND_LEN}_{SUPERTREND_MUL}'
    df['st_dir'] = st[st_dir_col]
    return df

def check_signal(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = curr['close']
    ema = curr['ema']
    vwap = curr['vwap']
    vwma = curr['vwma']
    rsi = curr['rsi']
    
    # Logic 1: BUY
    price_buy = (close > ema) and (close > vwap or close > vwma)
    ind_buy = (rsi > 40) 
    if price_buy and ind_buy:
        return "BUY (EXIT SHORT)"

    # Logic 2: SELL
    price_sell = (close < ema)
    if price_sell and rsi < 40:
        return "SELL (ENTRY SHORT)"
        
    # Logic 3: REVERSAL
    prev_green = prev['close'] > prev['open']
    prev_above_vwap = prev['close'] > prev['vwap']
    curr_red = curr['close'] < curr['open']
    prev_mid = (prev['open'] + prev['close']) / 2
    penetrated = curr['close'] < prev_mid
    
    if prev_green and prev_above_vwap and curr_red and penetrated:
        return "SELL (SMART REVERSAL) 🐻"

    return "NO SIGNAL (WAITING)"