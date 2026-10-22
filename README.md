# Portfolio Rebalancing Assistant

A small Flask web app that analyses a portfolio stored in `portfolio.json` and suggests rebalancing trades. A chat assistant (OpenAI tool calling) answers questions. All numbers — drift, trades, cash and costs — are computed in Python, not by the language model.

> Educational demo, not financial advice. Prices come from `portfolio.json` and are not live quotes. Consider taxes and fees, and consult a qualified adviser before trading.

## Features

- **Portfolio analysis:** holdings, cash and total value.
- **Drift tracking:** current vs target weight for every holding, every target, and cash.
- **Rebalancing suggestions:**
  - Trades only positions that drifted more than a threshold (default ±5 percentage points).
  - Uses whole shares by default.
  - Funds buys from cash plus sells, and scales buys down if cash would run out.
- **Cost estimate:** commission per trade plus a spread in basis points.
- **US market status:** NYSE regular session in New York time, including the regular NYSE holidays.
- **Chat interface:** the model calls the tools above and explains the results.

## Quick start

Requires Python 3.9+ and an OpenAI API key.

```bash
git clone https://github.com/anhvotn/portfolio-rebalancer.git
cd portfolio-rebalancer
python -m venv venv
# macOS/Linux: source venv/bin/activate      Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# edit .env: OPENAI_API_KEY, MODEL_NAME, FLASK_SECRET_KEY

python app.py
```

Then open http://127.0.0.1:5000.

## Your portfolio

Edit `portfolio.json`:

```json
{
  "currency": "USD",
  "holdings": [
    {"symbol": "VTI", "shares": 100, "current_price": 245.60, "cost_basis": 220.00}
  ],
  "cash": 5000.00,
  "target_allocation": {"VTI": 60.0, "BND": 37.0, "CASH": 3.0}
}
```

- **Targets** are in % of total value, including cash. `CASH` is optional; if you leave it out, whatever remains of 100% is the cash target.
- **Prices:** update `current_price` yourself. A target symbol you don't hold yet needs a holding entry with `"shares": 0` and a price before it can be bought; until then it is listed under `missing_prices`.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | – | required |
| `MODEL_NAME` | `gpt-4o-mini` | any chat model with tool calling that your account can use |
| `FLASK_SECRET_KEY` | dev key | set a long random value; it keeps sessions valid across restarts |
| `REBALANCE_THRESHOLD_PCT` | `5` | trade only positions that drifted more than this |
| `MIN_TRADE_AMOUNT` | `100` | skip smaller trades |
| `ALLOW_FRACTIONAL_SHARES` | `false` | allow fractional share quantities |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | the app listens only on your own computer by default |
| `FLASK_DEBUG` | `false` | never enable when the app is reachable by others |

## Tests

```bash
pip install pytest
python -m pytest -q
```

The tests run offline with a fake OpenAI client.

## Deployment notes

- **Conversation history** is kept in server memory, one store per process. Run a single worker (`gunicorn -w 1 -b 127.0.0.1:5000 app:app`), or move the store to Redis or a database before using more workers.
- **Public exposure:** don't put the app on the public internet without authentication. It spends your OpenAI credits and shows your portfolio.

## Architecture

- `agent.py`
  - `PortfolioDataExtension`: reads `portfolio.json`, works out total value, targets and drift.
  - `MarketDataExtension`: prices from `portfolio.json` (mock fallback); NYSE hours and holidays.
  - `RebalancingEngineExtension`: trades and costs, computed from the portfolio file directly.
  - `PortfolioRebalancerAgent`: OpenAI tool-calling loop, capped at 8 rounds, with a JSON-safe history.
- `app.py`: Flask routes `/`, `/api/chat`, `/api/reset` and `/api/portfolio`.
- `templates/` and `static/`: vanilla JS front end. Markdown is rendered with marked and sanitised with DOMPurify.

## Changes in this version

- **Startup crash fixed:** the old `openai==1.6.1` pin no longer works with current `httpx`, so `requirements.txt` now uses a current `openai` version.
- **Chat crash fixed:** history now holds plain dicts instead of SDK objects, so sessions can be saved. It is kept on the server instead of in the ~4 KB cookie.
- **Sessions survive restarts:** the secret key now comes from the environment instead of being regenerated on every start.
- **Rebalancing reads the portfolio file itself,** instead of relying on the model to pass the data.
  - Cash is a target like any other.
  - Unheld targets are reported.
  - Buys stay within available cash.
- **Market hours:** now in New York time, with NYSE holidays and a correct next-open time.
- **Security:**
  - The app listens only on your own computer by default, and debug mode is off.
  - CORS is no longer open to all websites.
  - Assistant output is sanitised before display.
  - The CDN scripts are pinned to fixed versions.
- **Docs and repo:** the README merge conflict is resolved, and `.env.example`, `.gitignore` and offline tests are added.

## License

MIT, see `LICENSE`.
