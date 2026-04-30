# Historical Trading Data

This folder contains exported trading data for cloud dashboard visualization.

## What's Stored Here

### Trade Logs
- `trades_YYYY-MM-DD.csv` - All trades executed on that date
- Columns: timestamp, strike, entry_exit, price, qty, pnl, trigger_type, regime

### Strike States
- `states_YYYY-MM-DD.csv` - End-of-day position states per strike
- Columns: strike_key, position_sig, entry_price, banked_pnl, trigger_type, etc.

### Candle Data
- `candles_{strike}_straddle_YYYY-MM-DD.csv` - OHLC + indicators for each strike
- Columns: timestamp, open, high, low, close, volume, rsi, roc, ema, vwma, vwap, di_plus, di_minus, adx, chop

## How to Generate

### Local Mode (During Trading)
1. Run: `streamlit run yuvi_dashboard.py`
2. Data auto-exports at 15:30 IST (market close)
3. Or click **"Export to CSV"** button in sidebar anytime

### Cloud Mode (Viewing)
- Cloud dashboard reads from these CSV files
- No data export capability in cloud mode (read-only)

## Git Management

These CSV files are **safe to commit** to GitHub because they only contain:
- ✅ Public market data (prices, volumes)
- ✅ Calculated indicators
- ✅ Trade timestamps and P&L
- ❌ NO API credentials or personal info

### Keep Repo Size Manageable

```bash
# Keep only last 30 days
cd historical_data
ls -t | tail -n +91 | xargs rm  # 30 days × 3 file types

# Archive older data
tar -czf archive_$(date +%Y-%m).tar.gz trades_*.csv states_*.csv candles_*.csv
# Upload archive to GitHub Releases or external storage
```

## File Naming Convention

All files use ISO date format: `YYYY-MM-DD`

Example:
```
historical_data/
├── trades_2026-04-30.csv
├── states_2026-04-30.csv
├── candles_23900_straddle_2026-04-30.csv
├── candles_24000_straddle_2026-04-30.csv
├── candles_24100_straddle_2026-04-30.csv
├── candles_24200_straddle_2026-04-30.csv
└── candles_24300_straddle_2026-04-30.csv
```

## Sample Data

To test the cloud dashboard without trading, you can create sample CSV files:

### trades_2026-04-30.csv
```csv
timestamp,strike,entry_exit,price,qty,pnl,trigger_type,regime
2026-04-30 09:45:00,24100,SHORT_ENTRY,524.50,390,0.0,NEW,BEARISH
2026-04-30 14:30:00,24100,SHORT_EXIT,516.25,390,3217.5,TARGET,BEARISH
```

### states_2026-04-30.csv
```csv
strike_key,position_sig,entry_price,banked_pnl,trigger_type,lowest_low,highest_high,sl_safe
24100_straddle,0,0.0,3217.5,TARGET,516.25,532.75,True
```

### candles_24100_straddle_2026-04-30.csv
```csv
timestamp,open,high,low,close,volume,rsi,roc,ema,vwma,vwap,di_plus,di_minus,adx,chop
2026-04-30 09:15:00,528.75,532.50,526.00,530.25,1250,52.3,1.2,528.5,529.0,528.8,25.4,22.1,28.7,45.2
2026-04-30 09:18:00,530.25,531.00,528.50,529.75,980,51.8,0.8,529.0,529.5,529.1,24.8,22.5,27.9,44.8
```

## Troubleshooting

### "No historical data found" in Cloud Dashboard

1. Verify CSV files exist in this folder
2. Check file naming matches: `trades_YYYY-MM-DD.csv`
3. Ensure files are committed to git: `git add historical_data/ && git push`

### Data not updating in Cloud

1. Go to Streamlit Cloud app settings
2. Click "Reboot app" to force reload
3. Or commit a dummy change to trigger redeploy

## Privacy & Security

✅ **Safe to Share**: These CSV files contain only public market data  
✅ **No Credentials**: No API keys, tokens, or passwords  
✅ **No Personal Info**: No account numbers or identifying information  
✅ **Public Prices**: Only NIFTY option prices and technical indicators  

You can safely commit these files to public GitHub repositories.
