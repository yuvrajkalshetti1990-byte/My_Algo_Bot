# yuvi_indicators.py — Indicator calculations for Yuvi MasterV6
# Mirrors the Pine Script indicator functions exactly.

import numpy as np
import pandas as pd
import pandas_ta as ta
import strategy_config as cfg


# ══════════════════════════════════════════════════════
# DMI / ADX  (matches Pine's calc_dmi)
# ══════════════════════════════════════════════════════
def calc_dmi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Returns df with columns: plus_di, minus_di, adx"""
    h, l, c = df["high"], df["low"], df["close"]

    up   = h.diff()
    down = -l.diff()

    plus_dm  = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    def rma(series, n):
        """Wilder's smoothing (RMA)"""
        result = pd.Series(index=series.index, dtype=float)
        result.iloc[n - 1] = series.iloc[:n].mean()
        alpha = 1.0 / n
        for i in range(n, len(series)):
            result.iloc[i] = alpha * series.iloc[i] + (1 - alpha) * result.iloc[i - 1]
        return result

    tr = pd.Series(
        np.maximum(
            np.maximum(h - l, np.abs(h - c.shift(1))),
            np.abs(l - c.shift(1))
        ),
        index=df.index
    )

    tr_rma    = rma(tr, length)
    plus_rma  = rma(pd.Series(plus_dm, index=df.index), length)
    minus_rma = rma(pd.Series(minus_dm, index=df.index), length)

    plus_di  = 100 * plus_rma  / tr_rma
    minus_di = 100 * minus_rma / tr_rma

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = rma(dx.fillna(0), length)

    df = df.copy()
    df["plus_di"]  = plus_di
    df["minus_di"] = minus_di
    df["adx"]      = adx
    return df


# ══════════════════════════════════════════════════════
# Choppiness Index  (matches Pine's ci())
# ══════════════════════════════════════════════════════
def calc_chop(df: pd.DataFrame, length: int = None) -> pd.Series:
    n = length or cfg.CHOP_LEN
    h, l, c = df["high"], df["low"], df["close"]

    tr = pd.Series(
        np.maximum(
            np.maximum(h - l, np.abs(h - c.shift(1))),
            np.abs(l - c.shift(1))
        ),
        index=df.index
    )

    atr_sum  = tr.rolling(n).sum()
    hh       = h.rolling(n).max()
    ll       = l.rolling(n).min()
    chop     = 100 * np.log10(atr_sum / (hh - ll)) / np.log10(n)
    return chop


