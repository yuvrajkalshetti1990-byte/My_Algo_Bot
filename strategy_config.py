# strategy_config.py — Yuvi-N-Short/Long MasterV6 Settings

# ══════════════════════════════════════════════════════
# 1. INDEX & EXPIRY
# ══════════════════════════════════════════════════════
INDEX_NAME   = "NIFTY"          # "NIFTY" | "BANKNIFTY" | "SENSEX"
EXP_DD       = "05"
EXP_MM       = "05"
EXP_YY       = "26"

# Backtest range (inclusive)
BT_START     = (2025, 12, 30)   # (year, month, day)
BT_END       = (2099, 12, 31)

# ══════════════════════════════════════════════════════
# 2. STRIKES  [enabled, strike_price]
# ══════════════════════════════════════════════════════
STRIKES = [
    {"label": "ITM2", "strike": 23900, "enabled": True},
    {"label": "ITM1", "strike": 24000, "enabled": True},
    {"label": "ATM",  "strike": 24100, "enabled": True},
    {"label": "OTM1", "strike": 24200, "enabled": True},
    {"label": "OTM2", "strike": 24300, "enabled": True},
]
ATM_IDX = 2   # index of ATM in STRIKES list (0-based)

# ══════════════════════════════════════════════════════
# 3. SIGNAL LOGIC
# ══════════════════════════════════════════════════════
CALC_MODE        = "Auto"          # "Auto" | "Strict" | "Simple"
FILTER_CHOP      = True
CHOP_LIMIT       = 61.8

CROSSOVER_WINDOW = 0               # 0 = continuous
USE_OLD_LOGIC    = True            # Momentum logic
USE_NEW_LOGIC    = False           # Trend crossover logic
USE_VWAP_REV     = False           # VWAP reversal
REV_MIN_SIZE     = 5.0

VWAP_RESTRICT_EN = False
VWAP_SCOPE       = [False, False, False, False, False]   # per strike

# ══════════════════════════════════════════════════════
# 4. SHORT STRATEGY
# ══════════════════════════════════════════════════════
SHORT_ENABLED    = True
LOTS_SHORT       = 6
MAX_SHORT_TRADES = 0               # 0 = unlimited
SHORT_RESTRICT_EN= True
SHORT_SCOPE      = [False, False, True, False, False]   # S3=ATM only

USE_HARD_EXIT_SHORT  = True
HARD_EXIT_HOUR_SHORT = 15
HARD_EXIT_MIN_SHORT  = 20

FIXED_SL         = 0.0            # 0 = disabled
FIXED_TARGET     = 0.0            # 0 = disabled

DISABLE_SL_EN    = True
DISABLE_SL_PTS   = 10.0

USE_TSL          = False            # Trailing SL disabled for short
TSL_TRIGGER      = 20.0            # Act threshold (kept for reference)
TSL_DIST         = 10.0

# ══════════════════════════════════════════════════════
# 5. LONG STRATEGY
# ══════════════════════════════════════════════════════
LONG_ENABLED     = True
LOTS_LONG        = 6
MAX_LONG_TRADES  = 1               # 0 = unlimited
LONG_START_TIME  = "09:30"         # IST HH:MM

USE_STRICT_LONG      = True
USE_HARD_EXIT_LONG   = True
HARD_EXIT_HOUR_LONG  = 15
HARD_EXIT_MIN_LONG   = 10
LONG_RESTRICT_EN     = True
LONG_SCOPE           = [False, True, False, True, False]   # S2=24000, S4=24200

LONG_FIXED_SL    = 0.0             # Fixed SL disabled
LONG_TARGET      = 10.0            # Fixed TGT = 10 pts
USE_LONG_TSL     = True
TSL_LONG_TRIGGER = 15.0
TSL_LONG_DIST    = 10.0

# ══════════════════════════════════════════════════════
# 6. ACCOUNT
# ══════════════════════════════════════════════════════
INIT_CAPITAL  = 2_300_000.0
LOT_SIZE      = 65                 # NSE NIFTY lot size

# ══════════════════════════════════════════════════════
# 7. INDICATORS
# ══════════════════════════════════════════════════════
EMA_LEN        = 20
VWMA_LEN       = 15
RSI_LEN        = 14
DMI_LEN        = 14
CHOP_LEN       = 14
SUPERTREND_FAC = 3.0
SUPERTREND_PER = 10
ROC_LEN        = 9

# ══════════════════════════════════════════════════════
# 8. TIMEFRAME
# ══════════════════════════════════════════════════════
TIMEFRAME      = "3"               # minutes — Fyers resolution
SESSION_START  = "09:15"
SESSION_END    = "14:30"
