# Streamlit Cloud Deployment Guide

## ⚠️ Important: Deployment Limitations

This bot has **real-time trading capabilities** that require:
1. **OAuth Login Flow**: Fyers API requires manual browser login to generate access tokens
2. **Token Expiration**: Access tokens expire and need refresh (manual intervention)
3. **Live Market Data**: Requires active Fyers API connection during market hours
4. **Stateful Data**: Session state resets on Streamlit Cloud sleep/restart

**Recommendation**: This bot is best suited for **local deployment** on your machine during market hours. Streamlit Cloud deployment is possible but has limitations for automated trading.

---

## Option 1: Local Deployment (Recommended for Trading)

### Setup
```bash
cd ~/Desktop/My_Algo_Bot
source .venv/bin/activate

# Configure credentials
cp config.example.py config.py
# Edit config.py with your Fyers credentials

# Login to get access token
python3 1_login_test.py

# Run dashboard
streamlit run yuvi_dashboard.py --server.port 8502
```

**Pros**: Full OAuth flow, persistent tokens, real-time data, no cold starts  
**Cons**: Requires your machine to be running during market hours

---

## Option 2: Streamlit Cloud Deployment (Read-Only Dashboard)

### Use Case
- Share **historical data visualization** with others
- Display **indicator calculations** without live trading
- **Demo/presentation** mode for your strategy

### Prerequisites
1. GitHub account connected to Streamlit Cloud ✅ (you have this)
2. Fyers API credentials (CLIENT_ID, SECRET_KEY)
3. Understanding that live trading features will be limited

### Deployment Steps

#### 1. Push Code to GitHub

```bash
cd ~/Desktop/My_Algo_Bot

# Add Streamlit config files
git add .streamlit/ requirements.txt config.example.py .gitignore
git commit -m "feat: add Streamlit Cloud deployment configuration"

# Push to your branch
git remote set-url origin https://yuvrajkalshetti1990-byte:YOUR_PAT@github.com/yuvrajkalshetti1990-byte/My_Algo_Bot.git
git push origin fyers-hl-fix

# Clean URL
git remote set-url origin https://github.com/yuvrajkalshetti1990-byte/My_Algo_Bot.git
```

#### 2. Deploy on Streamlit Cloud

1. Go to: https://share.streamlit.io/
2. Click **"New app"**
3. Select:
   - **Repository**: `yuvrajkalshetti1990-byte/My_Algo_Bot`
   - **Branch**: `fyers-hl-fix`
   - **Main file path**: `yuvi_dashboard.py`
4. Click **"Advanced settings"**
5. Set **Python version**: `3.9` or `3.10`
6. Click **"Deploy"**

#### 3. Configure Secrets

After deployment starts:

1. Click **⚙️ Settings** → **Secrets**
2. Paste this (with YOUR real credentials):

```toml
[fyers]
CLIENT_ID = "5DFGPH1D8Y-100"
SECRET_KEY = "CSATZUBFPM"
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
```

3. Click **"Save"**
4. App will automatically restart

#### 4. Handle OAuth Token

**Problem**: The cloud app can't run `1_login_test.py` to generate `access_token.txt`.

**Solutions**:

**A. Manual Token Upload** (Temporary - 1 day validity):
```bash
# On your local machine
python3 1_login_test.py  # Generates access_token.txt

# Add token to Streamlit secrets (Settings → Secrets)
# Add this line:
ACCESS_TOKEN = "paste_your_token_here"
```

Then update `yuvi_data.py` to read from `st.secrets` when available.

**B. Read-Only Mode** (No live trading):
- Display historical data from a CSV file
- Show indicator calculations on static data
- Demo mode without API calls

**C. Token Refresh Webhook** (Advanced):
- Set up a GitHub Action or external service to refresh tokens
- Store tokens in Streamlit secrets via API
- Requires additional infrastructure

---

## Code Changes for Cloud Deployment

### Option A: Add Token to Secrets

Update `yuvi_data.py`:

