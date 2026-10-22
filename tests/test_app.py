"""Offline tests (no OpenAI key or network needed): python -m pytest -q   or   python tests/test_app.py"""
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-offline")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")

from agent import NY, MarketDataExtension, PortfolioRebalancerAgent, nyse_holidays  # noqa: E402


class FakeClient:
    """Mimics client.chat.completions.create: first asks for tools, then answers."""
    def __init__(self, tool_names):
        self.tool_names, self.calls = list(tool_names), 0
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools, tool_choice):
        self.calls += 1
        json.dumps(messages)  # history must stay JSON-serialisable
        if self.tool_names:
            name = self.tool_names.pop(0)
            tc = NS(id=f"call_{self.calls}", type="function", function=NS(name=name, arguments="{}"))
            return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
        return NS(choices=[NS(message=NS(content="Done.", tool_calls=None))])


def test_rebalance_math():
    a = PortfolioRebalancerAgent("x", client=FakeClient([]))
    r = a.rebalancing_ext.generate_rebalance_recommendations()
    assert r["status"] == "success"
    recs = {x["symbol"]: x for x in r["recommendations"]}
    assert recs["VTI"]["action"] == "BUY" and recs["VTI"]["shares"] == int(recs["VTI"]["shares"])
    assert r["cash_after_estimate"] >= 0
    drift = a.portfolio_ext.calculate_allocation_drift()
    assert "CASH" in drift["drift"] and drift["warning"] is None
    costs = a.rebalancing_ext.calculate_transaction_costs(commission_per_trade=5)
    assert costs["num_trades"] == len(r["recommendations"])


def test_market_hours():
    m = MarketDataExtension()
    assert m.is_market_open(datetime(2026, 10, 20, 10, 0, tzinfo=NY))["is_open"] is True
    assert m.is_market_open(datetime(2026, 10, 20, 17, 0, tzinfo=NY))["next_open"].startswith("2026-10-21")
    assert m.is_market_open(datetime(2026, 11, 26, 11, 0, tzinfo=NY))["is_open"] is False  # Thanksgiving
    assert m.is_market_open(datetime(2026, 4, 3, 11, 0, tzinfo=NY))["is_open"] is False    # Good Friday
    assert {d.isoformat() for d in nyse_holidays(2026)} >= {"2026-01-01", "2026-07-03", "2026-12-25"}


def test_flask_chat_with_tool_calls():
    import app as app_module
    app_module.agent.client = FakeClient(["calculate_allocation_drift", "generate_rebalance_recommendations"])
    c = app_module.app.test_client()
    r = c.post("/api/chat", json={"message": "Show me rebalancing recommendations"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["response"] == "Done." and len(body["function_calls"]) == 2
    app_module.agent.client = FakeClient([])
    r2 = c.post("/api/chat", json={"message": "thanks"})  # same session: history reused
    assert r2.status_code == 200
    assert c.get("/api/portfolio").status_code == 200
    assert c.post("/api/reset").status_code == 200
    assert c.post("/api/chat", json={}).status_code == 400


if __name__ == "__main__":
    for t in (test_rebalance_math, test_market_hours, test_flask_chat_with_tool_calls):
        t()
        print("ok", t.__name__)
