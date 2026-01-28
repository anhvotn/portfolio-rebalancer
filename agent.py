import openai
import json
import os
from typing import List, Dict, Any
from datetime import datetime, time

class PortfolioDataExtension:
    def __init__(self, portfolio_db_path: str = "portfolio.json"):
        self.db_path = portfolio_db_path
    
    def get_portfolio_holdings(self) -> Dict[str, Any]:
        try:
            with open(self.db_path, 'r') as f:
                portfolio_data = json.load(f)
            total_value = self._calculate_total_value(portfolio_data)
            return {
                "status": "success",
                "holdings": portfolio_data.get("holdings", []),
                "cash": portfolio_data.get("cash", 0),
                "total_value": total_value
            }
        except FileNotFoundError:
            return {"status": "error", "message": "Portfolio data not found"}
    
    def get_target_allocation(self) -> Dict[str, float]:
        try:
            with open(self.db_path, 'r') as f:
                portfolio_data = json.load(f)
            return portfolio_data.get("target_allocation", {})
        except FileNotFoundError:
            return {}
    
    def calculate_allocation_drift(self) -> Dict[str, Any]:
        holdings = self.get_portfolio_holdings()
        targets = self.get_target_allocation()
        if holdings["status"] != "success":
            return holdings
        total_value = holdings["total_value"]
        drift = {}
        for holding in holdings["holdings"]:
            symbol = holding["symbol"]
            current_value = holding["shares"] * holding["current_price"]
            current_pct = (current_value / total_value) * 100
            target_pct = targets.get(symbol, 0)
            drift[symbol] = {
                "current_allocation": round(current_pct, 2),
                "target_allocation": target_pct,
                "drift": round(current_pct - target_pct, 2),
                "drift_dollars": round((current_pct - target_pct) / 100 * total_value, 2)
            }
        return drift
    
    def _calculate_total_value(self, portfolio_data: Dict) -> float:
        holdings_value = sum(h["shares"] * h["current_price"] for h in portfolio_data.get("holdings", []))
        return holdings_value + portfolio_data.get("cash", 0)

class MarketDataExtension:
    def get_current_price(self, symbol: str) -> Dict[str, Any]:
        mock_prices = {"AAPL": 178.50, "GOOGL": 142.30, "MSFT": 378.90, "VTI": 245.60, "BND": 72.30}
        return {"symbol": symbol, "price": mock_prices.get(symbol, 100.0), "timestamp": datetime.now().isoformat(), "source": "mock_data"}
    
    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, float]:
        return {symbol: self.get_current_price(symbol)["price"] for symbol in symbols}
    
    def is_market_open(self) -> Dict[str, Any]:
        now = datetime.now()
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        is_weekday = now.weekday() < 5
        is_trading_hours = market_open <= current_time <= market_close
        return {
            "is_open": is_weekday and is_trading_hours,
            "next_open": "Next business day 9:30 AM ET" if not is_weekday else "Today 9:30 AM ET",
            "current_time": now.isoformat()
        }

