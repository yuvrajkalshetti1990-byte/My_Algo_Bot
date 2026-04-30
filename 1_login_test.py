from fyers_apiv3 import fyersModel
import webbrowser
import config  # This imports your keys from the other file
import os
from urllib.parse import urlparse, parse_qs


def extract_auth_code(user_input):
    """Accept either raw auth code or full redirect URL and return auth_code."""
    text = (user_input or "").strip()
    if not text:
        return ""

    # If user pasted full URL, read query params.
    if "http://" in text or "https://" in text:
        try:
            parsed = urlparse(text)
            query = parse_qs(parsed.query)
            code = query.get("auth_code", [""])[0].strip()
            if code:
                return code
        except Exception:
            pass

    # If user pasted text like: auth_code=XXXX&state=...
    if "auth_code=" in text:
        try:
            query = parse_qs(text.split("?", 1)[-1])
            code = query.get("auth_code", [""])[0].strip()
            if code:
                return code
        except Exception:
            pass

    # Assume user pasted raw code.
    return text

# 1. Generate the Login URL
session = fyersModel.SessionModel(
    client_id=config.CLIENT_ID,
    secret_key=config.SECRET_KEY,
    redirect_uri=config.REDIRECT_URI,
    response_type="code",
    grant_type="authorization_code"
)

# Generate the auth link
login_url = session.generate_authcode()

# 2. Open Browser for you to Login
print("\n[1] Opening Fyers Login Page...")
webbrowser.open(login_url)

# 3. Ask you for the Auth Code
print("\n[2] Please Login in the browser.")
print("    After success, look at the URL or the Green Box on the web page.")
print("    Paste either full redirect URL OR only 'auth_code'.")
auth_input = input("\n👉 Paste URL/Auth Code Here: ")
auth_code = extract_auth_code(auth_input)

if not auth_code:
    print("\n❌ Could not find 'auth_code' in your input.")
    raise SystemExit(1)

# 4. Generate Access Token
session.set_token(auth_code)
response = session.generate_token()

try:
    # Check if login was successful
    access_token = response["access_token"]
    print("\n✅ LOGIN SUCCESSFUL!")
    
    # Save the token to a text file (so we can use it later)
    with open("access_token.txt", "w") as f:
        f.write(access_token)
    print("✅ Token Saved to 'access_token.txt'")

    # 5. TEST: Get NIFTY Price
    fyers = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=access_token, is_async=False, log_path="")
    
    # Symbol for Nifty 50 Index
    data = {"symbols": "NSE:NIFTY50-INDEX"}
    market_data = fyers.quotes(data=data)
    
    # Dig into the complex data to find the Price
    nifty_price = market_data['d'][0]['v']['lp']
    print(f"\n🚀 LIVE NIFTY PRICE: {nifty_price}")

except Exception as e:
    print("\n❌ Login Failed. Error:", e)
    print("Response from Fyers:", response)
    if isinstance(response, dict) and response.get("code") == -437:
        print("\nLikely reasons for code -437 (invalid auth code):")
        print("1. Pasted an old/used auth code (it is one-time use).")
        print("2. Copied incomplete text instead of full auth_code.")
        print("3. App redirect URI mismatch between Fyers app and config.py.")
        print("\nTry again with a fresh login and paste the full redirected URL.")