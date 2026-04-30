# yuvi_dashboard.py — Yuvi MasterV6 Dashboard (Enhanced UI)
# Run: streamlit run yuvi_dashboard.py

import time
import math
from datetime import datetime

import pandas as pd
import streamlit as st

import strategy_config as cfg
from yuvi_data import get_fyers_client, fetch_all_strikes
from yuvi_indicators import (
    add_indicators, get_mode, get_ind_regime,
    calc_regime, calc_ttype, proc_signal,
)
from yuvi_trade_manager import TradeManager

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Yuvi MasterV6",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp { background:#0d0d0d; color:#e8e8e8; font-family:'Segoe UI',sans-serif; }
section[data-testid="stSidebar"] { background:#111827; border-right:1px solid #1f2937; }
.block-container { padding-top:1rem !important; padding-bottom:0.5rem !important; }
.card { background:#1a1a2e; border:1px solid #2d2d44; border-radius:10px; padding:14px 18px; margin-bottom:8px; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700; letter-spacing:.4px; }
.badge-green  { background:#14532d; color:#4ade80; }
.badge-red    { background:#450a0a; color:#f87171; }
.badge-yellow { background:#422006; color:#facc15; }
.badge-blue   { background:#1e3a5f; color:#60a5fa; }
.badge-gray   { background:#1f2937; color:#9ca3af; }
.badge-orange { background:#431407; color:#fb923c; }
.badge-purple { background:#2e1065; color:#c084fc; }
.hdr-bar { display:flex; align-items:center; gap:12px; background:#0f172a; border:1px solid #1e293b; border-radius:10px; padding:10px 18px; margin-bottom:12px; }
.hdr-title { font-size:22px; font-weight:800; color:#f0f0f0; flex:1; }
.hdr-sub   { font-size:12px; color:#6b7280; }
.sec-divider { border:none; border-top:1px solid #1f2937; margin:10px 0; }
.prog-bar-bg { flex:1; height:6px; background:#1f2937; border-radius:3px; }
.prog-bar-fill { height:6px; border-radius:3px; }
.session-live { background:#14532d; color:#4ade80; padding:4px 14px; border-radius:999px; font-weight:700; font-size:13px; }
.session-closed { background:#1f2937; color:#6b7280; padding:4px 14px; border-radius:999px; font-weight:700; font-size:13px; }
.paper-pill { background:#1e3a5f; color:#60a5fa; padding:4px 14px; border-radius:999px; font-weight:700; font-size:13px; }
.live-pill  { background:#450a0a; color:#f87171; padding:4px 14px; border-radius:999px; font-weight:700; font-size:13px; animation:blink 1s step-start infinite; }
@keyframes blink { 50%{opacity:.4} }
[data-testid="stMetric"] { background:#111827; border:1px solid #1f2937; border-radius:8px; padding:10px 14px; }
[data-testid="stMetricLabel"] { color:#94a3b8 !important; font-size:12px !important; }
[data-testid="stMetricValue"] { color:#f1f5f9 !important; font-size:22px !important; font-weight:700; }
thead tr th { background:#1e293b !important; color:#94a3b8 !important; font-size:12px !important; text-transform:uppercase; }
tbody tr td { background:#111827 !important; color:#e2e8f0 !important; font-size:13px !important; border-bottom:1px solid #1f2937 !important; }
tbody tr:hover td { background:#1e293b !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for _k, _v in {
    "tm": TradeManager(), "trade_log": [], "is_live": False,
    "last_refresh": None, "last_data": None,
    "error_msg": None, "_last_auto_ts": 0.0,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

tm: TradeManager = st.session_state.tm

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _nan(v): return v is None or (isinstance(v, float) and math.isnan(v))
def _fmt(v, d=1): return f"{v:.{d}f}" if not _nan(v) else "—"
def _pnl_color(v): return "#22c55e" if v > 0 else ("#ef4444" if v < 0 else "#94a3b8")

def is_in_session(dt):
    t = dt.hour * 60 + dt.minute
    return 9*60+15 <= t <= 14*60+30

def is_hard_exit_short(dt):
    return dt.hour*60+dt.minute >= cfg.HARD_EXIT_HOUR_SHORT*60+cfg.HARD_EXIT_MIN_SHORT

def is_hard_exit_long(dt):
    return dt.hour*60+dt.minute >= cfg.HARD_EXIT_HOUR_LONG*60+cfg.HARD_EXIT_MIN_LONG

def can_long_start(dt):
    lh, lm = map(int, cfg.LONG_START_TIME.split(":"))
    return dt.hour*60+dt.minute >= lh*60+lm

def _use_strict(): return cfg.CALC_MODE in ("Strict", "Auto")

def _badge(cls, text): return f'<span class="badge badge-{cls}">{text}</span>'

def _regime_badge(r):
    M = {"BULLISH":("green","▲ BULL"), "BEARISH":("red","▼ BEAR"),
         "SHORT COV":("orange","↩ COV"), "DECAY":("gray","DECAY"), "SIDEWAYS":("gray","SIDE")}
    c, l = M.get(r, ("gray", r)); return _badge(c, l)

def _mode_badge(m):
    M = {"BUY CE":("green","▲ CE"), "BUY PE":("blue","▼ PE"),
         "LONG STR":("green","LONG STR"), "SHORT":("orange","SHORT"), "WAIT...":("gray","WAIT"),
         "Neutral":("gray","Neutral"), "NoTrend":("gray","NoTrend"),
         "Bearish":("red","▼ Bear"), "Bullish":("green","▲ Bull"), "Trending":("purple","Trend")}
    c, l = M.get(m, ("gray", m)); return _badge(c, l)

def _ttype_badge(t):
    M = {"Sell Str":("orange","Sell"), "Buy CE":("green","Buy CE"),
         "Buy PE":("red","Buy PE"), "Buy Str":("blue","Buy Str"), "NoTrade":("gray","—")}
    c, l = M.get(t, ("gray", t)); return _badge(c, l)

def _prog_html(val, lo, hi, color, w=100):
    p = max(0.0, min(1.0, (val - lo) / max(hi - lo, 1)))
    f = int(p * w)
    return (f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
            f'<div class="prog-bar-bg" style="width:{w}%">'
            f'<div class="prog-bar-fill" style="width:{f}%;background:{color}"></div>'
            f'</div></div>')

# ─────────────────────────────────────────────────────────────────────────────
# RUNTIME CFG — reads sidebar widget values from session_state → updates cfg
# ─────────────────────────────────────────────────────────────────────────────
def _apply_runtime_cfg():
    ss = st.session_state
    # 1. Setup
    cfg.INDEX_NAME = ss.get("w_index",   cfg.INDEX_NAME)
    cfg.EXP_DD     = ss.get("w_exp_dd",  cfg.EXP_DD)
    cfg.EXP_MM     = ss.get("w_exp_mm",  cfg.EXP_MM)
    cfg.EXP_YY     = ss.get("w_exp_yy",  cfg.EXP_YY)
    # 2. Strikes
    for _i in range(len(cfg.STRIKES)):
        cfg.STRIKES[_i]["enabled"] = bool(ss.get(f"w_str_en_{_i}",  cfg.STRIKES[_i]["enabled"]))
        cfg.STRIKES[_i]["strike"]  = int( ss.get(f"w_str_val_{_i}", cfg.STRIKES[_i]["strike"]))
    cfg.ATM_IDX = int(ss.get("w_atm_idx", cfg.ATM_IDX))
    # 3. Logic
    cfg.CALC_MODE        = ss.get("w_calc_mode",   cfg.CALC_MODE)
    cfg.FILTER_CHOP      = bool(ss.get("w_filter_chop", cfg.FILTER_CHOP))
    cfg.CHOP_LIMIT       = float(ss.get("w_chop_limit",  cfg.CHOP_LIMIT))
    cfg.CROSSOVER_WINDOW = int(  ss.get("w_bkdown_win",  cfg.CROSSOVER_WINDOW))
    cfg.USE_OLD_LOGIC    = bool(ss.get("w_use_mom",      cfg.USE_OLD_LOGIC))
    cfg.USE_NEW_LOGIC    = bool(ss.get("w_use_trend",    cfg.USE_NEW_LOGIC))
    cfg.USE_VWAP_REV     = bool(ss.get("w_use_vwap_rev", cfg.USE_VWAP_REV))
    cfg.REV_MIN_SIZE     = float(ss.get("w_rev_min",     cfg.REV_MIN_SIZE))
    cfg.VWAP_RESTRICT_EN = bool(ss.get("w_vwap_restrict", cfg.VWAP_RESTRICT_EN))
    for _i in range(5):
        cfg.VWAP_SCOPE[_i] = bool(ss.get(f"w_vwap_scope_{_i}", cfg.VWAP_SCOPE[_i]))
    # 4. Short
    cfg.SHORT_ENABLED        = bool( ss.get("w_short_en",        cfg.SHORT_ENABLED))
    cfg.LOTS_SHORT           = int(  ss.get("w_lots_short",       cfg.LOTS_SHORT))
    cfg.MAX_SHORT_TRADES     = int(  ss.get("w_max_short",        cfg.MAX_SHORT_TRADES))
    cfg.SHORT_RESTRICT_EN    = bool( ss.get("w_short_restrict",   cfg.SHORT_RESTRICT_EN))
    for _i in range(5):
        cfg.SHORT_SCOPE[_i]  = bool( ss.get(f"w_short_scope_{_i}", cfg.SHORT_SCOPE[_i]))
    cfg.USE_HARD_EXIT_SHORT  = bool( ss.get("w_short_time_exit",  cfg.USE_HARD_EXIT_SHORT))
    cfg.HARD_EXIT_HOUR_SHORT = int(  ss.get("w_short_exit_h",     cfg.HARD_EXIT_HOUR_SHORT))
    cfg.HARD_EXIT_MIN_SHORT  = int(  ss.get("w_short_exit_m",     cfg.HARD_EXIT_MIN_SHORT))
    cfg.FIXED_SL             = float(ss.get("w_fixed_sl",         cfg.FIXED_SL))
    cfg.FIXED_TARGET         = float(ss.get("w_fixed_tgt",        cfg.FIXED_TARGET))
    cfg.DISABLE_SL_EN        = bool( ss.get("w_smart_sl",         cfg.DISABLE_SL_EN))
    cfg.DISABLE_SL_PTS       = float(ss.get("w_smart_sl_pts",     cfg.DISABLE_SL_PTS))
    cfg.USE_TSL              = bool( ss.get("w_tsl_en",           cfg.USE_TSL))
    cfg.TSL_TRIGGER          = float(ss.get("w_tsl_act",          cfg.TSL_TRIGGER))
    cfg.TSL_DIST             = float(ss.get("w_tsl_dist",         cfg.TSL_DIST))
    # 5. Long
    cfg.LONG_ENABLED         = bool( ss.get("w_long_en",          cfg.LONG_ENABLED))
    cfg.LOTS_LONG            = int(  ss.get("w_lots_long",         cfg.LOTS_LONG))
    cfg.MAX_LONG_TRADES      = int(  ss.get("w_max_long",          cfg.MAX_LONG_TRADES))
    cfg.LONG_START_TIME      = ss.get("w_long_start",             cfg.LONG_START_TIME)
    cfg.USE_STRICT_LONG      = bool( ss.get("w_strict_long",       cfg.USE_STRICT_LONG))
    cfg.USE_HARD_EXIT_LONG   = bool( ss.get("w_long_time_exit",    cfg.USE_HARD_EXIT_LONG))
    cfg.HARD_EXIT_HOUR_LONG  = int(  ss.get("w_long_exit_h",       cfg.HARD_EXIT_HOUR_LONG))
    cfg.HARD_EXIT_MIN_LONG   = int(  ss.get("w_long_exit_m",       cfg.HARD_EXIT_MIN_LONG))
    cfg.LONG_RESTRICT_EN     = bool( ss.get("w_long_restrict",     cfg.LONG_RESTRICT_EN))
    for _i in range(5):
        cfg.LONG_SCOPE[_i]   = bool( ss.get(f"w_long_scope_{_i}", cfg.LONG_SCOPE[_i]))
    cfg.LONG_FIXED_SL        = float(ss.get("w_long_sl",           cfg.LONG_FIXED_SL))
    cfg.LONG_TARGET          = float(ss.get("w_long_tgt",           cfg.LONG_TARGET))
    cfg.USE_LONG_TSL         = bool( ss.get("w_long_tsl_en",        cfg.USE_LONG_TSL))
    cfg.TSL_LONG_TRIGGER     = float(ss.get("w_long_tsl_act",       cfg.TSL_LONG_TRIGGER))
    cfg.TSL_LONG_DIST        = float(ss.get("w_long_tsl_dist",      cfg.TSL_LONG_DIST))
    # 6. Account & Indicators
    cfg.INIT_CAPITAL         = float(ss.get("w_capital",  cfg.INIT_CAPITAL))
    cfg.LOT_SIZE             = int(  ss.get("w_lot_size", cfg.LOT_SIZE))
    cfg.EMA_LEN              = int(  ss.get("w_ema_len",  cfg.EMA_LEN))
    cfg.VWMA_LEN             = int(  ss.get("w_vwma_len", cfg.VWMA_LEN))
    cfg.TIMEFRAME            = str(  ss.get("w_timeframe", cfg.TIMEFRAME))


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Full interactive settings (mirrors Pine Script input panels)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    refresh_sec = st.slider("Auto-refresh (s)", 5, 120, 30, step=5)
    st.session_state.is_live = st.toggle(
        "🔴 LIVE MODE",
        value=st.session_state.is_live,
        help="OFF = Paper / Dry-run. No real orders placed."
    )
    st.markdown("<hr class='sec-divider'>", unsafe_allow_html=True)

    # ── 1. Index & Expiry ─────────────────────────────────────────────────
    with st.expander("1.  INDEX & EXPIRY", expanded=True):
        st.selectbox("Index Selection",
                     ["NIFTY", "BANKNIFTY", "SENSEX"],
                     index=["NIFTY", "BANKNIFTY", "SENSEX"].index(cfg.INDEX_NAME),
                     key="w_index")
        _ec1, _ec2, _ec3 = st.columns(3)
        _ec1.text_input("Ex DD", value=cfg.EXP_DD, max_chars=2, key="w_exp_dd")
        _ec2.text_input("MM",    value=cfg.EXP_MM, max_chars=2, key="w_exp_mm")
        _ec3.text_input("YY",    value=cfg.EXP_YY, max_chars=2, key="w_exp_yy")
        _tf_opts = ["3", "5"]
        st.radio("Candle Timeframe (min)", _tf_opts,
                 index=_tf_opts.index(cfg.TIMEFRAME) if cfg.TIMEFRAME in _tf_opts else 0,
                 key="w_timeframe", horizontal=True,
                 help="3 min matches Sensibull/TradingView chart; 5 min for fewer signals")

    # ── 2. Strike Selection ───────────────────────────────────────────────
    with st.expander("2.  STRIKE SELECTION", expanded=True):
        for _si, _sc in enumerate(cfg.STRIKES):
            _lbl = f"S{_si+1} {_sc['label']}" + ("  ★" if _si == cfg.ATM_IDX else "")
            _c1, _c2 = st.columns([1, 3])
            _c1.checkbox("En", value=_sc["enabled"],
                         key=f"w_str_en_{_si}", label_visibility="collapsed")
            _c2.number_input(_lbl, value=int(_sc["strike"]), step=50,
                             min_value=1000, max_value=99999,
                             key=f"w_str_val_{_si}")
        st.number_input("ATM index (0-based)", value=int(cfg.ATM_IDX),
                        min_value=0, max_value=4, step=1, key="w_atm_idx")

    # ── 3. Logic Settings ─────────────────────────────────────────────────
    with st.expander("3.  LOGIC SETTINGS"):
        _lc1, _lc2 = st.columns([1.4, 1])
        _lc1.selectbox("Calc Mode", ["Auto", "Strict", "Simple"],
                       index=["Auto", "Strict", "Simple"].index(cfg.CALC_MODE),
                       key="w_calc_mode")
        _lc2.number_input("Chop >", value=float(cfg.CHOP_LIMIT),
                          min_value=0.0, max_value=100.0, step=0.1,
                          key="w_chop_limit")
        _lf1, _lf2 = st.columns(2)
        _lf1.checkbox("Filter Chop", value=cfg.FILTER_CHOP, key="w_filter_chop")
        _lf2.number_input("Bkdn Win", value=int(cfg.CROSSOVER_WINDOW),
                          min_value=0, step=1, key="w_bkdown_win",
                          help="Breakdown Window — 0 = continuous crossover")
        _m1, _m2, _m3 = st.columns(3)
        _m1.checkbox("Momentum", value=cfg.USE_OLD_LOGIC,  key="w_use_mom")
        _m2.checkbox("Trend",    value=cfg.USE_NEW_LOGIC,  key="w_use_trend")
        _m3.checkbox("VWAP Rev", value=cfg.USE_VWAP_REV,  key="w_use_vwap_rev")
        st.number_input("Min Rev Size", value=float(cfg.REV_MIN_SIZE),
                        min_value=0.0, step=0.5, key="w_rev_min")
        _vr = st.checkbox("Restrict VWAP Scope?", value=cfg.VWAP_RESTRICT_EN,
                          key="w_vwap_restrict")
        _vs = st.columns(5)
        for _i in range(5):
            _vs[_i].checkbox(f"S{_i+1}", value=cfg.VWAP_SCOPE[_i],
                             key=f"w_vwap_scope_{_i}", disabled=not _vr)

    # ── 4. Short Strategy ─────────────────────────────────────────────────
    with st.expander("4.  SHORT STRATEGY"):
        _s1, _s2 = st.columns([1.4, 1])
        _s1.checkbox("Enable Short", value=cfg.SHORT_ENABLED, key="w_short_en")
        _s2.number_input("Lots", value=int(cfg.LOTS_SHORT),
                         min_value=1, step=1, key="w_lots_short",
                         label_visibility="collapsed")
        st.number_input("Max Short Trades (0 = unlimited)",
                        value=int(cfg.MAX_SHORT_TRADES), min_value=0,
                        step=1, key="w_max_short")
        _sr = st.checkbox("Restrict Scope?", value=cfg.SHORT_RESTRICT_EN,
                          key="w_short_restrict")
        _ss_cols = st.columns(5)
        for _i in range(5):
            _ss_cols[_i].checkbox(f"S{_i+1}", value=cfg.SHORT_SCOPE[_i],
                                  key=f"w_short_scope_{_i}", disabled=not _sr)
        _se1, _se2, _se3 = st.columns([2, 1, 1])
        _se1.checkbox("Time Exit?", value=cfg.USE_HARD_EXIT_SHORT,
                      key="w_short_time_exit")
        _se2.number_input("H", value=int(cfg.HARD_EXIT_HOUR_SHORT),
                          min_value=9, max_value=15, step=1, key="w_short_exit_h")
        _se3.number_input("M", value=int(cfg.HARD_EXIT_MIN_SHORT),
                          min_value=0, max_value=59, step=1, key="w_short_exit_m")
        _sf1, _sf2 = st.columns(2)
        _sf1.number_input("Fixed SL",  value=float(cfg.FIXED_SL),
                          min_value=0.0, step=1.0, key="w_fixed_sl")
        _sf2.number_input("Fixed TGT", value=float(cfg.FIXED_TARGET),
                          min_value=0.0, step=1.0, key="w_fixed_tgt")
        _sm1, _sm2 = st.columns([1.6, 1])
        _sm1.checkbox("Smart SL Disable >", value=cfg.DISABLE_SL_EN, key="w_smart_sl")
        _sm2.number_input("Pts", value=float(cfg.DISABLE_SL_PTS),
                          min_value=0.0, step=1.0, key="w_smart_sl_pts",
                          label_visibility="collapsed")
        _tsl1, _tsl2, _tsl3 = st.columns([1.6, 1, 1])
        _tsl1.checkbox("Trailing SL", value=cfg.USE_TSL, key="w_tsl_en")
        _tsl2.number_input("Act",  value=float(cfg.TSL_TRIGGER),
                           min_value=0.0, step=1.0, key="w_tsl_act")
        _tsl3.number_input("Dist", value=float(cfg.TSL_DIST),
                           min_value=0.0, step=1.0, key="w_tsl_dist")

    # ── 5. Long Strategy ──────────────────────────────────────────────────
    with st.expander("5.  LONG STRATEGY"):
        _l1, _l2 = st.columns([1.4, 1])
        _l1.checkbox("Enable Long", value=cfg.LONG_ENABLED, key="w_long_en")
        _l2.number_input("Lots", value=int(cfg.LOTS_LONG),
                         min_value=1, step=1, key="w_lots_long",
                         label_visibility="collapsed")
        st.number_input("Max Long Trades (0 = unlimited)",
                        value=int(cfg.MAX_LONG_TRADES), min_value=0,
                        step=1, key="w_max_long")
        st.text_input("Long Start Time (HH:MM)", value=cfg.LONG_START_TIME,
                      key="w_long_start")
        st.checkbox("Strict Entry", value=cfg.USE_STRICT_LONG, key="w_strict_long")
        _le1, _le2, _le3 = st.columns([2, 1, 1])
        _le1.checkbox("Time Exit?", value=cfg.USE_HARD_EXIT_LONG,
                      key="w_long_time_exit")
        _le2.number_input("H", value=int(cfg.HARD_EXIT_HOUR_LONG),
                          min_value=9, max_value=15, step=1, key="w_long_exit_h")
        _le3.number_input("M", value=int(cfg.HARD_EXIT_MIN_LONG),
                          min_value=0, max_value=59, step=1, key="w_long_exit_m")
        _lr = st.checkbox("Restrict Scope?", value=cfg.LONG_RESTRICT_EN,
                          key="w_long_restrict")
        _ls_cols = st.columns(5)
        for _i in range(5):
            _ls_cols[_i].checkbox(f"S{_i+1}", value=cfg.LONG_SCOPE[_i],
                                  key=f"w_long_scope_{_i}", disabled=not _lr)
        _lf1, _lf2 = st.columns(2)
        _lf1.number_input("Fixed SL",  value=float(cfg.LONG_FIXED_SL),
                          min_value=0.0, step=1.0, key="w_long_sl")
        _lf2.number_input("Fixed TGT", value=float(cfg.LONG_TARGET),
                          min_value=0.0, step=1.0, key="w_long_tgt")
        _ltsl1, _ltsl2, _ltsl3 = st.columns([1.6, 1, 1])
        _ltsl1.checkbox("Trailing SL", value=cfg.USE_LONG_TSL, key="w_long_tsl_en")
        _ltsl2.number_input("Act",  value=float(cfg.TSL_LONG_TRIGGER),
                            min_value=0.0, step=1.0, key="w_long_tsl_act")
        _ltsl3.number_input("Dist", value=float(cfg.TSL_LONG_DIST),
                            min_value=0.0, step=1.0, key="w_long_tsl_dist")

    # ── 6. Visuals & Account ──────────────────────────────────────────────
    with st.expander("6.  VISUALS & ACCOUNT"):
        _v1, _v2 = st.columns(2)
        _v1.number_input("EMA Length",  value=int(cfg.EMA_LEN),
                         min_value=1, step=1, key="w_ema_len")
        _v2.number_input("VWMA Length", value=int(cfg.VWMA_LEN),
                         min_value=1, step=1, key="w_vwma_len")
        st.number_input("Initial Capital (₹)", value=float(cfg.INIT_CAPITAL),
                        min_value=100_000.0, step=100_000.0,
                        key="w_capital", format="%.0f")
        st.number_input("Lot Size", value=float(cfg.LOT_SIZE),
                        min_value=1.0, step=1.0,
                        key="w_lot_size", format="%.0f")

# Apply sidebar values to cfg before any computation
_apply_runtime_cfg()

# ─────────────────────────────────────────────────────────────────────────────
# HEADER BAR
# ─────────────────────────────────────────────────────────────────────────────
now_dt = datetime.now()
_sess_html = ('<span class="session-live">● MARKET OPEN</span>'
              if is_in_session(now_dt)
              else '<span class="session-closed">● MARKET CLOSED</span>')
_mode_html = ('<span class="live-pill">LIVE</span>'
              if st.session_state.is_live
              else '<span class="paper-pill">PAPER / DRY RUN</span>')

st.markdown(f"""
<div class="hdr-bar">
  <div class="hdr-title">⚡ Yuvi MasterV6 — {cfg.INDEX_NAME}</div>
  {_sess_html}&nbsp;&nbsp;{_mode_html}
  <div style="margin-left:auto;text-align:right">
    <div style="font-size:16px;color:#cbd5e1;font-weight:600">{now_dt:%H:%M:%S}</div>
    <div class="hdr-sub">Last: {st.session_state.last_refresh or '—'} | Exp {cfg.EXP_DD}/{cfg.EXP_MM}/{cfg.EXP_YY}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BUTTONS
# ─────────────────────────────────────────────────────────────────────────────
_b1, _b2, _b3, _ = st.columns([1, 1, 1, 5])
do_refresh = _b1.button("Refresh", use_container_width=True)
do_reset   = _b2.button("Reset Day", use_container_width=True)
do_dry_run = _b3.button("Dry Run", use_container_width=True, type="primary")

if do_reset:
    tm.on_new_day()
    st.session_state.trade_log = []
    st.session_state.last_data = None
    st.session_state.pop("_replayed_date", None)
    st.toast("Day state reset.")

# ─────────────────────────────────────────────────────────────────────────────
# FETCH & PROCESS  (with full intraday replay for trade history)
# ─────────────────────────────────────────────────────────────────────────────
def _build_bar_at(dfs, i, sc, row, prev_row, df_slice, bar_dt):
    """Build the bar_input dict for one strike at one timestamp."""
    row_d  = dict(row)
    prev_d = dict(prev_row)
    rsi  = row.get("rsi",      float("nan"))
    dp   = row.get("plus_di",  float("nan"))
    dm   = row.get("minus_di", float("nan"))
    adx  = row.get("adx",      float("nan"))
    chop = row.get("chop",     float("nan"))
    ready = not _nan(row["close"]) and not _nan(row.get("daily_open"))
    mode    = get_mode(rsi, dp, dm, adx, ready)
    regime  = calc_regime(
        row["close"],    row.get("daily_open"),
        row["ce_close"], row.get("ce_daily_open"),
        row["pe_close"], row.get("pe_daily_open"),
    )
    ttype = calc_ttype(
        row["close"],    row.get("daily_open"),
        row["ce_close"], row.get("ce_daily_open"),
        row["pe_close"], row.get("pe_daily_open"),
        mode, chop if not _nan(chop) else 0.0
    )
    buy_c, sell_c, trig_str, panic = proc_signal(
        row_d | {"ready": ready}, prev_d, df_slice,
        i, ttype, regime,
        is_in_session(bar_dt), _use_strict()
    )
    return {
        "open": row["open"], "high": row.get("high", row["close"]),
        "low": row.get("low", row["close"]), "close": row["close"],
        "ema": row.get("ema"), "vwma": row.get("vwma"), "vwap": row.get("vwap"),
        "buy_cond": buy_c, "sell_cond": sell_c,
        "trig_str": trig_str, "panic_long": panic,
        "ttype": ttype, "regime": regime, "ready": ready,
        "_mode": mode, "_rsi": rsi, "_roc": row.get("roc", float("nan")),
        "_dp": dp, "_dm": dm, "_adx": adx, "_chop": chop,
        "_ind_reg": get_ind_regime(rsi, dp, dm, adx),
    }


def fetch_and_process(dry_run=False):
    try:
        fyers = get_fyers_client()
    except RuntimeError as e:
        st.session_state.error_msg = str(e)
        return None, None
    st.session_state.error_msg = None

    with st.spinner("Fetching option data from Fyers..."):
        all_data = fetch_all_strikes(fyers)

    today = datetime.now().date()

    # Pre-compute indicators for all strikes
    dfs = []
    for sc, data in zip(cfg.STRIKES, all_data):
        if data is None or not sc["enabled"]:
            dfs.append(None); continue
        df = add_indicators(data["combined"].copy())
        if len(df) < 2:
            dfs.append(None); continue
        dfs.append(df)

    # ── Full intraday replay if we haven't done it for today yet ─────────────
    # Also re-replay if timeframe changed (different candle resolution)
    _replay_key = f"{today}_{cfg.TIMEFRAME}"
    if st.session_state.get("_replayed_date") != _replay_key and not dry_run:
        tm.on_new_day()
        st.session_state.trade_log = []

        # Collect all today's timestamps across strikes
        today_ts = set()
        for df in dfs:
            if df is not None:
                today_rows = df[df.index.date == today]
                today_ts.update(today_rows.index.tolist())
        today_ts = sorted(today_ts)

        for ts in today_ts:
            bar_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            bar_inputs = []
            for i, (sc, df) in enumerate(zip(cfg.STRIKES, dfs)):
                if df is None or not sc["enabled"]:
                    bar_inputs.append(None); continue
                if ts not in df.index:
                    bar_inputs.append(None); continue
                pos = df.index.get_loc(ts)
                if pos < 1:
                    bar_inputs.append(None); continue
                row      = df.iloc[pos]
                prev_row = df.iloc[pos - 1]
                win      = max(cfg.CROSSOVER_WINDOW + 2, 5)
                df_slice = df.iloc[max(0, pos - win + 1): pos + 1]
                bar_inputs.append(_build_bar_at(dfs, i, sc, row, prev_row, df_slice, bar_dt))

            events = tm.process_bar(
                bar_inputs, bar_dt,
                is_hard_exit_short(bar_dt), is_hard_exit_long(bar_dt),
                is_in_session(bar_dt), can_long_start(bar_dt)
            )
            for ev in events:
                ev["ts"] = bar_dt.strftime("%H:%M")
                st.session_state.trade_log.append(ev)

        st.session_state._replayed_date = _replay_key

    # ── Build strike_rows from the LAST bar ──────────────────────────────────
    now = datetime.now()
    strike_rows = []
    last_bar_inputs = []

    for i, (sc, df) in enumerate(zip(cfg.STRIKES, dfs)):
        if df is None or not sc["enabled"]:
            strike_rows.append(None); last_bar_inputs.append(None); continue

        row, prev = df.iloc[-1], df.iloc[-2]
        win      = max(cfg.CROSSOVER_WINDOW + 2, 5)
        df_slice = df.tail(win)
        bar      = _build_bar_at(dfs, i, sc, row, prev, df_slice, now)

        ce_g = row["ce_close"] - row["ce_daily_open"] if not _nan(row.get("ce_daily_open")) else float("nan")
        pe_g = row["pe_close"] - row["pe_daily_open"] if not _nan(row.get("pe_daily_open")) else float("nan")
        dom  = "CE" if (not _nan(ce_g) and not _nan(pe_g) and ce_g >= pe_g) else "PE"

        strike_rows.append({
            "label": sc["label"], "strike": sc["strike"],
            "daily_open": row.get("daily_open"), "close": row["close"],
            "ce_close": row["ce_close"], "pe_close": row["pe_close"],
            "change": row["close"] - row.get("daily_open", row["close"]),
            "dom": dom, "regime": bar["regime"], "ind_reg": bar["_ind_reg"],
            "mode": bar["_mode"], "ttype": bar["ttype"],
            "rsi": bar["_rsi"], "roc": bar["_roc"],
            "plus_di": bar["_dp"], "minus_di": bar["_dm"],
            "adx": bar["_adx"], "chop": bar["_chop"],
            "buy_cond": bar["buy_cond"], "sell_cond": bar["sell_cond"],
            "trig_str": bar["trig_str"], "is_atm": i == cfg.ATM_IDX,
        })
        last_bar_inputs.append(bar)

    # Live bar processing (not replay, not dry_run)
    if not dry_run:
        events = tm.process_bar(
            last_bar_inputs, now,
            is_hard_exit_short(now), is_hard_exit_long(now),
            is_in_session(now), can_long_start(now)
        )
        for ev in events:
            ev["ts"] = now.strftime("%H:%M")
            st.session_state.trade_log.append(ev)
            icon = "SHORT" if "SHORT" in ev["type"] else "LONG"
            st.toast(f"[{icon}] {ev['type']} {ev['label']} @ {ev['price']:.2f}  ({ev['reason']})")

    st.session_state.last_data    = strike_rows
    st.session_state.last_refresh = now.strftime("%H:%M:%S")
    return strike_rows, last_bar_inputs


# ─────────────────────────────────────────────────────────────────────────────
# RENDER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def render_dashboard(strike_rows):
    valid = [r for r in strike_rows if r]
    if not valid:
        st.warning("No data — check Fyers token or market hours.")
        return

    # Recompute is_atm from current cfg.ATM_IDX so sidebar changes take effect
    # even when rendering from cached last_data
    atm_strike = cfg.STRIKES[cfg.ATM_IDX]["strike"]
    for r in valid:
        r["is_atm"] = (r["strike"] == atm_strike)

    # ── 1. Market Overview ─────────────────────────────────────────────────
    st.markdown("### Market Overview")
    hdr = ("<tr><th>Strike</th><th>Open</th><th>LTP</th><th>Chg</th>"
           "<th>CE</th><th>PE</th><th>Lead</th>"
           "<th>Regime</th><th>Ind.Reg</th><th>Mode</th><th>T.Type</th>"
           "<th>BUY</th><th>SELL</th></tr>")
    trs = ""
    for r in valid:
        chg = r["change"]
        cc  = "#22c55e" if chg >= 0 else "#ef4444"
        cs  = f"<span style='color:{cc}'>{'+' if chg >= 0 else ''}{chg:.1f}</span>"
        lbl = (f"<b style='color:#facc15'>[ATM] {r['label']}</b> <span style='color:#6b7280'>({r['strike']})</span>"
               if r["is_atm"] else
               f"{r['label']} <span style='color:#6b7280'>({r['strike']})</span>")
        dc = "#22c55e" if r["dom"] == "CE" else "#f87171"
        trs += (
            f"<tr>"
            f"<td>{lbl}</td>"
            f"<td>{_fmt(r['daily_open'], 2)}</td>"
            f"<td><b>{r['close']:.2f}</b></td>"
            f"<td>{cs}</td>"
            f"<td style='color:#60a5fa'>{r['ce_close']:.2f}</td>"
            f"<td style='color:#f87171'>{r['pe_close']:.2f}</td>"
            f"<td><b style='color:{dc}'>{r['dom']}</b></td>"
            f"<td>{_regime_badge(r['regime'])}</td>"
            f"<td>{_mode_badge(r['ind_reg'])}</td>"
            f"<td>{_mode_badge(r['mode'])}</td>"
            f"<td>{_ttype_badge(r['ttype'])}</td>"
            f"<td style='text-align:center'>{'YES' if r['buy_cond'] else '—'}</td>"
            f"<td style='text-align:center'>{'YES' if r['sell_cond'] else '—'}</td>"
            f"</tr>"
        )
    st.markdown(f"""
    <div class="card" style="overflow-x:auto;padding:0">
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead style="background:#1e293b;color:#94a3b8;text-transform:uppercase;font-size:11px">{hdr}</thead>
      <tbody style="color:#e2e8f0">{trs}</tbody>
    </table></div>""", unsafe_allow_html=True)

    # ── 2. ATM Indicator Gauges ────────────────────────────────────────────
    atm = next((r for r in valid if r["is_atm"]), None)
    if atm:
        st.markdown("### ATM Indicators")
        ind_cols = st.columns(6)
        specs = [
            ("RSI",  atm["rsi"],       0,  100, "#a78bfa"),
            ("ROC",  atm["roc"],      -30,  30, "#38bdf8"),
            ("+DI",  atm["plus_di"],   0,   40, "#4ade80"),
            ("-DI",  atm["minus_di"],  0,   40, "#f87171"),
            ("ADX",  atm["adx"],       0,   60, "#facc15"),
            ("CHOP", atm["chop"],      0,  100, "#fb923c"),
        ]
        for col, (lbl, val, lo, hi, clr) in zip(ind_cols, specs):
            col.markdown(
                f'<div class="card" style="padding:10px 12px">'
                f'<div style="font-size:11px;color:#6b7280;text-transform:uppercase">{lbl}</div>'
                f'<div style="font-size:20px;font-weight:700;color:#f1f5f9">{_fmt(val)}</div>'
                f'{_prog_html(val, lo, hi, clr)}</div>',
                unsafe_allow_html=True
            )

    # ── 3. Capital & P&L ──────────────────────────────────────────────────
    st.markdown("### Capital & P&L")
    summary   = tm.get_summary()
    total_pnl = sum(r["banked_rs"] for r in summary)
    equity    = cfg.INIT_CAPITAL + sum(tm.day_state.history_pnl) + total_pnl
    pct_chg   = total_pnl / cfg.INIT_CAPITAL * 100
    hist      = tm.day_state.history_pnl
    avg_hist  = sum(hist) / len(hist) if hist else 0.0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Equity",         f"Rs {equity:,.0f}",         delta=f"Rs {total_pnl:+,.0f}")
    mc2.metric("Day P&L",        f"Rs {total_pnl:+,.0f}",     delta=f"{pct_chg:+.2f}%")
    mc3.metric("Initial Capital", f"Rs {cfg.INIT_CAPITAL:,.0f}")
    mc4.metric("Avg Past P&L",   f"Rs {avg_hist:+,.0f}" if hist else "No history")

    if hist:
        st.markdown(
            "<div style='font-size:12px;color:#6b7280;margin-top:-4px'>History: " +
            " | ".join(
                f"<span style='color:{_pnl_color(v)}'>Rs {v:,.0f}</span>"
                for v in hist
            ) + "</div>",
            unsafe_allow_html=True
        )

    # ── 4. P&L Table (Pine Script-style) ─────────────────────────────────
    st.markdown("### P&L Table")

    # Build LTP map from strike_rows for floating P&L calculation
    ltp_map = {r["label"]: r["close"] for r in valid}

    # --- Build per-strike trade rows from trade_log (reliable replay events) ---
    # trade_log is populated by the replay and live bar processing.
    # Using it avoids dependency on tm.get_summary() session-state sync issues.
    log = st.session_state.trade_log

    # Aggregate per strike from trade_log events
    agg = {}   # label -> {cnt_short, cnt_long, banked_pts, banked_rs, entry_time,
               #            exit_time, last_ep, trig, in_short, in_long, lots}
    for ev in log:
        lbl = ev["label"]
        if lbl not in agg:
            agg[lbl] = {
                "cnt_short": 0, "cnt_long": 0,
                "banked_pts": 0.0, "banked_rs": 0.0,
                "entry_time": "—", "exit_time": "—",
                "last_ep": float("nan"), "trig": "—",
                "in_short": False, "in_long": False,
                "lots": cfg.LOTS_SHORT,
            }
        a = agg[lbl]
        t = ev["type"]
        if t == "SHORT_ENTRY":
            a["cnt_short"] += 1
            a["entry_time"] = ev["ts"]
            a["last_ep"]    = ev["price"]
            a["trig"]       = ev.get("reason", "OLD")
            a["in_short"]   = True
            a["in_long"]    = False
            a["lots"]       = ev["lots"]
        elif t == "SHORT_EXIT":
            a["banked_pts"] = ev["banked"]
            a["banked_rs"]  = ev["pnl_rs"]
            a["exit_time"]  = ev["ts"]
            a["in_short"]   = False
        elif t == "LONG_ENTRY":
            a["cnt_long"] += 1
            a["entry_time"] = ev["ts"]
            a["last_ep"]    = ev["price"]
            a["trig"]       = ev.get("reason", "BUY-V")
            a["in_long"]    = True
            a["in_short"]   = False
            a["lots"]       = ev["lots"]
        elif t == "LONG_EXIT":
            a["banked_pts"] = ev["banked"]
            a["banked_rs"]  = ev["pnl_rs"]
            a["exit_time"]  = ev["ts"]
            a["in_long"]    = False

    # Also fold in any open positions from get_summary() that have no exit event yet
    for s in summary:
        lbl = s["label"]
        if s["in_short"] or s["in_long"]:
            if lbl not in agg:
                agg[lbl] = {
                    "cnt_short": s["cnt_short"], "cnt_long": s["cnt_long"],
                    "banked_pts": s["banked_pts"], "banked_rs": s["banked_rs"],
                    "entry_time": s["entry_time"], "exit_time": "OPEN",
                    "last_ep": s["last_ep"], "trig": s["trig"],
                    "in_short": s["in_short"], "in_long": s["in_long"],
                    "lots": s["lots"],
                }
            else:
                a = agg[lbl]
                if (s["in_short"] and a["in_short"]) or (s["in_long"] and a["in_long"]):
                    a["exit_time"] = "OPEN"
                    a["last_ep"]   = s["last_ep"]

    # Build trade_rows preserving strike order from cfg.STRIKES
    trade_rows = []
    for sc in cfg.STRIKES:
        lbl = sc["label"]
        if lbl not in agg:
            continue
        a = agg[lbl]
        in_pos   = a["in_short"] or a["in_long"]
        exit_disp = "OPEN" if in_pos else a["exit_time"]
        trig = a["trig"]
        trig_cls = ("yellow"
                    if any(k in trig.upper() for k in ("BUY", "OLD", "V", "BASE", "NEW"))
                    else "orange" if any(k in trig.upper() for k in ("SELL", "SHORT", "SL", "VWAP"))
                    else "gray")
        trade_rows.append({
            "label":    lbl,
            "entry":    a["entry_time"],
            "exit":     exit_disp,
            "lots":     a["lots"],
            "ep_val":   a["last_ep"],
            "bkd_pts":  a["banked_pts"],
            "bkd_rs":   a["banked_rs"],
            "trig":     trig,
            "trig_cls": trig_cls,
            "S":        a["cnt_short"],
            "B":        a["cnt_long"],
            "in_pos":   in_pos,
            "in_short": a["in_short"],
            "in_long":  a["in_long"],
            "ep_open":  a["last_ep"] if in_pos else float("nan"),
        })

    # --- Floating P&L: unrealized for all open positions ---
    float_total = 0.0
    for row in trade_rows:
        if row["in_pos"] and not _nan(row["ep_open"]):
            ltp = ltp_map.get(row["label"])
            if ltp and not _nan(ltp):
                lots = row["lots"]
                if row["in_short"]:
                    float_total += (row["ep_open"] - ltp) * cfg.LOT_SIZE * lots
                else:
                    float_total += (ltp - row["ep_open"]) * cfg.LOT_SIZE * lots

    # --- Account-level numbers ---
    day_realized = sum(r["bkd_rs"] for r in trade_rows)
    equity       = cfg.INIT_CAPITAL + sum(tm.day_state.history_pnl) + day_realized
    total_S      = sum(r["S"] for r in trade_rows)
    total_B      = sum(r["B"] for r in trade_rows)
    hist         = tm.day_state.history_pnl
    hist_str     = " | ".join(f"₹{v:+,.0f}" for v in hist) if hist else "—"

    if trade_rows:
        # ── Table header ──────────────────────────────────────────────────
        th = """<tr>
          <th>STRIKE</th><th>ENTRY</th><th>EXIT</th><th>LOTS</th>
          <th>PRICE</th><th>PTS</th><th>P&amp;L</th><th>TRIG</th>
          <th>S</th><th>B</th>
        </tr>"""

        # ── Trade rows ────────────────────────────────────────────────────
        tr_html = ""
        for r in trade_rows:
            pts_v  = r["bkd_pts"]
            rs_v   = r["bkd_rs"]
            pts_c  = "#22c55e" if pts_v > 0 else ("#ef4444" if pts_v < 0 else "#94a3b8")
            rs_c   = "#22c55e" if rs_v  > 0 else ("#ef4444" if rs_v  < 0 else "#94a3b8")
            _pts_str = f"+{pts_v:g}" if pts_v >= 0 else f"{pts_v:g}"
            _rs_abs  = abs(int(rs_v)) if rs_v == int(rs_v) else abs(rs_v)
            _rs_str  = f"+₹{abs(rs_v):.0f}" if rs_v >= 0 else f"-₹{abs(rs_v):.0f}"
            pts_s  = f"<span style='color:{pts_c};font-weight:700'>{_pts_str}</span>"
            rs_s   = f"<span style='color:{rs_c};font-weight:700'>{_rs_str}</span>"
            ep_s   = f"{r['ep_val']:.2f}" if not _nan(r["ep_val"]) else "—"
            exit_s = (f"<span style='color:#f59e0b;font-weight:700'>OPEN</span>"
                      if r["exit"] == "OPEN"
                      else f"<span style='color:#94a3b8'>{r['exit']}</span>")
            trig_s = f"<span class='badge badge-{r['trig_cls']}'>{r['trig']}</span>"
            lbl_c  = "#facc15" if r["label"] == cfg.STRIKES[cfg.ATM_IDX]["label"] else "#f1f5f9"
            tr_html += f"""<tr>
              <td><b style='color:{lbl_c}'>{r["label"]}</b></td>
              <td style='color:#94a3b8'>{r["entry"]}</td>
              <td>{exit_s}</td>
              <td>{r["lots"]}</td>
              <td style='color:#60a5fa'>{ep_s}</td>
              <td>{pts_s}</td>
              <td>{rs_s}</td>
              <td>{trig_s}</td>
              <td style='color:#f87171'>{r["S"]}</td>
              <td style='color:#4ade80'>{r["B"]}</td>
            </tr>"""

        # ── Account Summary rows ──────────────────────────────────────────
        day_c  = "#22c55e" if day_realized >= 0 else "#ef4444"
        flt_c  = "#22c55e" if float_total  >= 0 else "#ef4444"

        _dr_str  = f"+₹{abs(day_realized):.0f}" if day_realized >= 0 else f"-₹{abs(day_realized):.0f}"
        _flt_str = f"+₹{abs(float_total):.0f}"  if float_total  >= 0 else f"-₹{abs(float_total):.0f}"
        acct_html = f"""
        <tr style='background:#1e293b;border-top:2px solid #334155'>
          <td style='color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.5px'
              colspan='1'>--- ACCOUNT SUMMARY ---</td>
          <td style='color:#6b7280;font-size:11px'>CAPITAL</td>
          <td colspan='2'><b style='color:#4ade80'>₹{equity:,.0f}</b></td>
          <td style='color:#6b7280;font-size:11px'>DAY P&amp;L</td>
          <td colspan='3'><b style='color:{day_c}'>{_dr_str}</b></td>
          <td style='color:#f87171;font-weight:700'>{total_S}</td>
          <td style='color:#4ade80;font-weight:700'>{total_B}</td>
        </tr>
        <tr style='background:#161b27;border-bottom:1px solid #1e293b'>
          <td style='color:#6b7280;font-size:11px;text-transform:uppercase'>FLOATING</td>
          <td colspan='9'><b style='color:{flt_c}'>{_flt_str}</b></td>
        </tr>
        <tr style='background:#0f1420'>
          <td colspan='10' style='color:#6b7280;font-size:11px;padding:7px 10px'>
            HIST: {hist_str}
          </td>
        </tr>"""

        st.markdown(f"""
        <div class="card" style="overflow-x:auto;padding:0">
        <table style="width:100%;border-collapse:collapse;font-size:13px;line-height:1.6">
          <thead style="background:#1e293b;color:#6b7280;text-transform:uppercase;
                        font-size:11px;letter-spacing:.5px">{th}</thead>
          <tbody style="color:#e2e8f0">{tr_html}{acct_html}</tbody>
        </table></div>""", unsafe_allow_html=True)
    else:
        # Even with no trades show the account summary skeleton
        hist_row = f"<div style='color:#6b7280;font-size:11px;margin-top:8px'>HIST: {hist_str}</div>"
        st.markdown(
            f'<div class="card" style="padding:16px">'
            f'<div style="color:#6b7280;text-align:center;padding:8px 0">No trades yet today</div>'
            f'<div style="display:flex;gap:24px;margin-top:10px;border-top:1px solid #1f2937;padding-top:10px">'
            f'<div><span style="color:#6b7280;font-size:11px">CAPITAL</span><br>'
            f'<b style="color:#4ade80">₹{equity:,.0f}</b></div>'
            f'<div><span style="color:#6b7280;font-size:11px">DAY P&L</span><br>'
            f'<b style="color:#94a3b8">₹0</b></div>'
            f'<div><span style="color:#6b7280;font-size:11px">FLOATING</span><br>'
            f'<b style="color:#94a3b8">₹0</b></div>'
            f'</div>{hist_row}</div>',
            unsafe_allow_html=True
        )


def render_dry_run(strike_rows):
    """Detailed per-strike diagnostic — shown only after Dry Run button."""
    st.markdown("---")
    st.markdown("### Dry Run — Signal Diagnostics")
    valid = [r for r in strike_rows if r]
    if not valid:
        st.warning("No data to analyse.")
        return

    for r in valid:
        action = "BUY SIGNAL" if r["buy_cond"] else ("SELL SIGNAL" if r["sell_cond"] else "No Signal")
        atm_tag = "  [ATM]" if r["is_atm"] else ""
        with st.expander(f"{r['label']} ({r['strike']}){atm_tag}  |  {action}",
                         expanded=r["is_atm"]):
            c1, c2, c3 = st.columns(3)
            c1.metric("LTP",    f"{r['close']:.2f}")
            c2.metric("Change", f"{r['change']:+.2f}")
            c3.metric("Lead",   r["dom"])

            s1, s2, s3, s4 = st.columns(4)
            s1.markdown(f"**Regime:** {_regime_badge(r['regime'])}", unsafe_allow_html=True)
            s2.markdown(f"**Mode:** {_mode_badge(r['mode'])}", unsafe_allow_html=True)
            s3.markdown(f"**T.Type:** {_ttype_badge(r['ttype'])}", unsafe_allow_html=True)
            s4.markdown(f"**Ind.Reg:** {_mode_badge(r['ind_reg'])}", unsafe_allow_html=True)

            r1, r2, r3, r4, r5, r6 = st.columns(6)
            r1.metric("RSI",  _fmt(r["rsi"]))
            r2.metric("ROC",  _fmt(r["roc"]))
            r3.metric("+DI",  _fmt(r["plus_di"]))
            r4.metric("-DI",  _fmt(r["minus_di"]))
            r5.metric("ADX",  _fmt(r["adx"]))
            r6.metric("CHOP", _fmt(r["chop"]))

            if r["trig_str"]:
                st.info(f"Trigger: {r['trig_str']}")

    st.success(
        f"Dry run complete at {datetime.now():%H:%M:%S}. "
        "No orders placed. Review signals above before switching to LIVE mode."
    )


# ─────────────────────────────────────────────────────────────────────────────
# ERROR BANNER
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.error_msg:
    st.error(f"Error: {st.session_state.error_msg}")
    st.info("Run `python 1_login_test.py` to refresh your Fyers access token.")

# ─────────────────────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────────────────────
if do_dry_run:
    rows, _ = fetch_and_process(dry_run=True)
    if rows:
        render_dashboard(rows)
        render_dry_run(rows)
elif do_refresh:
    rows, _ = fetch_and_process()
    if rows:
        render_dashboard(rows)
elif st.session_state.last_data:
    render_dashboard(st.session_state.last_data)
else:
    st.markdown(
        '<div class="card" style="text-align:center;padding:40px">'
        '<div style="font-size:40px">⚡</div>'
        '<div style="font-size:18px;color:#94a3b8;margin-top:10px">'
        'Click <b>Refresh</b> to load live data &nbsp;|&nbsp; '
        '<b>Dry Run</b> to test signals without placing orders'
        '</div></div>',
        unsafe_allow_html=True
    )

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-REFRESH PROGRESS BAR
# ─────────────────────────────────────────────────────────────────────────────
_now_ts  = time.time()
_elapsed = int(_now_ts - st.session_state._last_auto_ts)
_rem     = max(0, refresh_sec - _elapsed)
_fill    = int(min(1.0, _elapsed / max(refresh_sec, 1)) * 100)

st.markdown(
    f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px">'
    f'<div style="font-size:11px;color:#374151;min-width:160px">Auto-refresh in {_rem}s</div>'
    f'<div style="flex:1;height:3px;background:#111827;border-radius:2px">'
    f'<div style="width:{_fill}%;height:3px;background:#3b82f6;border-radius:2px"></div>'
    f'</div></div>',
    unsafe_allow_html=True
)

if _now_ts - st.session_state._last_auto_ts >= refresh_sec:
    st.session_state._last_auto_ts = _now_ts
    fetch_and_process()   # updates last_data; rerun below will render it once

time.sleep(1)
st.rerun()
