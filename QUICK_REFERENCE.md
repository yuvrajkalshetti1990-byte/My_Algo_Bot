# Quick Reference — Hybrid Deployment

## 🚀 Deploy to Streamlit Cloud (5 minutes)

### 1. Open Streamlit Cloud
Visit: https://share.streamlit.io/

### 2. Create New App
- Click **"New app"**
- **Repository**: `yuvrajkalshetti1990-byte/My_Algo_Bot`
- **Branch**: `fyers-hl-fix`
- **Main file**: `yuvi_dashboard.py`
- **Python version**: `3.9`
- Click **"Deploy"**

### 3. Done! 
Your cloud dashboard will be live in 2-3 minutes at:
```
https://share.streamlit.io/yuvrajkalshetti1990-byte/my_algo_bot
```

**Note**: Initially shows "No historical data found" — this is expected! See "First Data Upload" below.

---

## 📊 First Data Upload

### Option 1: Quick Test (Sample Data)

Create a test file to verify cloud deployment works:

```bash
cd ~/Desktop/My_Algo_Bot/historical_data

# Create sample trade log
cat > trades_2026-04-30.csv << EOF
timestamp,strike,entry_exit,price,qty,pnl,trigger_type,regime
2026-04-30 09:45:00,24100,SHORT_ENTRY,524.50,390,0.0,NEW,BEARISH
2026-04-30 14:30:00,24100,SHORT_EXIT,516.25,390,3217.5,TARGET,BEARISH
EOF

# Push to GitHub
git add historical_data/
git commit -m "Add sample trading data"
git push origin fyers-hl-fix
```

Cloud dashboard updates automatically in 1-2 minutes!

### Option 2: Real Trading Data

After your first live trading session:

```bash
cd ~/Desktop/My_Algo_Bot

# Start dashboard (trade for at least 1 hour)
streamlit run yuvi_dashboard.py --server.port 8502

# After trading, click "Export to CSV" in sidebar
# Or wait for auto-export at 15:30 IST

# Upload to GitHub
git add historical_data/
git commit -m "Add trading data $(date +%Y-%m-%d)"
git push origin fyers-hl-fix
```

---

## 📅 Daily Workflow

### Morning (Before 9:00 AM)
```bash
cd ~/Desktop/My_Algo_Bot
source .venv/bin/activate
streamlit run yuvi_dashboard.py --server.port 8502
```
Dashboard opens at: http://localhost:8502

### During Trading (9:15 AM - 3:30 PM)
- Monitor live signals and positions
- Bot trades automatically
- All data tracked in session state

### After Market Close (3:30 PM+)
**Automatic**: Data exports at 15:30 IST  
**Manual**: Click "Export to CSV" button in sidebar

### Share Results (Anytime)
```bash
cd ~/Desktop/My_Algo_Bot
git add historical_data/
git commit -m "Trading data $(date +%Y-%m-%d)"
git push origin fyers-hl-fix
```

Cloud dashboard updates in 1-2 minutes.

---

## 🔧 Useful Commands

### View Local Dashboard
```bash
cd ~/Desktop/My_Algo_Bot
source .venv/bin/activate
streamlit run yuvi_dashboard.py --server.port 8502
```

### Export Data Manually
In dashboard sidebar → Click **"📤 Export to CSV"**

### Upload to Cloud
```bash
cd ~/Desktop/My_Algo_Bot
git add historical_data/
git commit -m "Update: $(date +%Y-%m-%d)"
git push origin fyers-hl-fix
```

### Check What's Exported
```bash
ls -lh ~/Desktop/My_Algo_Bot/historical_data/
```

### Clean Old Data (Keep Last 30 Days)
```bash
cd ~/Desktop/My_Algo_Bot/historical_data
ls -t | tail -n +91 | xargs rm
```

### View Cloud Dashboard
Open browser: https://share.streamlit.io/yuvrajkalshetti1990-byte/my_algo_bot

---

## 🎯 Quick Troubleshooting

### Cloud shows "No historical data found"
```bash
# Verify files exist
ls ~/Desktop/My_Algo_Bot/historical_data/*.csv

# If empty, export from local dashboard first
# Then commit and push:
git add historical_data/
git commit -m "Add historical data"
git push origin fyers-hl-fix
```

### Local dashboard shows API error
```bash
# Refresh token
cd ~/Desktop/My_Algo_Bot
python3 1_login_test.py

# Restart dashboard
streamlit run yuvi_dashboard.py --server.port 8502
```

### Cloud dashboard not updating
1. Go to app settings → Click **"Reboot app"**
2. Or force redeploy: `git commit --allow-empty -m "Trigger redeploy" && git push`

---

## 📱 Share Your Dashboard

Send this link to anyone:
```
https://share.streamlit.io/yuvrajkalshetti1990-byte/my_algo_bot
```

They can:
- ✅ View your trading performance
- ✅ See all indicators and signals
- ✅ Analyze historical trades
- ✅ Select different dates
- ❌ Cannot make trades (read-only)
- ❌ Cannot see your API credentials

---

## 🎉 You're All Set!

**Local Trading**: Real-time API, live positions, full features  
**Cloud Dashboard**: Historical viewer, public sharing, no credentials needed  
**Auto-Sync**: Export at 15:30 IST + manual button  
**Zero Config**: Cloud mode auto-detects (no access_token.txt)  

**Happy Trading! 🚀**