class RebalancingEngineExtension:
    def __init__(self, threshold_pct: float = 5.0, min_trade_amount: float = 100.0):
        self.threshold_pct = threshold_pct
        self.min_trade_amount = min_trade_amount
    
    def generate_rebalance_recommendations(self, current_holdings: Dict[str, Any], target_allocation: Dict[str, float], current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        recommendations = []
        total_value = current_holdings["total_value"]
        for holding in current_holdings["holdings"]:
            symbol = holding["symbol"]
            current_shares = holding["shares"]
            current_price = current_prices.get(symbol, holding["current_price"])
            current_value = current_shares * current_price
            current_pct = (current_value / total_value) * 100
            target_pct = target_allocation.get(symbol, 0)
            drift_pct = current_pct - target_pct
            if abs(drift_pct) > self.threshold_pct:
                target_value = (target_pct / 100) * total_value
                target_shares = target_value / current_price
                shares_diff = target_shares - current_shares
                trade_value = abs(shares_diff * current_price)
                if trade_value > self.min_trade_amount:
                    recommendations.append({
                        "symbol": symbol,
                        "action": "BUY" if shares_diff > 0 else "SELL",
                        "shares": round(abs(shares_diff), 2),
                        "estimated_value": round(trade_value, 2),
                        "current_allocation": round(current_pct, 2),
                        "target_allocation": target_pct,
                        "drift_pct": round(drift_pct, 2),
                        "priority": self._calculate_priority(abs(drift_pct))
                    })
        recommendations.sort(key=lambda x: x["priority"], reverse=True)
        return recommendations
    
    def calculate_transaction_costs(self, recommendations: List[Dict[str, Any]], commission_per_trade: float = 0.0, spread_bps: float = 2.0) -> Dict[str, Any]:
        num_trades = len(recommendations)
        total_commission = num_trades * commission_per_trade
        spread_costs = sum(rec["estimated_value"] * (spread_bps / 10000) for rec in recommendations)
        total_costs = total_commission + spread_costs
        return {
            "num_trades": num_trades,
            "commission_costs": round(total_commission, 2),
            "spread_costs": round(spread_costs, 2),
            "total_estimated_costs": round(total_costs, 2)
        }
    
    def _calculate_priority(self, drift_pct: float) -> int:
        if drift_pct > 15: return 5
        elif drift_pct > 10: return 4
        elif drift_pct > 7: return 3
        elif drift_pct > 5: return 2
        else: return 1

class PortfolioRebalancerAgent:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = os.getenv("MODEL_NAME", "gpt-4-turbo-preview")
        self.portfolio_ext = PortfolioDataExtension()
        self.market_ext = MarketDataExtension()
        self.rebalancing_ext = RebalancingEngineExtension()
        self.functions = self._build_function_registry()
        self.tools = self._build_tools_schema()
        self.system_prompt = """You are an expert financial advisor specializing in portfolio management.
Your role is to help users rebalance their investment portfolios to maintain target allocations while considering transaction costs, tax implications, and market conditions.

Always:
1. Check current portfolio holdings and allocation
2. Compare against target allocation
3. Calculate drift and prioritize rebalancing needs
4. Consider transaction costs
5. Provide clear, actionable recommendations with reasoning
6. Use markdown formatting for better readability

Be conversational, clear, and always explain your reasoning."""
    
    def _build_function_registry(self) -> Dict[str, Any]:
        return {
            "get_portfolio_holdings": self.portfolio_ext.get_portfolio_holdings,
            "get_target_allocation": self.portfolio_ext.get_target_allocation,
            "calculate_allocation_drift": self.portfolio_ext.calculate_allocation_drift,
            "get_current_price": self.market_ext.get_current_price,
            "get_multiple_prices": self.market_ext.get_multiple_prices,
            "is_market_open": self.market_ext.is_market_open,
            "generate_rebalance_recommendations": self.rebalancing_ext.generate_rebalance_recommendations,
            "calculate_transaction_costs": self.rebalancing_ext.calculate_transaction_costs,
        }
    
    def _build_tools_schema(self) -> List[Dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": "get_portfolio_holdings", "description": "Get current portfolio holdings", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "get_target_allocation", "description": "Get target allocation percentages", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "calculate_allocation_drift", "description": "Calculate allocation drift", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "get_current_price", "description": "Get price for symbol", "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}}},
            {"type": "function", "function": {"name": "get_multiple_prices", "description": "Get multiple prices", "parameters": {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}}}, "required": ["symbols"]}}},
            {"type": "function", "function": {"name": "is_market_open", "description": "Check if market is open", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "generate_rebalance_recommendations", "description": "Generate rebalancing recommendations", "parameters": {"type": "object", "properties": {"current_holdings": {"type": "object"}, "target_allocation": {"type": "object"}, "current_prices": {"type": "object"}}, "required": ["current_holdings", "target_allocation", "current_prices"]}}},
            {"type": "function", "function": {"name": "calculate_transaction_costs", "description": "Calculate transaction costs", "parameters": {"type": "object", "properties": {"recommendations": {"type": "array"}}, "required": ["recommendations"]}}}
        ]
    
    def chat(self, user_message: str, conversation_history: List[Dict] = None) -> tuple:
        if conversation_history is None:
            conversation_history = []
        conversation_history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": self.system_prompt}] + conversation_history
        function_calls_made = []
        response = self.client.chat.completions.create(model=self.model, messages=messages, tools=self.tools, tool_choice="auto")
        while response.choices[0].message.tool_calls:
            assistant_message = response.choices[0].message
            conversation_history.append({"role": "assistant", "content": assistant_message.content, "tool_calls": assistant_message.tool_calls})
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                function_calls_made.append({"name": function_name, "arguments": function_args})
                function_response = self._execute_function(function_name, function_args)
                conversation_history.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(function_response)})
            messages = [{"role": "system", "content": self.system_prompt}] + conversation_history
            response = self.client.chat.completions.create(model=self.model, messages=messages, tools=self.tools, tool_choice="auto")
        assistant_response = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": assistant_response})
        return assistant_response, conversation_history, function_calls_made
    
    def _execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Any:
        if function_name not in self.functions:
            return {"error": f"Function {function_name} not found"}
        try:
            return self.functions[function_name](**arguments)
        except Exception as e:
            return {"error": str(e)}