```python
# At the top, add:
import streamlit as st

def get_fyers_client():
    """Get Fyers client with token from secrets or file."""
    try:
        # Try Streamlit secrets first (cloud)
        if hasattr(st, 'secrets') and 'fyers' in st.secrets:
            if 'ACCESS_TOKEN' in st.secrets['fyers']:
                token = st.secrets['fyers']['ACCESS_TOKEN']
            else:
                # Fallback to file
                token = Path("access_token.txt").read_text().strip()
        else:
            # Local mode
            token = Path("access_token.txt").read_text().strip()
        
        return fyersModel.FyersModel(
            client_id=config.CLIENT_ID,
            token=token,
            is_async=False,
            log_path=str(Path(__file__).parent)
        )
    except Exception as e:
        st.error(f"Failed to initialize Fyers client: {e}")
        return None
```

### Option B: Demo Mode (No API Required)

Create a demo mode that loads data from CSV:

```python
# In yuvi_dashboard.py, add:
USE_DEMO_MODE = st.sidebar.checkbox("Demo Mode (No API)", value=True)

if USE_DEMO_MODE:
    # Load historical data from CSV instead of live API
    df = pd.read_csv("demo_data.csv")
else:
    # Use live API (requires valid token)
    df = fetch_live_data()
```

---

## Recommended Deployment Strategy

### For Live Trading
✅ **Run locally** on your machine during market hours  
✅ Use `bash run_dashboard.sh` in background  
✅ Set up `cron` job to auto-start at 9:00 AM IST  

### For Sharing/Demo
✅ **Deploy to Streamlit Cloud** with demo mode  
✅ Use historical CSV data for visualization  
✅ Share public URL for strategy presentations  

### Hybrid Approach
✅ **Trade locally** during market hours  
✅ **Export data** to CSV at end of day  
✅ **Deploy cloud dashboard** to visualize historical performance  

---

## Environment Variables

If you need to use environment variables instead of secrets:

```bash
# In Streamlit Cloud: Settings → Secrets
[env]
FYERS_CLIENT_ID = "5DFGPH1D8Y-100"
FYERS_SECRET_KEY = "CSATZUBFPM"
```

Then read in code:
```python
import os
CLIENT_ID = os.getenv("FYERS_CLIENT_ID", "fallback_value")
```

---

## Monitoring & Debugging

### View Logs
- Streamlit Cloud: Click **"Manage app"** → **"Logs"**
- Look for API errors, token expiration, connection issues

### Common Issues

**"Module not found"**:
- Check `requirements.txt` has all dependencies
- Ensure versions are compatible (e.g., `fyers-apiv3>=3.0.0`)

**"Secrets not found"**:
- Verify secrets are saved in Streamlit Cloud settings
- Check exact key names match (case-sensitive)

**"API Error"**:
- Token expired → Refresh manually via `1_login_test.py`
- Rate limiting → Add delays between API calls
- Market closed → Fyers API returns no data outside 9:15-15:30 IST

**App keeps sleeping**:
- Streamlit Cloud free tier sleeps after inactivity
- Upgrade to paid tier for 24/7 uptime
- Or use local deployment for trading

---

## Cost Considerations

**Streamlit Cloud Free Tier**:
- ✅ 1 private app
- ✅ Unlimited public apps
- ⚠️ Apps sleep after inactivity
- ⚠️ Limited resources (1 CPU, 1GB RAM)

**Streamlit Cloud Pro** ($20/month):
- ✅ 3 private apps
- ✅ No sleeping
- ✅ More resources
- ✅ Better for real-time apps

**Alternative**: Deploy to AWS/GCP/Heroku for full control

---

## Next Steps

Choose your deployment path:

### Path A: Quick Cloud Deploy (Demo Mode)
```bash
# Add demo mode to dashboard
# Deploy to Streamlit Cloud
# Share public URL
```

### Path B: Hybrid (Trade Local + Share Cloud)
```bash
# Run locally for trading
# Export daily data to CSV
# Deploy cloud dashboard for historical viz
```

### Path C: Full Cloud (Requires Token Management)
```bash
# Set up token refresh automation
# Deploy with secrets
# Monitor for token expiration
```

Let me know which path you want to pursue, and I'll help with the specific implementation!
