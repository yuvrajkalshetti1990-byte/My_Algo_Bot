# Hybrid Deployment Guide — Trade Locally + Share Cloud Dashboard

This bot now supports **Hybrid Deployment**: trade with live data locally during market hours, then automatically export your results and share them via Streamlit Cloud.

---

## 🎯 How It Works

### Local Mode (Your Trading Machine)
- ✅ Full Fyers OAuth authentication
- ✅ Real-time market data via Fyers API
- ✅ Live position tracking and P&L
- ✅ **Auto-exports data at 15:30 IST** (market close)
- ✅ Manual export anytime via sidebar button

### Cloud Mode (Streamlit Cloud)
- ☁️ No API credentials needed in secrets
- ☁️ Displays historical data from CSV files
- ☁️ Public URL you can share with anyone
- ☁️ Date selector to view different trading days
- ☁️ Read-only dashboard (no live trading)

---

## 🚀 Setup Guide

### Part 1: Local Trading Setup (One-time)

```bash
cd ~/Desktop/My_Algo_Bot
source .venv/bin/activate

# Configure your credentials
cp config.example.py config.py
# Edit config.py with your Fyers CLIENT_ID and SECRET_KEY

# Login and get access token
python3 1_login_test.py

# Start trading dashboard
streamlit run yuvi_dashboard.py --server.port 8502
```

**During Trading:**
- Dashboard runs locally at `http://localhost:8502`
- Data auto-exports daily at 15:30 IST to `historical_data/` folder
- Or click **"Export to CSV"** button in sidebar anytime

### Part 2: Cloud Dashboard Setup (One-time)

#### Step 1: Deploy to Streamlit Cloud

1. Visit: https://share.streamlit.io/
2. Click **"New app"**
3. Configure:
   - **Repository**: `yuvrajkalshetti1990-byte/My_Algo_Bot`
   - **Branch**: `fyers-hl-fix`
   - **Main file path**: `yuvi_dashboard.py`
   - **Python version**: `3.9`
4. Click **"Deploy"**

#### Step 2: Upload Historical Data

After your first deployment, the app will show: "No historical data found"

**Option A: Manual Upload (Quick Start)**

1. After trading locally, your data is in `~/Desktop/My_Algo_Bot/historical_data/`
2. Go to your Streamlit Cloud app → **⚙️ Settings** → **Secrets**
3. You can add a few sample CSV files directly to the repo:

```bash
cd ~/Desktop/My_Algo_Bot

# Create a demo data branch (optional)
git checkout -b demo-data

# Add historical data files (commit only a few recent days)
git add historical_data/trades_*.csv
git add historical_data/states_*.csv
git add historical_data/candles_*.csv

git commit -m "Add sample historical trading data for cloud demo"
git push origin demo-data

# Update your Streamlit Cloud app to use demo-data branch
```

**Option B: Automated Sync (Recommended)**

Set up a GitHub Action to sync data automatically:

1. Create `.github/workflows/sync-data.yml` (see template below)
2. The workflow runs after market close and commits new CSV files
3. Cloud dashboard auto-updates with latest data

#### Step 3: Access Your Cloud Dashboard

Your dashboard will be live at:
```
https://share.streamlit.io/yuvrajkalshetti1990-byte/my_algo_bot
```

Share this URL with anyone to show your trading performance!

---

## 📊 What Gets Exported

### Files Created in `historical_data/` Folder

```
historical_data/
├── trades_2026-04-30.csv          # All trades executed that day
├── states_2026-04-30.csv          # Final position states per strike
├── candles_23900_straddle_2026-04-30.csv  # ITM2 OHLC + indicators
├── candles_24000_straddle_2026-04-30.csv  # ITM1 OHLC + indicators
├── candles_24100_straddle_2026-04-30.csv  # ATM OHLC + indicators
├── candles_24200_straddle_2026-04-30.csv  # OTM1 OHLC + indicators
└── candles_24300_straddle_2026-04-30.csv  # OTM2 OHLC + indicators
```

