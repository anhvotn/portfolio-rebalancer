"""Portfolio rebalancing assistant: deterministic portfolio tools + an OpenAI tool-calling agent.

The numbers (drift, trades, costs) are always computed in Python from portfolio.json;
the language model only decides which tool to call and explains the results.
"""
import json
import os
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import openai

CASH_KEY = "CASH"
NY = ZoneInfo("America/New_York")


# --------------------------------------------------------------------------
# Portfolio data
# --------------------------------------------------------------------------
class PortfolioDataExtension:
    def __init__(self, portfolio_db_path: str = "portfolio.json"):
        self.db_path = portfolio_db_path

    def _load(self) -> Dict[str, Any]:
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_portfolio_holdings(self) -> Dict[str, Any]:
        try:
            data = self._load()
        except FileNotFoundError:
            return {"status": "error", "message": f"Portfolio file '{self.db_path}' not found"}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Portfolio file is not valid JSON: {e}"}
        holdings = data.get("holdings", [])
        cash = float(data.get("cash", 0))
        invested = sum(h["shares"] * h["current_price"] for h in holdings)
        return {"status": "success", "holdings": holdings, "cash": cash,
                "invested_value": round(invested, 2), "total_value": round(invested + cash, 2),
                "currency": data.get("currency", "USD")}

    def get_target_allocation(self) -> Dict[str, float]:
        """Target weights in % of TOTAL value. Optional key 'CASH'; if absent, the
        remainder (100 - sum of targets) is treated as the cash target."""
        try:
            targets = {k: float(v) for k, v in self._load().get("target_allocation", {}).items()}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if CASH_KEY not in targets:
            targets[CASH_KEY] = round(max(0.0, 100.0 - sum(targets.values())), 4)
        return targets

    def calculate_allocation_drift(self) -> Dict[str, Any]:
        h = self.get_portfolio_holdings()
        if h["status"] != "success":
            return h
        targets = self.get_target_allocation()
        total = h["total_value"]
        if total <= 0:
            return {"status": "error", "message": "Portfolio total value is zero"}
        values = {x["symbol"]: x["shares"] * x["current_price"] for x in h["holdings"]}
        values[CASH_KEY] = h["cash"]
        drift = {}
        for sym in sorted(set(values) | set(targets)):
            cur_pct = values.get(sym, 0.0) / total * 100
            tgt = targets.get(sym, 0.0)
            drift[sym] = {"current_allocation": round(cur_pct, 2), "target_allocation": round(tgt, 2),
                          "drift": round(cur_pct - tgt, 2),
                          "drift_value": round((cur_pct - tgt) / 100 * total, 2)}
        warn = None
        s = sum(v for k, v in targets.items() if k != CASH_KEY) + targets.get(CASH_KEY, 0)
        if abs(s - 100) > 0.01:
            warn = f"Targets sum to {s:.2f}%, not 100%"
        return {"status": "success", "total_value": total, "drift": drift, "warning": warn}


# --------------------------------------------------------------------------
# Market data (prices from portfolio.json; mock fallback for unknown symbols)
# --------------------------------------------------------------------------
def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    return d - timedelta(days=1) if d.weekday() == 5 else (d + timedelta(days=1) if d.weekday() == 6 else d)


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def nyse_holidays(year: int) -> set:
    """Regular NYSE full-day holidays (rule-based; ad-hoc closures are not included)."""
    hol = {_observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
           _easter(year) - timedelta(days=2), _last_weekday(year, 5, 0),
           _observed(date(year, 7, 4)), _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 11, 3, 4),
           _observed(date(year, 12, 25))}
    if year >= 2022:
        hol.add(_observed(date(year, 6, 19)))
    return hol


