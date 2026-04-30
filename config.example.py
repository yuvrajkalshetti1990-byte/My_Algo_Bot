# config.example.py - Template for Secret Keys
# 
# INSTRUCTIONS FOR LOCAL DEVELOPMENT:
# 1. Copy this file to: config.py
# 2. Replace the placeholder values below with your real Fyers API credentials
# 3. NEVER commit config.py to git (it's in .gitignore)
#
# INSTRUCTIONS FOR STREAMLIT CLOUD:
# This file supports both local config.py and Streamlit secrets.
# On Streamlit Cloud, credentials are read from st.secrets automatically.

try:
    import streamlit as st
    # Running on Streamlit Cloud - read from secrets
    if hasattr(st, 'secrets') and 'fyers' in st.secrets:
        CLIENT_ID = st.secrets["fyers"]["CLIENT_ID"]
        SECRET_KEY = st.secrets["fyers"]["SECRET_KEY"]
        REDIRECT_URI = st.secrets["fyers"]["REDIRECT_URI"]
    else:
        # Local development fallback
        CLIENT_ID = "YOUR_CLIENT_ID_HERE-100"  # Your Fyers App ID
        SECRET_KEY = "YOUR_SECRET_KEY_HERE"    # Your Fyers Secret Key
        REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
except ImportError:
    # Non-Streamlit environment
    CLIENT_ID = "YOUR_CLIENT_ID_HERE-100"
    SECRET_KEY = "YOUR_SECRET_KEY_HERE"
    REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"

# Do not touch this
APP_ID_HASH = CLIENT_ID + ":" + SECRET_KEY
