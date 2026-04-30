import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import requests
from datetime import datetime, timedelta
import config
from fyers_apiv3 import fyersModel
import os

# ==========================================
# ⚙️ UI CONFIGURATION
# ==========================================
st.set_page_config(page_title="Stoxxo V27 (Hybrid)", page_icon="⚡", layout="wide")
st.markdown("""
    <style>
        .stApp { background-color: #000000; color: #ffffff; } 
        section[data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #333; }
        .stExpander { background-color: #222222; border: 1px solid #444; }
        thead tr th { background-color: #333333 !important; color: #ffffff !important; }
        tbody tr td { color: #ffffff !important; }
        td[data-testid="stTableStyledCell"] { font-weight: bold; }
        .timer-box { font-size: 20px; font-weight: bold; color: #00FF00; border: 1px solid #333; padding: 5px 10px; border-radius: 5px; display: inline-block;}
        /* Manual Button Styles */
        .manual-fire { color: red !important; font-weight: bold; border: 2px solid red !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 💾 PERSISTENCE & STATE
# ==========================================
DATA_FILE = "stoxxo_data.csv"


def is_auth_error(resp):
    """Return True when Fyers API indicates token/auth failure."""
    return isinstance(resp, dict) and str(resp.get("code")) == "-16"

def load_data():
    default_state = {"wallet": 2300000.0, "daily_pnl": 0.0, "history": [0.0]*5}
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            last = df.iloc[-1]
            return {
                "wallet": float(last['wallet']),
                "daily_pnl": float(last['daily_pnl']),
                "history": [float(x) for x in str(last['history']).split('|') if x]
            }
        except: return default_state
    return default_state

def save_data(wallet, daily_pnl, history):
    hist_str = "|".join([str(x) for x in history])
    df = pd.DataFrame([{"timestamp": datetime.now(), "wallet": wallet, "daily_pnl": daily_pnl, "history": hist_str}])
    df.to_csv(DATA_FILE, mode='a', header=not os.path.exists(DATA_FILE), index=False)

if "init_done" not in st.session_state:
    data = load_data()
    st.session_state.wallet = data['wallet']
    st.session_state.daily_pnl = data['daily_pnl']
    st.session_state.history_pnl = data['history']
    st.session_state.trade_log = []
    st.session_state.webhook_log = [] # New Log for Stoxxo
    st.session_state.positions = {}
    # Independent Manual State
    st.session_state.manual_pos = {'status': 'NONE', 'entry': 0, 'row_id': -1} 
    st.session_state.init_done = True

# ==========================================
# 🚀 SIGNAL SENDER (UPDATED WITH LOGGING)
# ==========================================
def fire_to_stoxxo(url, message, is_live):
    """Sends signal to Stoxxo and Logs it"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    # 1. Paper Trade Mode
    if not is_live:
        log_entry = {"Time": timestamp, "Message": message, "Status": "PAPER", "Response": "Simulated"}
        st.session_state.webhook_log.append(log_entry)
        return True, "Paper"

    # 2. Live Execution
    if not url or "http" not in url:
        return False, "Invalid URL"
    
    try:
        response = requests.post(url, data=message, timeout=2)
        status_code = response.status_code
        resp_text = response.text[:50] # First 50 chars
        
        # Log to Table
        log_entry = {"Time": timestamp, "Message": message, "Status": str(status_code), "Response": resp_text}
        st.session_state.webhook_log.append(log_entry)
        
        if status_code == 200: return True, "200 OK"
        else: return False, f"Err {status_code}"
        
    except Exception as e:
        log_entry = {"Time": timestamp, "Message": message, "Status": "FAIL", "Response": str(e)}
        st.session_state.webhook_log.append(log_entry)
        return False, "Failed"

# ==========================================
# 🔧 DATA ENGINE
# ==========================================
def get_access_token():
    if not os.path.exists("access_token.txt"): return None
    with open("access_token.txt", "r") as f: return f.read().strip()

def get_month_code(month_str):
    m = month_str.upper()[:3]
    mapping = {"JAN": "1", "FEB": "2", "MAR": "3", "APR": "4", "MAY": "5", "JUN": "6",
               "JUL": "7", "AUG": "8", "SEP": "9", "OCT": "O", "NOV": "N", "DEC": "D"}
    return mapping.get(m, m)

def build_symbol_v3(index, yy, mm_input, dd, strike, side, is_weekly):
    root_map = {
        "NIFTY": "NSE:NIFTY",
        "BANKNIFTY": "NSE:BANKNIFTY",
        "SENSEX": "BSE:SENSEX"
    }
    root = root_map.get(index, "NSE:NIFTY")
    if is_weekly:
        m_code = get_month_code(mm_input)
        return f"{root}{yy}{m_code}{dd}{strike}{side}"
    else:
        return f"{root}{yy}{mm_input.upper()}{strike}{side}"


def _month_add(year, month, add):
    total = (year * 12 + (month - 1)) + add
    out_year = total // 12
    out_month = (total % 12) + 1
    return out_year, out_month


def _next_thursdays(count=10):
    today = datetime.now().date()
    out = []
    offset = (3 - today.weekday()) % 7
    first = today + timedelta(days=offset)
    for i in range(count):
        out.append(first + timedelta(days=7*i))
    return out


def _symbol_has_data(fyers, symbol, tf):
    data = {
        "symbol": symbol,
        "resolution": str(tf),
        "date_format": "0",
        "range_from": int(time.time()) - (2 * 86400),
        "range_to": int(time.time()),
        "cont_flag": "1"
    }
    resp = fyers.history(data=data)
    if is_auth_error(resp):
        raise RuntimeError("AUTH_EXPIRED")
    return isinstance(resp, dict) and isinstance(resp.get("candles"), list) and len(resp["candles"]) > 0


def detect_working_expiry(fyers, index, strike, tf):
    # 1) Prefer weekly expiries (next Thursdays)
    for d in _next_thursdays(count=10):
        yy, mm, dd = d.strftime("%y"), d.strftime("%b").upper(), d.strftime("%d")
        ce = build_symbol_v3(index, yy, mm, dd, str(strike), "CE", True)
        pe = build_symbol_v3(index, yy, mm, dd, str(strike), "PE", True)
        if _symbol_has_data(fyers, ce, tf) and _symbol_has_data(fyers, pe, tf):
            return {"yy": yy, "mm": mm, "dd": dd, "is_weekly": True}

    # 2) Fallback to monthly contracts for current + next 3 months
    now = datetime.now()
    for i in range(4):
        y, m = _month_add(now.year, now.month, i)
        yy = f"{y % 100:02d}"
        mm = datetime(y, m, 1).strftime("%b").upper()
        ce = build_symbol_v3(index, yy, mm, "", str(strike), "CE", False)
        pe = build_symbol_v3(index, yy, mm, "", str(strike), "PE", False)
        if _symbol_has_data(fyers, ce, tf) and _symbol_has_data(fyers, pe, tf):
            return {"yy": yy, "mm": mm, "dd": "", "is_weekly": False}

    return None

def fetch_synthetic_straddle(fyers, sym_ce, sym_pe, tf):
    def fetch(sym):
        data = {"symbol": sym, "resolution": str(tf), "date_format": "0", "range_from": int(time.time()) - (5*86400), "range_to": int(time.time()), "cont_flag": "1"}
        resp = fyers.history(data=data)
        if is_auth_error(resp):
            raise RuntimeError("AUTH_EXPIRED")
        if "candles" not in resp: return None
        df = pd.DataFrame(resp["candles"], columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        df.set_index("timestamp", inplace=True)
        return df.astype(float)

    ce = fetch(sym_ce)
    pe = fetch(sym_pe)
    if ce is None or pe is None: return None, 0, 0, 0, 0, 0, 0, 0, 0

    df = pd.merge(ce, pe, left_index=True, right_index=True, suffixes=('_c', '_p'))
    df['open'] = df['open_c'] + df['open_p']
    df['close'] = df['close_c'] + df['close_p']
    df['high'] = df[['open', 'close']].max(axis=1)
    df['low'] = df[['open', 'close']].min(axis=1)
    df['volume'] = df['volume_c'] + df['volume_p']
    
    curr_date = df.index[-1].date()
    day_df = df[df.index.date == curr_date]
    day_open = day_df['open'].iloc[0] if not day_df.empty else df['open'].iloc[-1]
    ce_do = day_df['open_c'].iloc[0] if not day_df.empty else df['open_c'].iloc[-1]
    pe_do = day_df['open_p'].iloc[0] if not day_df.empty else df['open_p'].iloc[-1]

    df['ema'] = ta.ema(df['close'], length=20)
    df['vwma'] = ta.vwma(df['close'], df['volume'], length=35)
    df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['roc'] = ta.roc(df['close'], length=14)
    adx = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx is not None:
        df['di_p'] = adx['DMP_14']
        df['di_m'] = adx['DMN_14']
        df['adx'] = adx['ADX_14']
    try: df['chop'] = ta.chop(df['high'], df['low'], df['close'], length=14)
    except: df['chop'] = 50

    df = df.ffill().bfill()
    return df, df['close_c'].iloc[-1], df['close_p'].iloc[-1], df['open_c'].iloc[-1], df['open_p'].iloc[-1], day_open, ce_do, pe_do

# ==========================================
# 🧠 LOGIC ENGINE
# ==========================================
def process_logic(df, settings):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    c, ema, vwap, vwma = curr['close'], curr['ema'], curr['vwap'], curr['vwma']
    rsi, roc, di_p, di_m = curr['rsi'], curr['roc'], curr['di_p'], curr['di_m']
    chop, adx = curr['chop'], curr['adx']
    
    ind_reg = "Neutral"
    if adx < 15: ind_reg = "NoTrend"
    elif rsi > 55 and di_p > di_m: ind_reg = "Bullish"
    elif rsi < 45 and di_m > di_p: ind_reg = "Bearish"
    
    regime = "SIDEWAYS"
    if adx > prev['adx']: regime = "EXPANDING"
    
    t_mode, t_type = "WAIT...", "NoTrade"
    
    if settings['filter_chop'] and chop > settings['chop_limit']:
        return "WAIT...", "NoTrade", ind_reg, regime

    strict = settings['mode'] == "Strict"
    
    price_sell = (c < ema) and (c < vwap or c < vwma) if strict else (c < ema)
    trend_valid = True
    if settings['bd_window'] > 0:
        subset = df.tail(settings['bd_window'] + 1)
        trend_valid = ((subset['ema'] < subset['vwap']) & (subset['ema'].shift(1) >= subset['vwap'].shift(1))).any()
    else:
        trend_valid = (ema < vwap) or (vwma < vwap)

    old_logic = price_sell and (rsi < 40) and (di_m > di_p) and (roc < 0)
    new_logic = trend_valid
    
    prev_mid = (prev['open'] + prev['close']) / 2
    reversal = settings['use_rev'] and (prev['close'] > prev['open']) and (prev['close'] > prev['vwap']) and \
               (curr['close'] < curr['open']) and (c < prev_mid)
    
    sell_signal = False
    if settings['use_old'] and settings['use_new']: sell_signal = old_logic and new_logic
    elif settings['use_old']: sell_signal = old_logic
    elif settings['use_new']: sell_signal = new_logic
    
    if sell_signal or reversal:
        t_mode = "SELL STR"
        t_type = "Sell Str"

    price_buy = (c > ema) and (c > vwap or c > vwma) if strict else (c > ema)
    mom_buy = (rsi > 40) and (di_p > di_m) and (roc > 0)
    if (price_buy and mom_buy) or (c > vwap):
        t_mode = "BUY EXIT"
        t_type = "Buy Str"

    return t_mode, t_type, ind_reg, regime

def get_timer(resolution_str):
    res_int = int(resolution_str)
    now = datetime.now()
    next_min = res_int - (now.minute % res_int)
    sec_rem = 60 - now.second
    return f"⏳ {next_min-1}m {sec_rem}s"

# ==========================================
# 🖥️ DASHBOARD MAIN
# ==========================================
def main():
    if "exp_yy" not in st.session_state:
        st.session_state.exp_yy = "26"
    if "exp_mm" not in st.session_state:
        st.session_state.exp_mm = "JAN"
    if "exp_dd" not in st.session_state:
        st.session_state.exp_dd = "06"
    if "auto_expiry" not in st.session_state:
        st.session_state.auto_expiry = True
    if "auto_expiry_done" not in st.session_state:
        st.session_state.auto_expiry_done = False

    c1, c2 = st.columns([3, 1])
    c1.title("⚡ Stoxxo V27 (Hybrid)")
    timer_placeholder = c2.empty()
    
    with st.sidebar:
        # MANUAL CONTROLS
        with st.expander("🔥 Manual Controls (ATM)", expanded=True):
            st.caption("Strike 3 Independent Fire")
            if st.session_state.manual_pos['status'] == 'NONE':
                if st.button("🔥 FIRE ATM NOW", use_container_width=True):
                    st.session_state.manual_trigger = "ENTRY"
            else:
                if st.button("🛑 EXIT MANUAL", use_container_width=True):
                    st.session_state.manual_trigger = "EXIT"

        with st.expander("1. Setup", expanded=True):
            idx = st.selectbox("Index", ["NIFTY", "BANKNIFTY", "SENSEX"])
            tf_sel = st.selectbox("Timeframe", ["1 Min", "3 Min", "5 Min", "15 Min"], index=2)
            tf_map = {"1 Min": "1", "3 Min": "3", "5 Min": "5", "15 Min": "15"}
            current_tf = tf_map[tf_sel]
            
            st.markdown("---")
            is_weekly = st.checkbox("Weekly Expiry?", True)
            st.checkbox("Auto Detect Expiry", key="auto_expiry")
            c1, c2, c3 = st.columns(3)
            c1.text_input("YY", key="exp_yy")
            c2.text_input("MM", key="exp_mm")
            c3.text_input("DD", key="exp_dd")
            yy, mm, dd = st.session_state.exp_yy, st.session_state.exp_mm, st.session_state.exp_dd
            if st.button("🎯 Detect Expiry Now"):
                st.session_state.force_detect_expiry = True
            if st.button("🔄 Test Data"): st.session_state.test_fetch = True

        with st.expander("2. Strikes", expanded=True):
            def s_row(lbl, val):
                c1, c2, c3, c4 = st.columns([2, 0.8, 0.8, 0.8])
                v = c1.number_input(lbl, val, step=50)
                en = c2.checkbox("En", True, key=lbl+"en")
                return {'val': v, 'en': en}
            strikes = [s_row("S1", 24800), s_row("S2", 24900), s_row("S3", 25000), s_row("S4", 25100), s_row("S5", 25200)]

        with st.expander("3. Logic", expanded=False):
            logic_settings = {
                "mode": st.selectbox("Mode", ["Auto", "Strict", "Simple"], 1),
                "filter_chop": st.checkbox("Filter Chop", True),
                "chop_limit": st.number_input("Limit", 61.8),
                "bd_window": st.number_input("Breakdown Window", 0),
                "use_old": st.checkbox("Momentum", True),
                "use_new": st.checkbox("Trend", False),
                "use_rev": st.checkbox("Reversal", False)
            }

        with st.expander("6. Account", expanded=False):
            st.number_input("Capital", 2300000)
            lot_size = st.number_input("Lot Size", 65)
            user_lots = st.number_input("Lots", 4)

        with st.expander("7. Alerts (Stoxxo)", expanded=True):
            st.caption("Stoxxo Configuration")
            webhook_url = st.text_input("Webhook URL", "https://stoxxo.in/webhook/...")
            stag = st.text_input("Tag", "DEFAULT")
            entry_tpl = st.text_area("Entry", "MULTILEG:YES,TYPE:ENTRY,OPT:STRADDLE_{{strike}},STAG:{{strategy}},LOTS:{{lots}}")
            exit_tpl = st.text_area("Exit", "MULTILEG:YES,TYPE:EXIT,OPT:STRADDLE_{{strike}},STAG:{{strategy}},LOTS:{{lots}}")

        # RENAMED TOGGLE AS REQUESTED
        live_execution = st.checkbox("🔴 LIVE EXECUTION (Uncheck for Paper)", False)

    # --- MAIN DISPLAY ---
    c1, c2 = st.columns([3, 1])
    monitor_slot = c1.empty()
    acc_slot = c2.empty()
    
    st.markdown("### 📝 P&L Trade Log")
    pnl_slot = st.empty()
    
    # NEW WEBHOOK LOG SECTION
    st.markdown("### 📜 Webhook Logs")
    webhook_slot = st.empty()
    alert_slot = st.empty()

    token = get_access_token()
    if not token: st.error("No Token"); return
    fyers = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False, log_path="")

    # Early auth check so expired tokens don't fail silently in the grid loop.
    try:
        q = fyers.quotes(data={"symbols": "NSE:NIFTY50-INDEX"})
        if is_auth_error(q):
            st.error("Fyers token expired/invalid (code -16). Run 1_login_test.py to refresh access_token.txt, then restart dashboard.")
            return
    except Exception:
        pass

    # Auto-detect valid expiry once per run or when explicitly requested.
    force_detect = st.session_state.get("force_detect_expiry", False)
    if st.session_state.get("auto_expiry", True) and (force_detect or not st.session_state.get("auto_expiry_done", False)):
        try:
            with st.spinner("Detecting valid expiry from live option symbols..."):
                detected = detect_working_expiry(fyers, idx, strikes[2]['val'], current_tf)
            if detected:
                st.session_state.exp_yy = detected["yy"]
                st.session_state.exp_mm = detected["mm"]
                st.session_state.exp_dd = detected["dd"]
                is_weekly = detected["is_weekly"]
                st.session_state.auto_expiry_done = True
                st.success(f"Expiry set: {detected['yy']} {detected['mm']} {detected['dd']} ({'Weekly' if detected['is_weekly'] else 'Monthly'})")
            else:
                st.warning("Could not auto-detect an expiry from current settings. Try adjusting strikes/index and click Detect Expiry Now.")
        except Exception as e:
            if "AUTH_EXPIRED" in str(e):
                st.error("Fyers token expired/invalid (code -16). Run 1_login_test.py to refresh access_token.txt, then restart dashboard.")
                return
            st.warning(f"Expiry auto-detect failed: {e}")
        finally:
            st.session_state.force_detect_expiry = False
    yy, mm, dd = st.session_state.exp_yy, st.session_state.exp_mm, st.session_state.exp_dd

    # Fetch Test
    if st.session_state.get('test_fetch'):
        s = strikes[2]
        sym = build_symbol_v3(idx, yy, mm, dd, str(s['val']), "CE", is_weekly)
        st.info(f"Fetch: {sym}")
        try:
            d = {"symbol": sym, "resolution": current_tf, "date_format": "0", "range_from": int(time.time())-86400, "range_to": int(time.time()), "cont_flag": "1"}
            r = fyers.history(data=d)
            if "candles" in r: st.success("OK")
            else: st.error("No Data")
        except: st.error("Error")
        st.session_state.test_fetch = False

    while True:
        timer_placeholder.markdown(f"<div class='timer-box'>{get_timer(current_tf)}</div>", unsafe_allow_html=True)
        rows = []
        alerts = []
        floating_total = 0.0
        
        for i, s in enumerate(strikes):
            try:
                ce = build_symbol_v3(idx, yy, mm, dd, str(s['val']), "CE", is_weekly)
                pe = build_symbol_v3(idx, yy, mm, dd, str(s['val']), "PE", is_weekly)
                df, ce_ltp, pe_ltp, ce_o, pe_o, day_o, ce_do, pe_do = fetch_synthetic_straddle(fyers, ce, pe, current_tf)
                
                if df is not None:
                    t_mode, t_type, ind_reg, regime = process_logic(df, logic_settings)
                    ltp = df['close'].iloc[-1]
                    change = ltp - day_o
                    
                    # Lead Calculation
                    ce_gain = ce_ltp - ce_do
                    pe_gain = pe_ltp - pe_do
                    dom_arrow = "▲" if ce_gain >= pe_gain else "▼"
                    dir_arrow = "↑" if change > 0 else "↓"
                    lead = f"{'CE' if ce_gain >= pe_gain else 'PE'} {dom_arrow} {dir_arrow}"
                    
                    pos_key = int(s['val'])
                    # AUTO POS STATE
                    if pos_key not in st.session_state.positions:
                        st.session_state.positions[pos_key] = {'status': 'NONE', 'entry': 0, 'row_id': -1}
                    p = st.session_state.positions[pos_key]
                    
                    # ----------------------------
                    # 🔥 MANUAL FIRE LOGIC (Strike 3 Only)
                    # ----------------------------
                    if i == 2: # Strike 3 Index
                        m_trigger = st.session_state.get('manual_trigger', None)
                        m_pos = st.session_state.manual_pos
                        
                        # MANUAL ENTRY
                        if m_trigger == "ENTRY" and m_pos['status'] == 'NONE':
                            msg = entry_tpl.replace("{{strike}}", str(s['val'])).replace("{{strategy}}", stag).replace("{{lots}}", str(user_lots))
                            ok, status = fire_to_stoxxo(webhook_url, msg, live_execution)
                            alerts.append(f"MANUAL ENTRY {s['val']} [{status}]")
                            
                            new_row = {"STRIKE": f"{s['val']} (M)", "ENTRY": datetime.now().strftime('%H:%M'), "EXIT": "Running...", "LOTS": user_lots, "PRICE": ltp, "PTS": 0.0, "P&L": 0.0}
                            st.session_state.trade_log.append(new_row)
                            st.session_state.manual_pos = {'status': 'SHORT', 'entry': ltp, 'row_id': len(st.session_state.trade_log)-1}
                            st.session_state.manual_trigger = None

                        # MANUAL EXIT
                        elif m_trigger == "EXIT" and m_pos['status'] == 'SHORT':
                            msg = exit_tpl.replace("{{strike}}", str(s['val'])).replace("{{strategy}}", stag).replace("{{lots}}", str(user_lots))
                            ok, status = fire_to_stoxxo(webhook_url, msg, live_execution)
                            alerts.append(f"MANUAL EXIT {s['val']} [{status}]")
                            
                            pts = m_pos['entry'] - ltp
                            pnl = pts * user_lots * lot_size
                            st.session_state.wallet += pnl
                            st.session_state.daily_pnl += pnl
                            
                            r_id = m_pos['row_id']
                            st.session_state.trade_log[r_id]['EXIT'] = datetime.now().strftime('%H:%M')
                            st.session_state.trade_log[r_id]['PRICE'] = ltp
                            st.session_state.trade_log[r_id]['PTS'] = round(pts, 2)
                            st.session_state.trade_log[r_id]['P&L'] = round(pnl, 0)
                            
                            st.session_state.manual_pos = {'status': 'NONE', 'entry': 0, 'row_id': -1}
                            st.session_state.manual_trigger = None
                        
                        # MANUAL P&L UPDATE
                        if m_pos['status'] == 'SHORT':
                            r_id = m_pos['row_id']
                            curr_pts = m_pos['entry'] - ltp
                            curr_pnl = curr_pts * user_lots * lot_size
                            floating_total += curr_pnl
                            st.session_state.trade_log[r_id]['PRICE'] = ltp
                            st.session_state.trade_log[r_id]['PTS'] = round(curr_pts, 2)
                            st.session_state.trade_log[r_id]['P&L'] = round(curr_pnl, 0)

                    # ----------------------------
                    # 🤖 AUTO LOGIC (All Strikes)
                    # ----------------------------
                    # Update Floating P&L
                    if p['status'] == 'SHORT' and p['row_id'] >= 0:
                        r_id = p['row_id']
                        curr_pts = p['entry'] - ltp
                        curr_pnl = curr_pts * user_lots * lot_size
                        floating_total += curr_pnl
                        st.session_state.trade_log[r_id]['PRICE'] = ltp
                        st.session_state.trade_log[r_id]['PTS'] = round(curr_pts, 2)
                        st.session_state.trade_log[r_id]['P&L'] = round(curr_pnl, 0)

                    # ENTRY SIGNAL
                    if p['status'] == 'NONE' and t_mode == "SELL STR":
                        msg = entry_tpl.replace("{{strike}}", str(s['val'])).replace("{{strategy}}", stag).replace("{{lots}}", str(user_lots))
                        
                        ok, status = fire_to_stoxxo(webhook_url, msg, live_execution)
                        alerts.append(f"ENTRY {s['val']} [{status}]")
                        
                        new_row = {"STRIKE": s['val'], "ENTRY": datetime.now().strftime('%H:%M'), "EXIT": "Running...", "LOTS": user_lots, "PRICE": ltp, "PTS": 0.0, "P&L": 0.0}
                        st.session_state.trade_log.append(new_row)
                        st.session_state.positions[pos_key] = {'status': 'SHORT', 'entry': ltp, 'row_id': len(st.session_state.trade_log)-1}

                    # EXIT SIGNAL
                    elif p['status'] == 'SHORT' and t_mode == "BUY EXIT":
                        msg = exit_tpl.replace("{{strike}}", str(s['val'])).replace("{{strategy}}", stag).replace("{{lots}}", str(user_lots))
                        
                        ok, status = fire_to_stoxxo(webhook_url, msg, live_execution)
                        alerts.append(f"EXIT {s['val']} [{status}]")
                        
                        pts = p['entry'] - ltp
                        pnl = pts * user_lots * lot_size
                        st.session_state.wallet += pnl
                        st.session_state.daily_pnl += pnl
                        save_data(st.session_state.wallet, st.session_state.daily_pnl, st.session_state.history_pnl)
                        
                        r_id = p['row_id']
                        st.session_state.trade_log[r_id]['EXIT'] = datetime.now().strftime('%H:%M')
                        st.session_state.trade_log[r_id]['PRICE'] = ltp
                        st.session_state.trade_log[r_id]['PTS'] = round(pts, 2)
                        st.session_state.trade_log[r_id]['P&L'] = round(pnl, 0)
                        st.session_state.positions[pos_key]['status'] = 'NONE'

                    rows.append({
                        "STRIKE": s['val'], "OPEN": round(day_o, 2), "LTP": round(ltp, 2), "CHANGE": round(change, 2),
                        "LEAD": lead, "REGIME": regime, "IND.REG": ind_reg, "T.MODE": t_mode, "T.TYPE": t_type
                    })
            except Exception as e:
                err = str(e)
                if "AUTH_EXPIRED" in err:
                    st.error("Fyers token expired/invalid (code -16). Run 1_login_test.py to refresh access_token.txt, then restart dashboard.")
                    return
                rows.append({"STRIKE": s['val'], "OPEN":0, "LTP":0, "CHANGE":0, "LEAD":"-", "REGIME":"-", "IND.REG":"-", "T.MODE":"ERR", "T.TYPE":"ERR"})
        
        if rows: monitor_slot.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        acc_slot.metric("Wallet", f"₹{round(st.session_state.wallet,0)}")
        acc_slot.metric("Day P&L", f"₹{round(st.session_state.daily_pnl,0)}")
        
        # P&L Display
        df_log = pd.DataFrame(st.session_state.trade_log) if st.session_state.trade_log else pd.DataFrame(columns=["STRIKE", "ENTRY", "EXIT", "LOTS", "PRICE", "PTS", "P&L"])
        hist_str = " | ".join([f"₹{x}" for x in st.session_state.history_pnl])
        summary_data = [
            {"STRIKE": "---", "ENTRY": "ACCOUNT", "EXIT": "SUMMARY", "LOTS": "---", "PRICE": "---", "PTS": "---", "P&L": "---"},
            {"STRIKE": "CAPITAL", "ENTRY": f"₹{round(st.session_state.wallet,0)}", "EXIT": "", "LOTS": "", "PRICE": "", "PTS": "", "P&L": ""},
            {"STRIKE": "DAY P&L", "ENTRY": f"₹{round(st.session_state.daily_pnl,0)}", "EXIT": "", "LOTS": "", "PRICE": "", "PTS": "", "P&L": ""},
            {"STRIKE": "FLOATING", "ENTRY": f"₹{round(floating_total,0)}", "EXIT": "", "LOTS": "", "PRICE": "", "PTS": "", "P&L": ""},
            {"STRIKE": "HIST (5D)", "ENTRY": hist_str, "EXIT": "", "LOTS": "", "PRICE": "", "PTS": "", "P&L": ""}
        ]
        df_final = pd.concat([df_log, pd.DataFrame(summary_data)], ignore_index=True)
        pnl_slot.dataframe(df_final, use_container_width=True, hide_index=True)

        # WEBHOOK LOGS DISPLAY
        if st.session_state.webhook_log:
            wh_df = pd.DataFrame(st.session_state.webhook_log)
            webhook_slot.dataframe(wh_df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            webhook_slot.info("No Signals Sent Yet")

        if alerts: 
            for a in alerts: alert_slot.text(f"{datetime.now().strftime('%H:%M:%S')} {a}")
        time.sleep(1)

if __name__ == "__main__":
    main()