class MarketDataExtension:
    MOCK_PRICES = {"AAPL": 178.50, "GOOGL": 142.30, "MSFT": 378.90, "VTI": 245.60, "BND": 72.30}

    def __init__(self, portfolio: Optional[PortfolioDataExtension] = None):
        self.portfolio = portfolio

    def get_current_price(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper()
        if self.portfolio:
            h = self.portfolio.get_portfolio_holdings()
            for x in h.get("holdings", []):
                if x["symbol"].upper() == symbol:
                    return {"symbol": symbol, "price": x["current_price"], "source": "portfolio.json"}
        if symbol in self.MOCK_PRICES:
            return {"symbol": symbol, "price": self.MOCK_PRICES[symbol], "source": "mock (not a live quote)"}
        return {"symbol": symbol, "price": None, "source": "unknown symbol - add it to portfolio.json"}

    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Any]:
        return {s.upper(): self.get_current_price(s) for s in symbols}

    def is_market_open(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """US equity market (NYSE) regular session, 09:30-16:00 New York time."""
        now = (now or datetime.now(tz=NY)).astimezone(NY)
        today = now.date()

        def trading_day(d):
            return d.weekday() < 5 and d not in nyse_holidays(d.year)

        is_open = trading_day(today) and time(9, 30) <= now.time() < time(16, 0)
        d = today if (trading_day(today) and now.time() < time(9, 30)) else today + timedelta(days=1)
        while not trading_day(d):
            d += timedelta(days=1)
        return {"is_open": is_open, "new_york_time": now.strftime("%Y-%m-%d %H:%M %Z"),
                "next_open": None if is_open else f"{d.isoformat()} 09:30 ET",
                "note": "Regular session only; early closes and ad-hoc closures not modelled."}


# --------------------------------------------------------------------------
# Rebalancing engine (reads the portfolio itself - no arguments from the model)
# --------------------------------------------------------------------------
class RebalancingEngineExtension:
    def __init__(self, portfolio: PortfolioDataExtension, threshold_pct: float = 5.0,
                 min_trade_amount: float = 100.0, allow_fractional: bool = False):
        self.portfolio = portfolio
        self.threshold_pct = threshold_pct
        self.min_trade_amount = min_trade_amount
        self.allow_fractional = allow_fractional

    def generate_rebalance_recommendations(self) -> Dict[str, Any]:
        h = self.portfolio.get_portfolio_holdings()
        if h["status"] != "success":
            return h
        targets = self.portfolio.get_target_allocation()
        total = h["total_value"]
        prices = {x["symbol"]: x["current_price"] for x in h["holdings"]}
        shares = {x["symbol"]: x["shares"] for x in h["holdings"]}
        missing = [s for s in targets if s != CASH_KEY and s not in prices]
        recs = []
        for sym in sorted(set(prices) | {s for s in targets if s != CASH_KEY}):
            if sym not in prices:
                continue  # target for a symbol without a price: reported in 'missing_prices'
            price = prices[sym]
            cur_val = shares.get(sym, 0) * price
            cur_pct = cur_val / total * 100
            tgt_pct = targets.get(sym, 0.0)
            drift = cur_pct - tgt_pct
            if abs(drift) <= self.threshold_pct:
                continue
            diff_sh = (tgt_pct / 100 * total - cur_val) / price
            if not self.allow_fractional:
                diff_sh = int(diff_sh)  # round toward zero: never overshoot
            value = abs(diff_sh * price)
            if diff_sh == 0 or value < self.min_trade_amount:
                continue
            recs.append({"symbol": sym, "action": "BUY" if diff_sh > 0 else "SELL",
                         "shares": round(abs(diff_sh), 4), "estimated_value": round(value, 2),
                         "current_allocation": round(cur_pct, 2), "target_allocation": tgt_pct,
                         "drift_pct": round(drift, 2), "priority": self._priority(abs(drift))})
        # cash check: sells fund buys; scale buys down if cash would go negative
        sells = sum(r["estimated_value"] for r in recs if r["action"] == "SELL")
        buys = sum(r["estimated_value"] for r in recs if r["action"] == "BUY")
        available = h["cash"] + sells
        note = None
        if buys > available and buys > 0:
            f = available / buys
            for r in recs:
                if r["action"] == "BUY":
                    sh = r["shares"] * f
                    sh = sh if self.allow_fractional else int(sh)
                    r["shares"] = round(sh, 4)
                    r["estimated_value"] = round(sh * prices[r["symbol"]], 2)
            recs = [r for r in recs if r["shares"] > 0]
            note = f"Buys scaled to {f:.0%} to stay within available cash"
            buys = sum(r["estimated_value"] for r in recs if r["action"] == "BUY")
        recs.sort(key=lambda r: (r["priority"], abs(r["drift_pct"])), reverse=True)
        return {"status": "success", "threshold_pct": self.threshold_pct, "recommendations": recs,
                "cash_before": h["cash"], "cash_after_estimate": round(h["cash"] + sells - buys, 2),
                "missing_prices": missing, "note": note}

    def calculate_transaction_costs(self, commission_per_trade: float = 0.0,
                                    spread_bps: float = 2.0) -> Dict[str, Any]:
        r = self.generate_rebalance_recommendations()
        if r.get("status") != "success":
            return r
        recs = r["recommendations"]
        commission = len(recs) * commission_per_trade
        spread = sum(x["estimated_value"] * spread_bps / 10000 for x in recs)
        return {"num_trades": len(recs), "commission_costs": round(commission, 2),
                "spread_costs": round(spread, 2), "total_estimated_costs": round(commission + spread, 2),
                "assumptions": {"commission_per_trade": commission_per_trade, "spread_bps": spread_bps}}

    @staticmethod
    def _priority(d: float) -> int:
        return 5 if d > 15 else 4 if d > 10 else 3 if d > 7 else 2 if d > 5 else 1


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------
NO_ARGS = {"type": "object", "properties": {}, "required": []}


class PortfolioRebalancerAgent:
    MAX_TOOL_ROUNDS = 8

    def __init__(self, api_key: str, portfolio_path: str = "portfolio.json", client=None):
        self.client = client or openai.OpenAI(api_key=api_key)
        self.model = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.portfolio_ext = PortfolioDataExtension(portfolio_path)
        self.market_ext = MarketDataExtension(self.portfolio_ext)
        self.rebalancing_ext = RebalancingEngineExtension(
            self.portfolio_ext,
            threshold_pct=float(os.getenv("REBALANCE_THRESHOLD_PCT", 5)),
            min_trade_amount=float(os.getenv("MIN_TRADE_AMOUNT", 100)),
            allow_fractional=os.getenv("ALLOW_FRACTIONAL_SHARES", "false").lower() == "true")
        self.functions = {
            "get_portfolio_holdings": self.portfolio_ext.get_portfolio_holdings,
            "get_target_allocation": self.portfolio_ext.get_target_allocation,
            "calculate_allocation_drift": self.portfolio_ext.calculate_allocation_drift,
            "get_current_price": self.market_ext.get_current_price,
            "get_multiple_prices": self.market_ext.get_multiple_prices,
            "is_market_open": self.market_ext.is_market_open,
            "generate_rebalance_recommendations": self.rebalancing_ext.generate_rebalance_recommendations,
            "calculate_transaction_costs": self.rebalancing_ext.calculate_transaction_costs,
        }
        self.tools = [
            self._tool("get_portfolio_holdings", "Current holdings, cash and total value from portfolio.json"),
            self._tool("get_target_allocation", "Target weights in % of total value (CASH = cash target)"),
            self._tool("calculate_allocation_drift", "Current vs target weight for every holding, target and cash"),
            self._tool("get_current_price", "Price of one symbol (from portfolio.json; not a live quote)",
                       {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}),
            self._tool("get_multiple_prices", "Prices of several symbols",
                       {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}}},
                        "required": ["symbols"]}),
            self._tool("is_market_open", "Whether the US stock market (NYSE) is open now, in New York time"),
            self._tool("generate_rebalance_recommendations",
                       "Buy/sell trades that bring drifted positions back to target (computed from portfolio.json)"),
            self._tool("calculate_transaction_costs", "Estimated costs of the recommended trades",
                       {"type": "object", "properties": {
                           "commission_per_trade": {"type": "number", "description": "fee per trade, default 0"},
                           "spread_bps": {"type": "number", "description": "half-spread in basis points, default 2"}},
                        "required": []}),
        ]
        self.system_prompt = (
            "You are a portfolio rebalancing assistant for educational use. Always use the tools to get "
            "holdings, drift, trades and costs - never invent numbers. Prices come from portfolio.json and "
            "are not live quotes; say so when relevant. Explain your reasoning clearly in markdown. "
            "You do not give personalised investment, tax or legal advice; remind the user to consider "
            "taxes and to consult a qualified adviser before trading.")

    @staticmethod
    def _tool(name, desc, params=None):
        return {"type": "function", "function": {"name": name, "description": desc, "parameters": params or NO_ARGS}}

    def chat(self, user_message: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[str, List[Dict], List[Dict]]:
        history = list(conversation_history or [])
        history.append({"role": "user", "content": user_message})
        calls_made = []
        for _ in range(self.MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "system", "content": self.system_prompt}] + history,
                tools=self.tools, tool_choice="auto")
            msg = response.choices[0].message
            if not msg.tool_calls:
                answer = msg.content or ""
                history.append({"role": "assistant", "content": answer})
                return answer, history, calls_made
            # store plain dicts (JSON-serialisable), not SDK objects
            history.append({"role": "assistant", "content": msg.content,
                            "tool_calls": [{"id": tc.id, "type": "function",
                                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                           for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls_made.append({"name": tc.function.name, "arguments": args})
                result = self._execute_function(tc.function.name, args)
                history.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
        answer = "Sorry - I could not finish that request (too many tool steps). Please try a simpler question."
        history.append({"role": "assistant", "content": answer})
        return answer, history, calls_made

    def _execute_function(self, name: str, arguments: Dict[str, Any]) -> Any:
        fn = self.functions.get(name)
        if fn is None:
            return {"error": f"Function {name} not found"}
        try:
            return fn(**arguments)
        except Exception as e:  # report to the model instead of crashing the request
            return {"error": f"{type(e).__name__}: {e}"}
