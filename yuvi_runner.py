#!/usr/bin/env python3
# yuvi_runner.py — Headless (non-UI) live runner for Yuvi MasterV6
# Polls Fyers every N seconds during market hours and processes signals.
# Use this when you don't need the Streamlit dashboard.
#
# Usage: python yuvi_runner.py

import time
import math
import os
import signal
import sys
from datetime import datetime

import strategy_config as cfg
from yuvi_data import get_fyers_client, fetch_all_strikes
from yuvi_indicators import (
    add_indicators, get_mode, get_ind_regime, calc_regime, calc_ttype, proc_signal
)
from yuvi_trade_manager import TradeManager

POLL_INTERVAL_SEC = 30   # how often to refresh (seconds)
_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n[RUNNER] Graceful shutdown…")
    _running = False


signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def _nan(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def is_in_session(dt: datetime) -> bool:
    t = dt.hour * 60 + dt.minute
    return 9 * 60 + 15 <= t <= 14 * 60 + 30


def is_hard_exit_short(dt: datetime) -> bool:
    t = dt.hour * 60 + dt.minute
    return t >= cfg.HARD_EXIT_HOUR_SHORT * 60 + cfg.HARD_EXIT_MIN_SHORT


def is_hard_exit_long(dt: datetime) -> bool:
    t = dt.hour * 60 + dt.minute
    return t >= cfg.HARD_EXIT_HOUR_LONG * 60 + cfg.HARD_EXIT_MIN_LONG


def can_long_start(dt: datetime) -> bool:
    parts = cfg.LONG_START_TIME.split(":")
    lh, lm = int(parts[0]), int(parts[1])
    return dt.hour * 60 + dt.minute >= lh * 60 + lm


def run_once(fyers, tm: TradeManager):
    now = datetime.now()
    if not is_in_session(now):
        print(f"[{now:%H:%M:%S}] Outside session — skipping.")
        return

    all_data = fetch_all_strikes(fyers)
    bar_inputs = []

    for i, (s_cfg, data) in enumerate(zip(cfg.STRIKES, all_data)):
        if data is None or not s_cfg["enabled"]:
            bar_inputs.append(None)
            continue

        df = add_indicators(data["combined"].copy())
        if len(df) < 2:
            bar_inputs.append(None)
            continue

        row   = df.iloc[-1]
        prev  = df.iloc[-2]
        ready = not _nan(row["close"]) and not _nan(row.get("daily_open"))

        rsi  = row.get("rsi",      float("nan"))
        dp   = row.get("plus_di",  float("nan"))
        dm   = row.get("minus_di", float("nan"))
        adx  = row.get("adx",      float("nan"))
        roc  = row.get("roc",      float("nan"))
        chop = row.get("chop",     float("nan"))

        mode   = get_mode(rsi, dp, dm, adx, ready)
        regime = calc_regime(
            row["close"], row.get("daily_open"),
            row["ce_close"], row.get("ce_daily_open"),
            row["pe_close"], row.get("pe_daily_open"),
        )
        ttype = calc_ttype(
            row["close"], row.get("daily_open"),
            row["ce_close"], row.get("ce_daily_open"),
            row["pe_close"], row.get("pe_daily_open"),
            mode, chop if not _nan(chop) else 0.0
        )

        # Auto strict mode
        use_strict = True if cfg.CALC_MODE in ("Strict", "Auto") else False

        buy_cond, sell_cond, trig_str, panic_long = proc_signal(
            dict(row) | {"ready": ready},
            dict(prev),
            df.tail(max(cfg.CROSSOVER_WINDOW + 2, 5)),
            i, ttype, regime,
            is_in_session(now), use_strict
        )

        bar_inputs.append({
            "open": row["open"], "high": row.get("high", row["close"]),
            "low": row.get("low", row["close"]), "close": row["close"],
            "ema": row.get("ema"), "vwma": row.get("vwma"), "vwap": row.get("vwap"),
            "buy_cond": buy_cond, "sell_cond": sell_cond,
            "trig_str": trig_str, "panic_long": panic_long,
            "ttype": ttype, "regime": regime, "ready": ready,
        })

        print(f"  [{s_cfg['label']}] {s_cfg['strike']}  LTP={row['close']:.2f}"
              f"  Mode={mode}  TType={ttype}  Regime={regime}"
              f"  BUY={buy_cond}  SELL={sell_cond}  Trig={trig_str}")

    events = tm.process_bar(
        bar_inputs, now,
        is_hard_exit_short(now), is_hard_exit_long(now),
        is_in_session(now), can_long_start(now)
    )

    for ev in events:
        sign = "🔴" if "SHORT" in ev["type"] else "🟢"
        print(f"  {sign} EVENT: {ev['type']:15s} {ev['label']:5s} "
              f"@ {ev['price']:.2f}  lots={ev['lots']}  "
              f"P&L pts={ev['banked_pts']:+.2f}  ₹{ev['pnl_rs']:+,.0f}  ({ev['reason']})")


def main():
    print("=" * 60)
    print("  Yuvi MasterV6 — Live Runner")
    print(f"  Index: {cfg.INDEX_NAME}  |  Expiry: {cfg.EXP_DD}/{cfg.EXP_MM}/{cfg.EXP_YY}")
    print(f"  Poll interval: {POLL_INTERVAL_SEC}s")
    print("  Ctrl+C to stop")
    print("=" * 60)

    fyers = get_fyers_client()
    tm    = TradeManager()

    while _running:
        now = datetime.now()
        print(f"\n[{now:%H:%M:%S}] ── Tick ──────────────────────────")
        try:
            run_once(fyers, tm)
        except Exception as exc:
            print(f"  [ERROR] {exc}")

        # Summary
        summary = tm.get_summary()
        day_pnl = sum(r["banked_rs"] for r in summary)
        equity  = cfg.INIT_CAPITAL + sum(tm.day_state.history_pnl) + day_pnl
        print(f"  Day P&L: ₹{day_pnl:+,.0f}   Equity: ₹{equity:,.0f}")

        # Wait for next poll
        for _ in range(POLL_INTERVAL_SEC):
            if not _running:
                break
            time.sleep(1)

    print("[RUNNER] Stopped.")


if __name__ == "__main__":
    main()
