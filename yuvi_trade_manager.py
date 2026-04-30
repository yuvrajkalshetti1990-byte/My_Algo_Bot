# yuvi_trade_manager.py — Per-strike trade state machine for Yuvi MasterV6
# Mirrors the Pine Script short + long management blocks exactly.

from dataclasses import dataclass, field
from typing import Optional
import strategy_config as cfg


@dataclass
class StrikeState:
    """All mutable state for one strike (mirrors Pine's var declarations)."""
    label: str
    strike: int
    idx: int

    # Short state
    lsig: int = 0           # -1 = in short, 0 = flat
    ep: float = float("nan")
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    banked: float = 0.0
    trig: str = "—"
    is_long: bool = False
    sl_safe: bool = False
    ll: float = float("nan")    # lowest low since short entry
    cnt_short: int = 0

    # Long state
    lsig_long: int = 0      # 2 = in long, 0 = flat
    ep_long: float = float("nan")
    hh: float = float("nan")    # highest high since long entry
    cnt_long: int = 0


@dataclass
class DayState:
    """Resets at start of each trading day."""
    wallet: float = cfg.INIT_CAPITAL
    daily_pnl: float = 0.0
    history_pnl: list = field(default_factory=list)
    strikes: list = field(default_factory=list)

    def reset_day(self):
        """Called when a new trading day starts."""
        total_banked = sum(s.banked * cfg.LOT_SIZE *
                           (cfg.LOTS_LONG if s.is_long else cfg.LOTS_SHORT)
                           for s in self.strikes)
        # Roll yesterday P&L into history
        if len(self.history_pnl) >= 5:
            self.history_pnl.pop(0)
        self.history_pnl.append(total_banked)

        for s in self.strikes:
            s.lsig = 0
            s.lsig_long = 0
            s.ep = float("nan")
            s.ep_long = float("nan")
            s.banked = 0.0
            s.hh = float("nan")
            s.ll = float("nan")
            s.entry_time = None
            s.exit_time = None
            s.is_long = False
            s.sl_safe = False
            s.cnt_short = 0
            s.cnt_long = 0

        self.daily_pnl = 0.0


def _safe(val):
    import math
    return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else val