# ══════════════════════════════════════════════════════
# All indicators for a single strike dataframe
# ══════════════════════════════════════════════════════
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds to df: ema, vwma, vwap, rsi, roc, plus_di, minus_di, adx, chop
    Input df must have: open, high, low, close, volume, ce_close, pe_close,
                        ce_daily_open, pe_daily_open, daily_open
    """
    df = df.copy()

    df["ema"]  = ta.ema(df["close"], length=cfg.EMA_LEN)
    df["vwma"] = ta.vwma(df["close"], df["volume"], length=cfg.VWMA_LEN)
    df["vwap"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
    df["rsi"]  = ta.rsi(df["close"], length=cfg.RSI_LEN)
    df["roc"]  = ta.roc(df["close"], length=cfg.ROC_LEN)
    df["chop"] = calc_chop(df, cfg.CHOP_LEN)
    df = calc_dmi(df, cfg.DMI_LEN)

    return df


# ══════════════════════════════════════════════════════
# Mode  (matches Pine's getMode)
# ══════════════════════════════════════════════════════
def get_mode(rsi, plus_di, minus_di, adx, ready: bool) -> str:
    if not ready:
        return "WAIT..."
    if adx < 15:
        return "SHORT"
    if rsi > 50 and plus_di > minus_di:
        return "BUY CE"
    if rsi < 40 and minus_di > plus_di:
        return "BUY PE"
    if adx > 20 and 40 <= rsi <= 60:
        return "LONG STR"
    return "SHORT"


# ══════════════════════════════════════════════════════
# Indicator Regime  (matches Pine's getIndReg)
# ══════════════════════════════════════════════════════
def get_ind_regime(rsi, plus_di, minus_di, adx) -> str:
    if adx < 15:
        return "NoTrend"
    if rsi > 55 and plus_di > minus_di:
        return "Bullish"
    if rsi < 45 and minus_di > plus_di:
        return "Bearish"
    return "Neutral"


# ══════════════════════════════════════════════════════
# Market Regime  (matches Pine's calcRegime)
# ══════════════════════════════════════════════════════
def calc_regime(close, daily_open, ce_close, ce_daily_open, pe_close, pe_daily_open) -> str:
    if pd.isna(close) or pd.isna(daily_open):
        return "—"
    diff    = close - daily_open
    str_dir = "UP" if diff > 0 else ("DOWN" if diff < 0 else "FLAT")
    ce_g    = ce_close - ce_daily_open if not pd.isna(ce_close) and not pd.isna(ce_daily_open) else 0.0
    pe_g    = pe_close - pe_daily_open if not pd.isna(pe_close) and not pd.isna(pe_daily_open) else 0.0
    dom     = "CE" if ce_g >= pe_g else "PE"

    if str_dir == "UP"   and dom == "CE": return "BULLISH"
    if str_dir == "UP"   and dom == "PE": return "SHORT COV"
    if str_dir == "DOWN" and dom == "PE": return "BEARISH"
    if str_dir == "DOWN" and dom == "CE": return "DECAY"
    return "SIDEWAYS"


# ══════════════════════════════════════════════════════
# Trade Type  (matches Pine's calcTType)
# ══════════════════════════════════════════════════════
def calc_ttype(close, daily_open, ce_close, ce_daily_open, pe_close, pe_daily_open,
               mode: str, chop: float) -> str:
    if pd.isna(close) or pd.isna(daily_open):
        return "NoTrade"

    ce_g = ce_close - ce_daily_open if not pd.isna(ce_close) and not pd.isna(ce_daily_open) else None
    pe_g = pe_close - pe_daily_open if not pd.isna(pe_close) and not pd.isna(pe_daily_open) else None

    if ce_g is None or pe_g is None:
        dom = "—"
    else:
        dom = "CE" if ce_g >= pe_g else "PE"

    is_mode_active = mode in ("BUY CE", "LONG STR", "BUY PE")

    if chop > 61.8 or mode == "WAIT...":
        return "NoTrade"
    if mode == "SHORT" and close < daily_open:
        return "Sell Str"
    if is_mode_active:
        if dom == "CE":   return "Buy CE"
        if dom == "PE":   return "Buy PE"
        return "Buy Str"
    return "NoTrade"


# ══════════════════════════════════════════════════════
# Signal processing row  (matches Pine's procSignal)
# ══════════════════════════════════════════════════════
def proc_signal(row, prev_row, df_slice, strike_idx: int, ttype: str, regime: str,
                in_session: bool, use_strict: bool) -> tuple[bool, bool, str, bool]:
    """
    Returns (buy_cond, sell_cond, trig_str, panic_long)
    df_slice: last N rows up to current bar (for crossover detection)
    """
    if not row["ready"] or not in_session or not cfg.STRIKES[strike_idx]["enabled"]:
        return False, False, "—", False

    c    = row["close"]
    ema  = row["ema"]
    vwap = row["vwap"]
    vwma = row["vwma"]
    rsi  = row["rsi"]
    dp   = row["plus_di"]
    dm   = row["minus_di"]
    roc  = row["roc"]
    chop = row["chop"]

    if pd.isna(ema) or pd.isna(rsi):
        return False, False, "—", False

    is_choppy = cfg.FILTER_CHOP and (chop > cfg.CHOP_LIMIT)
    if is_choppy:
        return False, False, "—", False

    # BUY condition
    buy_cond = False
    if use_strict:
        price_buy = (c > ema) and (c > vwap or c > vwma)
    else:
        price_buy = c > ema
    ind_buy = (rsi > 40) and (dp > dm) and (roc > 0)
    buy_cond = (price_buy and ind_buy) or ((c > vwap) and (vwap > vwma))

    # SELL condition
    sell_cond = False
    trig_str  = "—"

    if use_strict:
        price_sell = (c < ema) and (c < vwap or c < vwma)
    else:
        price_sell = c < ema

    old_part = price_sell and (rsi < 40) and (dm > dp) and (roc < 0)

    # Crossover detection (EMA/VWMA crossing under VWAP)
    x_under_ema  = False
    x_under_vwma = False
    if len(df_slice) >= 2:
        prev_ema  = df_slice["ema"].iloc[-2]
        prev_vwap = df_slice["vwap"].iloc[-2]
        prev_vwma = df_slice["vwma"].iloc[-2]
        curr_ema  = df_slice["ema"].iloc[-1]
        curr_vwap = df_slice["vwap"].iloc[-1]
        curr_vwma = df_slice["vwma"].iloc[-1]
        x_under_ema  = (prev_ema  >= prev_vwap) and (curr_ema  < curr_vwap)
        x_under_vwma = (prev_vwma >= prev_vwap) and (curr_vwma < curr_vwap)

    cross_event = x_under_ema or x_under_vwma
    if cfg.CROSSOVER_WINDOW == 0:
        new_part = (ema < vwap) or (vwma < vwap)
    else:
        # Find bars since last cross in df_slice
        crosses = df_slice.apply(
            lambda r: (r["ema"] < r["vwap"]) or (r["vwma"] < r["vwap"]), axis=1
        )
        last_cross_bars = len(df_slice) - crosses[::-1].idxmax() - 1 if crosses.any() else 9999
        new_part = last_cross_bars <= cfg.CROSSOVER_WINDOW

    # VWAP reversal
    rev_part  = False
    if cfg.USE_VWAP_REV:
        scope_allowed = (not cfg.VWAP_RESTRICT_EN) or cfg.VWAP_SCOPE[strike_idx]
        if scope_allowed and ttype == "Buy PE" and regime != "SHORT COV":
            if prev_row is not None:
                prev_green      = prev_row["close"] > prev_row["open"]
                prev_above_vwap = prev_row["close"] > prev_row["vwap"]
                curr_red        = c < row["open"]
                prev_body       = abs(prev_row["close"] - prev_row["open"])
                curr_body       = abs(c - row["open"])
                size_met        = False
                if prev_green and prev_above_vwap and curr_red:
                    if prev_body <= 3.0:
                        size_met = curr_body >= cfg.REV_MIN_SIZE
                    else:
                        size_met = (curr_body >= cfg.REV_MIN_SIZE) and (curr_body >= 0.8 * prev_body)
                if size_met:
                    rev_part = True
                elif len(df_slice) >= 3:
                    c2_ago = df_slice["close"].iloc[-3]
                    v2_ago = df_slice["vwap"].iloc[-3]
                    if c2_ago > v2_ago and curr_red and curr_body >= cfg.REV_MIN_SIZE:
                        rev_part = True

    satisfy_old = old_part if cfg.USE_OLD_LOGIC else True
    satisfy_new = new_part if cfg.USE_NEW_LOGIC else True
    base_met    = False
    if not cfg.USE_OLD_LOGIC and not cfg.USE_NEW_LOGIC:
        base_met = False
    else:
        base_met = satisfy_old and satisfy_new

    sell_cond = base_met or rev_part
    if rev_part:
        trig_str = "VWAP.REV"
    elif base_met:
        if cfg.USE_OLD_LOGIC and cfg.USE_NEW_LOGIC:
            trig_str = "BASE"
        elif cfg.USE_OLD_LOGIC:
            trig_str = "OLD"
        elif cfg.USE_NEW_LOGIC:
            trig_str = "NEW"

    panic_long = (c < vwap) and (vwap < vwma)

    return buy_cond, sell_cond, trig_str, panic_long
