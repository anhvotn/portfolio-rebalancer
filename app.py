import os
import sys
import threading
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from agent import PortfolioRebalancerAgent

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-your"):
    sys.exit("ERROR: OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

app = Flask(__name__)
# A fixed secret keeps sessions valid across restarts and across gunicorn workers.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "dev-only-change-me"
if app.secret_key == "dev-only-change-me":
    print("[warn] FLASK_SECRET_KEY not set - using an insecure development key.")

agent = PortfolioRebalancerAgent(api_key, portfolio_path=os.getenv("PORTFOLIO_FILE", "portfolio.json"))

# Conversation history is kept on the server (a browser cookie holds only ~4 KB).
# NOTE: in-memory store = per process. With several gunicorn workers use one worker,
# or replace this dict with Redis / a database.
MAX_HISTORY_MESSAGES = 40
_histories = {}
_lock = threading.Lock()


def _conversation_id() -> str:
    if "cid" not in session:
        session["cid"] = uuid.uuid4().hex
    return session["cid"]


def _trim(history):
    """Keep the last messages, starting at a user turn so tool messages stay paired."""
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    h = history[-MAX_HISTORY_MESSAGES:]
    while h and h[0].get("role") != "user":
        h = h[1:]
    return h


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "No message provided"}), 400
    cid = _conversation_id()
    with _lock:
        history = list(_histories.get(cid, []))
    try:
        response, history, calls = agent.chat(message, history)
    except Exception as e:
        app.logger.exception("chat failed")
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500
    with _lock:
        _histories[cid] = _trim(history)
    return jsonify({"response": response, "function_calls": calls})


@app.route("/api/reset", methods=["POST"])
def reset():
    with _lock:
        _histories.pop(session.get("cid"), None)
    return jsonify({"status": "success", "message": "Conversation reset"})


@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    holdings = agent.portfolio_ext.get_portfolio_holdings()
    if holdings.get("status") != "success":
        return jsonify({"error": holdings.get("message", "Could not load portfolio")}), 500
    return jsonify({"holdings": holdings,
                    "targets": agent.portfolio_ext.get_target_allocation(),
                    "drift": agent.portfolio_ext.calculate_allocation_drift()})


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")  # local only by default; never expose debug mode
    port = int(os.getenv("PORT", 5000))
    print(f"Portfolio Rebalancing Assistant - open http://{host}:{port}  (CTRL+C to stop)")
    app.run(debug=debug, host=host, port=port)
