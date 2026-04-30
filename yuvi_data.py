# yuvi_data.py — Fyers data fetcher for Yuvi MasterV6
# Fetches OHLCV for CE + PE of each strike and returns combined straddle candles.

import os
import time
import pandas as pd
from fyers_apiv3 import fyersModel
import config
import strategy_config as cfg


def get_fyers_client():
    if not os.path.exists("access_token.txt"):
        raise RuntimeError("access_token.txt not found. Run 1_login_test.py first.")
    with open("access_token.txt", "r") as f:
        token = f.read().strip()
    return fyersModel.FyersModel(
        client_id=config.CLIENT_ID,
        token=token,
        is_async=False,
        log_path=""
    )


_MONTH_CODE = {
    "01": "1", "02": "2", "03": "3", "04": "4",
    "05": "5", "06": "6", "07": "7", "08": "8",
    "09": "9", "10": "O", "11": "N", "12": "D",
}

def build_symbol(strike: int, opt_type: str) -> str:
    """Build Fyers symbol string for a weekly option.
    Fyers weekly format: NSE:NIFTY{YY}{MCODE}{DD}{STRIKE}{CE|PE}
    e.g. NSE:NIFTY2650524000CE  (May 5 2026, 24000 CE)
    opt_type: 'CE' or 'PE'
    """
    if cfg.INDEX_NAME == "SENSEX":
        root = "BSE:SENSEX"
    elif cfg.INDEX_NAME == "BANKNIFTY":
        root = "NSE:BANKNIFTY"
    else:
        root = "NSE:NIFTY"

    mcode = _MONTH_CODE.get(cfg.EXP_MM, cfg.EXP_MM)
    return f"{root}{cfg.EXP_YY}{mcode}{cfg.EXP_DD}{strike}{opt_type}"


def fetch_ohlcv(fyers, symbol: str, resolution: str = None) -> pd.DataFrame | None:
    """Fetch historical OHLCV candles for a single symbol."""
    res = resolution or cfg.TIMEFRAME
    payload = {
        "symbol": symbol,
        "resolution": str(res),
        "date_format": "0",
        "range_from": int(time.time()) - (5 * 24 * 60 * 60),
        "range_to": int(time.time()),
        "cont_flag": "1",
    }
    response = fyers.history(data=payload)
    if not response or "candles" not in response:
        return None

    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(response["candles"], columns=cols)
    df["timestamp"] = (
        pd.to_datetime(df["timestamp"], unit="s")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Kolkata")
    )
    df.set_index("timestamp", inplace=True)
    return df


def fetch_straddle(fyers, strike: int) -> dict | None:
    """
    Fetch CE and PE candles for a strike, return a dict with:
      ce_df, pe_df, combined_df
    combined uses: open=ce_open+pe_open, close=ce_close+pe_close,
                   high=max(open,close), low=min(open,close), volume=ce_vol+pe_vol
    Also returns daily open for CE and PE (first candle of day).
    """
    ce_sym = build_symbol(strike, "CE")
    pe_sym = build_symbol(strike, "PE")

    ce_df = fetch_ohlcv(fyers, ce_sym)
    pe_df = fetch_ohlcv(fyers, pe_sym)

    if ce_df is None or pe_df is None:
        return None

    # Align on common timestamps
    ce_df, pe_df = ce_df.align(pe_df, join="inner")

    combined = pd.DataFrame(index=ce_df.index)
    combined["ce_open"]  = ce_df["open"]
    combined["ce_close"] = ce_df["close"]
    combined["pe_open"]  = pe_df["open"]
    combined["pe_close"] = pe_df["close"]
    combined["open"]     = ce_df["open"]  + pe_df["open"]
    combined["close"]    = ce_df["close"] + pe_df["close"]
    # Correct straddle H/L:
    #   When Nifty is at its intrabar HIGH → CE peaks, PE troughs → CE_H + PE_L
    #   When Nifty is at its intrabar LOW  → CE troughs, PE peaks → CE_L + PE_H
    _h1 = ce_df["high"] + pe_df["low"]
    _h2 = ce_df["low"]  + pe_df["high"]
    combined["high"] = pd.concat([combined["open"], combined["close"], _h1, _h2], axis=1).max(axis=1)
    combined["low"]  = pd.concat([combined["open"], combined["close"], _h1, _h2], axis=1).min(axis=1)
    combined["volume"]   = ce_df["volume"] + pe_df["volume"]

    # Daily open: first candle of each trading day
    combined["date"] = combined.index.date
    daily_open = combined.groupby("date")["open"].first()
    ce_daily_open = combined.groupby("date")["ce_open"].first()
    pe_daily_open = combined.groupby("date")["pe_open"].first()
    combined["daily_open"]    = combined["date"].map(daily_open)
    combined["ce_daily_open"] = combined["date"].map(ce_daily_open)
    combined["pe_daily_open"] = combined["date"].map(pe_daily_open)
    combined.drop(columns=["date"], inplace=True)

    return {
        "ce_df":    ce_df,
        "pe_df":    pe_df,
        "combined": combined,
        "ce_sym":   ce_sym,
        "pe_sym":   pe_sym,
    }


def fetch_all_strikes(fyers) -> list[dict | None]:
    """Fetch straddle data for all configured strikes. Returns list aligned with cfg.STRIKES."""
    results = []
    for s in cfg.STRIKES:
        if s["enabled"]:
            data = fetch_straddle(fyers, s["strike"])
        else:
            data = None
        results.append(data)
    return results