### Trades CSV Structure
```csv
timestamp,strike,entry_exit,price,qty,pnl,trigger_type,regime
2026-04-30 09:45:00,24100,SHORT_ENTRY,524.50,390,0.0,NEW,BEARISH
2026-04-30 14:30:00,24100,SHORT_EXIT,516.25,390,3217.5,TARGET,BEARISH
```

### Candles CSV Structure
```csv
timestamp,open,high,low,close,volume,rsi,roc,ema,vwma,vwap,di_plus,di_minus,adx,chop
2026-04-30 09:15:00,528.75,532.50,526.00,530.25,1250,52.3,1.2,528.5,529.0,528.8,25.4,22.1,28.7,45.2
```

---

## 🔄 Daily Workflow

### Morning (Before Market Opens - 9:00 AM IST)

```bash
# Start your local dashboard
cd ~/Desktop/My_Algo_Bot
source .venv/bin/activate
streamlit run yuvi_dashboard.py --server.port 8502
```

### During Market Hours (9:15 AM - 3:30 PM)

- Monitor live dashboard at `http://localhost:8502`
- Bot trades automatically based on signals
- Position tracking and P&L updates in real-time

### After Market Close (3:30 PM onwards)

**Automatic Export** (No action needed):
- Bot auto-exports data at 15:30 IST
- CSV files saved to `historical_data/` folder

**Manual Export** (Optional):
- Click **"Export to CSV"** in sidebar
- Useful if you want to capture mid-day snapshot

### Share Results (Anytime)

**Option 1: Direct Upload to GitHub**
```bash
cd ~/Desktop/My_Algo_Bot
git add historical_data/
git commit -m "Add trading data for $(date +%Y-%m-%d)"
git push origin fyers-hl-fix
```

Cloud dashboard updates automatically in 1-2 minutes.

**Option 2: Automated GitHub Action** (see below)

---

## 🤖 Automated Data Sync (GitHub Actions)

Create `.github/workflows/sync-data.yml`:

```yaml
name: Sync Trading Data

on:
  schedule:
    # Run at 16:00 IST (10:30 UTC) after market close
    - cron: '30 10 * * 1-5'  # Monday-Friday
  workflow_dispatch:  # Allow manual trigger

jobs:
  sync-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: fyers-hl-fix
      
      - name: Check for new data files
        id: check_files
        run: |
          if [ -d "historical_data" ] && [ "$(ls -A historical_data)" ]; then
            echo "has_data=true" >> $GITHUB_OUTPUT
          else
            echo "has_data=false" >> $GITHUB_OUTPUT
          fi
      
      - name: Commit and push data
        if: steps.check_files.outputs.has_data == 'true'
        run: |
          git config user.name "Trading Bot"
          git config user.email "bot@example.com"
          git add historical_data/
          git commit -m "Auto-sync: Trading data $(date +%Y-%m-%d)" || exit 0
          git push
```

**Note**: This requires you to manually copy CSV files to the repo folder. For fully automated sync, you'd need to set up a cloud storage integration (S3, Dropbox, etc.).

---

## 🔐 Security Notes

### Local Mode
- ✅ `config.py` contains your real API credentials
- ✅ File is excluded by `.gitignore` — never committed to git
- ✅ `access_token.txt` is also excluded

### Cloud Mode
- ✅ **No API credentials needed** in Streamlit secrets
- ✅ Cloud dashboard only reads from CSV files
- ✅ No API calls made from cloud app
- ✅ Historical data is safe to share (contains only prices/indicators)

### CSV Files
Historical CSV files are **safe to commit** to GitHub because they contain:
- ✅ Public market data (prices, volumes)
- ✅ Calculated indicators (RSI, VWAP, etc.)
- ✅ Trade timestamps and P&L

They do NOT contain:
- ❌ API credentials
- ❌ Personal information
- ❌ Account numbers

---

## 🎨 Cloud Dashboard Features

When viewing historical data, the dashboard shows:

### Mode Banner
```
☁️ CLOUD MODE - Displaying Historical Data
```

