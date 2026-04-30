#!/usr/bin/env bash
set -euo pipefail

# Run from this script's directory so relative paths work.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
REQ_MODULES=(streamlit pandas pandas_ta requests fyers_apiv3)

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[Setup] Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Install missing packages only.
MISSING=0
for mod in "${REQ_MODULES[@]}"; do
  python - <<PY >/dev/null 2>&1 || MISSING=1
import ${mod}
PY
done

if [[ "$MISSING" -eq 1 ]]; then
  echo "[Setup] Installing required Python packages..."
  pip install --upgrade pip
  pip install streamlit pandas pandas-ta requests fyers-apiv3
fi

if [[ ! -f "access_token.txt" ]] || [[ ! -s "access_token.txt" ]]; then
  echo "[Auth] access_token.txt missing or empty. Starting Fyers login..."
  python 1_login_test.py
fi

# Validate token before launching Streamlit to avoid runtime code -16 failures.
TOKEN_STATE="$(python - <<'PY'
import os
import config
from fyers_apiv3 import fyersModel

token_path = "access_token.txt"
if not os.path.exists(token_path) or os.path.getsize(token_path) == 0:
    print("MISSING")
    raise SystemExit(0)

with open(token_path, "r", encoding="utf-8") as f:
    token = f.read().strip()

try:
    fyers = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False, log_path="")
    resp = fyers.quotes(data={"symbols": "NSE:NIFTY50-INDEX"})
    if isinstance(resp, dict) and str(resp.get("code")) == "-16":
        print("INVALID")
    else:
        print("VALID")
except Exception:
    print("UNKNOWN")
PY
)"

if [[ "$TOKEN_STATE" == "INVALID" ]] || [[ "$TOKEN_STATE" == "MISSING" ]]; then
  echo "[Auth] Token invalid/expired. Starting Fyers login refresh..."
  python 1_login_test.py
elif [[ "$TOKEN_STATE" == "UNKNOWN" ]]; then
  echo "[Auth] Could not verify token state (network/API issue). Continuing..."
fi

echo "[Run] Starting dashboard at http://localhost:8501"
streamlit run 3_dashboard.py
