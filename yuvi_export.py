# yuvi_export.py — Export/Import historical trading data for cloud deployment
import os
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st


DATA_DIR = Path("historical_data")
DATA_DIR.mkdir(exist_ok=True)


def export_daily_data(trade_log, strike_states, date_str=None):
    """Export today's trading data to CSV for cloud visualization.
    
    Args:
        trade_log: List of trade dictionaries from session state
        strike_states: Dict of StrikeState objects from TradeManager
        date_str: Date string (YYYY-MM-DD), defaults to today
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Export trade log
    if trade_log:
        trade_df = pd.DataFrame(trade_log)
        trade_file = DATA_DIR / f"trades_{date_str}.csv"
        trade_df.to_csv(trade_file, index=False)
        print(f"✅ Exported {len(trade_log)} trades to {trade_file}")
    
    # Export strike states (positions, P&L, etc.)
    if strike_states:
        states_data = []
        for strike_key, state in strike_states.items():
            states_data.append({
                'strike_key': strike_key,
                'position_sig': state.position_sig,
                'entry_price': state.entry_price,
                'banked_pnl': state.banked_pnl,
                'trigger_type': state.trigger_type,
                'lowest_low': state.lowest_low,
                'highest_high': state.highest_high,
                'sl_safe': state.sl_safe,
            })
        states_df = pd.DataFrame(states_data)
        states_file = DATA_DIR / f"states_{date_str}.csv"
        states_df.to_csv(states_file, index=False)
        print(f"✅ Exported {len(states_data)} strike states to {states_file}")
    
    return True


def export_candle_data(all_strikes_data, date_str=None):
    """Export OHLCV candle data for cloud replay.
    
    Args:
        all_strikes_data: Dict with strike keys → DataFrames with OHLC + indicators
        date_str: Date string (YYYY-MM-DD), defaults to today
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    for strike_key, df in all_strikes_data.items():
        if df is not None and not df.empty:
            candle_file = DATA_DIR / f"candles_{strike_key}_{date_str}.csv"
            df.to_csv(candle_file, index=False)
    
    print(f"✅ Exported candle data for {len(all_strikes_data)} strikes")
    return True


def get_available_dates():
    """Get list of dates with available historical data."""
    if not DATA_DIR.exists():
        return []
    
    dates = set()
    for file in DATA_DIR.glob("trades_*.csv"):
        # Extract date from filename: trades_2026-04-30.csv
        date_str = file.stem.split("_", 1)[1]
        dates.add(date_str)
    
    return sorted(dates, reverse=True)


def load_historical_trades(date_str):
    """Load historical trades for a specific date."""
    trade_file = DATA_DIR / f"trades_{date_str}.csv"
    if trade_file.exists():
        return pd.read_csv(trade_file).to_dict('records')
    return []


def load_historical_states(date_str):
    """Load historical strike states for a specific date."""
    states_file = DATA_DIR / f"states_{date_str}.csv"
    if states_file.exists():
        df = pd.read_csv(states_file)
        return df.to_dict('records')
    return []


def load_historical_candles(strike_key, date_str):
    """Load historical candle data for a specific strike and date."""
    candle_file = DATA_DIR / f"candles_{strike_key}_{date_str}.csv"
    if candle_file.exists():
        df = pd.read_csv(candle_file)
        # Convert timestamp string back to datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    return None


def is_cloud_mode():
    """Detect if running on Streamlit Cloud (no access_token.txt)."""
    return not os.path.exists("access_token.txt")


def get_mode_banner():
    """Return HTML banner showing current mode."""
    if is_cloud_mode():
        return """
        <div style="background:#1e3a8a;border:2px solid #3b82f6;border-radius:8px;padding:12px;margin:10px 0;text-align:center;">
            <span style="color:#93c5fd;font-size:14px;font-weight:600;">
                ☁️ CLOUD MODE - Displaying Historical Data
            </span>
        </div>
        """
    else:
        return """
        <div style="background:#14532d;border:2px solid #22c55e;border-radius:8px;padding:12px;margin:10px 0;text-align:center;">
            <span style="color:#86efac;font-size:14px;font-weight:600;">
                🔴 LIVE MODE - Real-time Trading Data
            </span>
        </div>
        """


def auto_export_on_market_close(trade_log, strike_states, all_strikes_data):
    """Automatically export data at market close (15:30 IST)."""
    now = datetime.now()
    hour, minute = now.hour, now.minute
    
    # Check if market just closed (15:30-15:31 IST)
    # Assuming system time is IST or adjust accordingly
    if hour == 15 and minute >= 30 and minute < 32:
        # Check if already exported today
        today_str = now.strftime("%Y-%m-%d")
        marker_file = DATA_DIR / f".exported_{today_str}"
        
        if not marker_file.exists():
            export_daily_data(trade_log, strike_states, today_str)
            export_candle_data(all_strikes_data, today_str)
            marker_file.touch()  # Create marker to prevent duplicate exports
            st.success(f"✅ Auto-exported trading data for {today_str}")
            return True
    
    return False