### Date Selector (Sidebar)
- Dropdown with all available trading days
- Automatically loads data for selected date
- Shows trades, positions, and indicators

### Market Overview Table
- Strike-wise OHLC, LTP, indicators
- Same layout as live mode
- All indicator calculations preserved

### P&L Summary
- Daily trades with entry/exit prices
- Points and rupees P&L per trade
- Total day P&L and win/loss ratio

### Indicator Charts (If implemented)
- RSI, ROC, DMI, CHOP trends
- VWAP levels and crossovers
- EMA/VWMA overlays

---

## 📈 Advanced: Custom Data Exports

Want to export additional data? Modify `yuvi_export.py`:

```python
# Add custom metrics to export
def export_daily_data(trade_log, strike_states, date_str=None):
    # ... existing code ...
    
    # Add custom summary
    summary = {
        'total_trades': len(trade_log),
        'winning_trades': len([t for t in trade_log if t['pnl'] > 0]),
        'total_pnl': sum(t['pnl'] for t in trade_log),
        'max_drawdown': calculate_max_drawdown(trade_log),
        # ... more metrics
    }
    
    summary_file = DATA_DIR / f"summary_{date_str}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
```

---

## 🐛 Troubleshooting

### "No historical data found" in Cloud

**Cause**: No CSV files in `historical_data/` folder in your GitHub repo.

**Fix**:
1. Run bot locally for at least one trading session
2. Click "Export to CSV" in sidebar
3. Commit and push CSV files:
   ```bash
   git add historical_data/
   git commit -m "Add historical data"
   git push origin fyers-hl-fix
   ```

### "Module not found" error in Cloud

**Cause**: Missing dependency in `requirements.txt`.

**Fix**: Check `requirements.txt` includes:
```
fyers-apiv3>=3.0.0
pandas>=1.5.0,<2.0.0
streamlit>=1.28.0
ta>=0.10.0
python-dateutil>=2.8.0
```

### Cloud app shows stale data

**Cause**: Streamlit Cloud caching.

**Fix**:
1. Go to app settings → Click "Reboot app"
2. Or commit a dummy change to trigger redeploy

### Auto-export not working locally

**Cause**: System time may not be IST, or process not running at 15:30.

**Fix**:
- Use manual export button: "Export to CSV" in sidebar
- Or set up a cron job to export at specific time

---

## 🎯 Best Practices

### Local Trading
1. Start dashboard before market opens (9:00 AM)
2. Monitor signals and positions during trading hours
3. Let auto-export run at 15:30, or manually export
4. Keep your machine running until after 15:30 for auto-export

### Cloud Dashboard
1. Push historical data after each trading day
2. Keep only last 30-60 days of data (avoid repo bloat)
3. Use GitHub Releases for monthly archives
4. Document any unusual market conditions in commit messages

### Data Management
```bash
# Keep last 30 days only
cd historical_data
ls -t | tail -n +91 | xargs rm  # Keeps 30 days × 3 files

# Archive old data
tar -czf archive_2026-04.tar.gz trades_2026-04-*.csv
rm trades_2026-04-*.csv
```

---

## 📞 Support

If you run into issues:

1. **Local Mode Issues**: Check `access_token.txt` is valid, run `python3 1_login_test.py`
2. **Cloud Mode Issues**: Verify CSV files exist in repo's `historical_data/` folder
3. **Export Issues**: Check write permissions on `historical_data/` folder
4. **Deployment Issues**: Check Streamlit Cloud logs for errors

---

## 🚀 Summary

**Your Complete Setup**:
- ✅ Trade locally with live API during market hours
- ✅ Auto-export at market close (15:30 IST)
- ✅ Push CSV files to GitHub
- ✅ Cloud dashboard updates automatically
- ✅ Share public URL with anyone
- ✅ Historical data viewable by date

**No more**:
- ❌ Manual token refresh on cloud
- ❌ Exposing API credentials
- ❌ Cloud app sleeping during trades
- ❌ Complex cloud infrastructure

**Happy Trading! 🎉**
