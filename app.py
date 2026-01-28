from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from agent import PortfolioRebalancerAgent
from dotenv import load_dotenv
import os
import secrets
import sys

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key == "your_api_key_here":
    print("=" * 60)
    print("ERROR: OPENAI_API_KEY not set!")
    print("=" * 60)
    print("Please edit .env file and add your OpenAI API key")
    print("=" * 60)
    exit(1)

agent = PortfolioRebalancerAgent(api_key)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        conversation_history = session.get('conversation_history', [])
        response, updated_history, function_calls = agent.chat(user_message, conversation_history)
        session['conversation_history'] = updated_history
        return jsonify({"response": response, "function_calls": function_calls})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    session.pop('conversation_history', None)
    return jsonify({"status": "success", "message": "Conversation reset"})

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    try:
        holdings = agent.portfolio_ext.get_portfolio_holdings()
        targets = agent.portfolio_ext.get_target_allocation()
        drift = agent.portfolio_ext.calculate_allocation_drift()
        return jsonify({"holdings": holdings, "targets": targets, "drift": drift})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("")
    print("=" * 60)
    print("Portfolio Rebalancing Assistant - Web Interface")
    print("=" * 60)
    print("")
    print("[OK] Agent initialized successfully")
    print("[OK] Server starting...")
    print("")
    print("Open your browser to: http://localhost:5000")
    print("")
    print("Press CTRL+C to stop the server")
    print("")
    app.run(debug=True, host='0.0.0.0', port=5000)
