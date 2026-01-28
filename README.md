<<<<<<< HEAD
# 📊 Portfolio Rebalancing Assistant

An AI-powered web application that helps you analyze your investment portfolio and provides intelligent rebalancing recommendations using OpenAI GPT-4.

## ✨ Features

- 💼 **Portfolio Analysis** - Comprehensive analysis of your holdings and allocations
- 📈 **Drift Tracking** - Monitor how far your allocation has drifted from targets
- 🎯 **Smart Recommendations** - AI-powered buy/sell recommendations
- 💰 **Cost Estimation** - Calculate transaction costs before rebalancing
- 🤖 **Interactive Chat** - Natural language interface powered by GPT-4
- 📱 **Responsive Design** - Beautiful UI that works on all devices

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## 📖 Usage

### Customize Your Portfolio

Edit `portfolio.json` to match your actual holdings:

```json
{
  "holdings": [
    {
      "symbol": "AAPL",
      "shares": 50,
      "current_price": 178.50,
      "cost_basis": 150.00
    }
  ],
  "cash": 5000.00,
  "target_allocation": {
    "AAPL": 15.0,
    "VTI": 50.0,
    "BND": 35.0
  }
}
```

### Chat with the Assistant

Try these example questions:
- "Analyze my portfolio"
- "Show me rebalancing recommendations"
- "Calculate my allocation drift"
- "What are the estimated transaction costs?"
- "Is the market open?"

### Key Components

- **Portfolio Data Extension** - Manages holdings and target allocations
- **Market Data Extension** - Fetches current prices (mock implementation)
- **Rebalancing Engine** - Calculates optimal trades and costs
- **AI Agent** - OpenAI GPT-4 with function calling capabilities

## 🛠️ Technologies Used

- **Backend**: Flask, Python
- **AI**: OpenAI GPT-4 with function calling
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Markdown Rendering**: Marked.js

## 🤝 Contributing

Contributions are welcome! Feel free to submit a Pull Request.

## ⚠️ Disclaimer

This is a demonstration application for educational purposes. **Always consult with a qualified financial advisor before making investment decisions.** Past performance does not guarantee future results.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with OpenAI GPT-4
- Inspired by GitHub Copilot SDK patterns
- UI design influenced by modern fintech applications

---

⭐ Star this repo if you find it helpful!
=======
# portfolio-rebalancer
AI-powered portfolio rebalancing assistant using GPT-4
>>>>>>> 64397c9de91592c5a813b1b410e3dea4fad49913

