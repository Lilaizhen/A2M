# Contributing to AlphaVantage MCP Server

Thanks for your interest in contributing! 🎉  
This project is the official [MCP (Model Context Protocol)](https://github.com/modelcontextprotocol/servers) server for [Alpha Vantage](https://www.alphavantage.co). Here's how to get started with local development and testing.

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/calvernaz/alphavantage.git
cd alphavantage
```
## Set up your environment

You'll need an [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key).

Create a .env file in the project root:

```bash
touch .env
```

Add your API key to the .env file:

```bash
ALPHAVANTAGE_API_KEY=your_api_key_here
```

Alternatively, you can export it directly in your terminal:
```bash
export ALPHAVANTAGE_API_KEY=your_api_key_here
```

## 🧪 Running Locally with Inspector

Use the MCP Inspector to run and test your server locally with hot reload.

```bash
npm install -g @modelcontextprotocol/inspector
```

Then, run the server:

```bash
npx @modelcontextprotocol/inspector uv --directory ~/alphavantage run alphavantage
```
> Replace ~/code/alphavantage with your actual path to this repo.

