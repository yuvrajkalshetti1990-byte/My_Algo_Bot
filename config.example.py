# config.example.py - Template for Secret Keys
# 
# INSTRUCTIONS:
# 1. Copy this file to: config.py
# 2. Replace the placeholder values below with your real Fyers API credentials
# 3. NEVER commit config.py to git (it's in .gitignore)

CLIENT_ID = "YOUR_CLIENT_ID_HERE-100"  # Your Fyers App ID (It usually ends with -100)
SECRET_KEY = "YOUR_SECRET_KEY_HERE"    # Your Fyers Secret Key

# This must match EXACTLY what you set in Fyers Dashboard
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html" 

# Do not touch this
APP_ID_HASH = CLIENT_ID + ":" + SECRET_KEY