class TradeManager:
    """
    Processes one confirmed bar per strike and returns a list of trade events.
    Usage:
        tm = TradeManager()
        events = tm.process_bar(bar_data_dict)
    """

    def __init__(self):
        self.strikes = [
            StrikeState(label=s["label"], strike=s["strike"], idx=i)
            for i, s in enumerate(cfg.STRIKES)
        ]
        self.day_state = DayState(strikes=self.strikes)
        self._last_date = None

    # ─── public ───────────────────────────────────────────────────────────────

    def on_new_day(self):
        self.day_state.reset_day()

    def process_bar(self, bars: list[dict], bar_dt, is_hard_exit_short: bool,
                    is_hard_exit_long: bool, in_session: bool,
                    can_long_start: bool) -> list[dict]:
        """
        bars: list of dicts, one per strike, with keys:
            open, high, low, close, ema, vwma, vwap,
            buy_cond, sell_cond, trig_str, panic_long,
            ttype, regime, ready
        Returns list of event dicts for UI / webhook.
        """
        events = []

        # Day boundary
        bar_date = bar_dt.date() if hasattr(bar_dt, "date") else None
        if bar_date and bar_date != self._last_date:
            if self._last_date is not None:
                self.on_new_day()
            self._last_date = bar_date

        for i, s in enumerate(self.strikes):
            if not cfg.STRIKES[i]["enabled"]:
                continue
            bar = bars[i]
            if bar is None:
                continue

            o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
            ema, vwma = bar["ema"], bar["vwma"]
            buy_cond, sell_cond = bar["buy_cond"], bar["sell_cond"]
            trig_str = bar["trig_str"]
            panic_long = bar["panic_long"]
            ts = bar_dt.strftime("%H:%M") if hasattr(bar_dt, "strftime") else str(bar_dt)[11:16]

            evs = []
            evs += self._process_short(s, o, h, l, c, ema, vwma,
                                        buy_cond, sell_cond, trig_str,
                                        is_hard_exit_short, ts)
            evs += self._process_long(s, o, h, l, c, ema, vwma,
                                       bar["vwap"], bar["ttype"], bar["regime"],
                                       panic_long, is_hard_exit_long,
                                       in_session, can_long_start, ts)
            events.extend(evs)

        # Recompute daily P&L
        self.day_state.daily_pnl = self._calc_day_pnl()
        return events

    # ─── internal ─────────────────────────────────────────────────────────────

    def _process_short(self, s: StrikeState, o, h, l, c, ema, vwma,
                        buy_cond, sell_cond, trig_str,
                        is_hard_exit: bool, ts: str) -> list[dict]:
        events = []
        allow_short = (
            (cfg.MAX_SHORT_TRADES == 0 or s.cnt_short < cfg.MAX_SHORT_TRADES)
            and s.lsig_long == 0
        )
        scope_ok = (not cfg.SHORT_RESTRICT_EN) or cfg.SHORT_SCOPE[s.idx]

        if s.lsig == -1:
            # ── In a short position ──
            if float("nan") != float("nan"):   # always true, but keep pattern
                pass
            s.ll = min(_safe(s.ll) if not _is_nan(s.ll) else l, l)

            tgt_hit   = cfg.FIXED_TARGET > 0 and l <= (s.ep - cfg.FIXED_TARGET)
            tsl_hit   = (cfg.USE_TSL and
                         (s.ep - s.ll) >= cfg.TSL_TRIGGER and
                         h >= (s.ll + cfg.TSL_DIST))
            smart_guard = (cfg.USE_TSL and
                           (s.ep - s.ll) >= cfg.TSL_TRIGGER and
                           c > ema and c > vwma)

            if is_hard_exit:
                pnl = s.ep - _safe(c)
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", c, ts, reason="TIME EXIT"))
                self._close_short(s, ts)

            elif tgt_hit:
                pnl = cfg.FIXED_TARGET
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", s.ep - cfg.FIXED_TARGET, ts, reason="TGT HIT"))
                self._close_short(s, ts)

            elif smart_guard:
                pnl = s.ep - _safe(c)
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", c, ts, reason="SMART EXIT"))
                self._close_short(s, ts)

            elif tsl_hit:
                exit_price = s.ll + cfg.TSL_DIST
                pnl = s.ep - exit_price
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", exit_price, ts, reason="TSL HIT"))
                self._close_short(s, ts)

            elif cfg.DISABLE_SL_EN and (s.ep - l) >= cfg.DISABLE_SL_PTS:
                s.sl_safe = True

            elif cfg.FIXED_SL > 0 and h >= (s.ep + cfg.FIXED_SL) and not s.sl_safe:
                pnl = -cfg.FIXED_SL
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", s.ep + cfg.FIXED_SL, ts, reason="SL HIT"))
                self._close_short(s, ts)

            elif buy_cond:
                pnl = s.ep - _safe(c)
                s.banked += pnl
                events.append(self._evt(s, "SHORT_EXIT", c, ts, reason="BUY SIGNAL"))
                self._close_short(s, ts)

        elif sell_cond and s.lsig != -1 and allow_short and scope_ok and cfg.SHORT_ENABLED:
            # ── Enter short ──
            s.lsig = -1
            s.ep = c
            s.entry_time = ts
            s.trig = trig_str
            s.is_long = False
            s.sl_safe = False
            s.ll = float("nan")
            s.cnt_short += 1
            events.append(self._evt(s, "SHORT_ENTRY", c, ts, reason=trig_str))

        return events

    def _process_long(self, s: StrikeState, o, h, l, c, ema, vwma, vwap,
                       ttype, regime, panic_long,
                       is_hard_exit: bool, in_session: bool, can_long_start: bool,
                       ts: str) -> list[dict]:
        events = []
        allow_long = (
            (cfg.MAX_LONG_TRADES == 0 or s.cnt_long < cfg.MAX_LONG_TRADES)
            and s.lsig == 0
        )
        scope_ok = (not cfg.LONG_RESTRICT_EN) or cfg.LONG_SCOPE[s.idx]

        if s.lsig_long == 2:
            if not _is_nan(s.hh):
                s.hh = max(s.hh, h)
            else:
                s.hh = h

            cond_hard = is_hard_exit
            cond_tgt  = cfg.LONG_TARGET > 0 and h >= s.ep_long + cfg.LONG_TARGET
            cond_sl   = cfg.LONG_FIXED_SL > 0 and l <= s.ep_long - cfg.LONG_FIXED_SL
            cond_tsl  = (cfg.USE_LONG_TSL and
                         (s.hh - s.ep_long) >= cfg.TSL_LONG_TRIGGER and
                         l <= s.hh - cfg.TSL_LONG_DIST)
            cond_str  = c < ema and c < vwma and c < vwap
            cond_panic= panic_long

            if cond_hard or cond_tgt or cond_sl or cond_tsl or cond_str or cond_panic:
                if cond_tgt:
                    pnl = cfg.LONG_TARGET
                    reason = "TGT HIT"
                elif cond_sl:
                    pnl = -cfg.LONG_FIXED_SL
                    reason = "SL HIT"
                elif cond_tsl:
                    pnl = (s.hh - cfg.TSL_LONG_DIST) - s.ep_long
                    reason = "TSL HIT"
                elif cond_str:
                    pnl = _safe(c) - s.ep_long
                    reason = "STRUCT BRK"
                elif cond_hard:
                    pnl = _safe(c) - s.ep_long
                    reason = "TIME EXIT"
                else:
                    pnl = _safe(c) - s.ep_long
                    reason = "PANIC EXIT"

                s.banked += pnl
                events.append(self._evt(s, "LONG_EXIT", c, ts, reason=reason))
                s.lsig_long = 0
                s.exit_time = ts

        elif (s.lsig_long == 0 and allow_long and in_session and can_long_start
              and scope_ok and cfg.LONG_ENABLED):
            sig_val = ttype in ("Buy CE", "Buy PE") and (
                (ttype == "Buy PE" and regime == "SHORT COV") or ttype == "Buy CE"
            )
            str_val = c > ema and c > vwma and c > vwap
            final_entry = (sig_val and str_val) if cfg.USE_STRICT_LONG else sig_val

            if final_entry:
                s.lsig_long = 2
                s.ep_long = c
                s.entry_time = ts
                s.trig = "BUY-V"
                s.hh = c
                s.is_long = True
                s.cnt_long += 1
                events.append(self._evt(s, "LONG_ENTRY", c, ts, reason="BUY-V"))

        return events

    def _close_short(self, s: StrikeState, ts: str):
        s.lsig = 0
        s.exit_time = ts
        s.sl_safe = False

    def _evt(self, s: StrikeState, event_type: str, price, ts: str, reason: str = "") -> dict:
        lots = cfg.LOTS_LONG if s.is_long else cfg.LOTS_SHORT
        return {
            "type":   event_type,
            "label":  s.label,
            "strike": s.strike,
            "price":  price,
            "lots":   lots,
            "reason": reason,
            "ts":     ts,
            "banked": s.banked,
            "pnl_pts": s.banked,
            "pnl_rs":  s.banked * cfg.LOT_SIZE * lots,
        }

    def _calc_day_pnl(self) -> float:
        total = 0.0
        for s in self.strikes:
            lots = cfg.LOTS_LONG if s.is_long else cfg.LOTS_SHORT
            pts = s.banked
            if s.lsig == -1:
                pts += (s.ep - _safe(s.ep))   # floating — handled in dashboard
            elif s.lsig_long == 2:
                pts += (_safe(s.ep_long) - s.ep_long)
            total += pts * cfg.LOT_SIZE * lots
        return total

    def get_summary(self) -> list[dict]:
        """Returns per-strike summary for dashboard table."""
        rows = []
        for s in self.strikes:
            lots = cfg.LOTS_LONG if s.is_long else cfg.LOTS_SHORT
            # last_ep: always reflects the last trade's entry price (even after close)
            last_ep = s.ep_long if s.is_long else s.ep
            rows.append({
                "label":       s.label,
                "strike":      s.strike,
                "entry_time":  s.entry_time or "—",
                "exit_time":   s.exit_time  or "—",
                "lots":        lots,
                "is_long":     s.is_long,
                "ep":          s.ep if s.lsig == -1 else s.ep_long if s.lsig_long == 2 else float("nan"),
                "last_ep":     last_ep,
                "banked_pts":  s.banked,
                "banked_rs":   s.banked * cfg.LOT_SIZE * lots,
                "trig":        s.trig,
                "cnt_short":   s.cnt_short,
                "cnt_long":    s.cnt_long,
                "in_short":    s.lsig == -1,
                "in_long":     s.lsig_long == 2,
            })
        return rows


def _is_nan(v) -> bool:
    import math
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return True
