# 🚀 Crypto Trading Analysis Dashboard

An intelligent crypto trading analysis platform with automated factor analysis, news evaluation, and integrated FreqTrade support.

## ✨ Features

- 📊 **Comprehensive Market Analysis** - Multi-factor technical analysis
- 🤖 **AI-Powered Insights** - LLM-driven news and market evaluation  
- 💹 **Integrated Trading** - FreqTrade + FreqUI for automated trading
- 🛡️ **Security First** - Auto-generated credentials and dry-run safety
- 📱 **Modern Interface** - Responsive React dashboard with real-time updates
- 🐳 **Docker Ready** - One-command deployment

## 🎯 Quick Start

**Choose your preferred setup workflow:**

### Option 1: Set API Key First (Recommended)
```bash
# 1. Configure OpenAI API key
./update_openai_credentials.sh

# 2. Deploy everything
./deploy.sh

# 3. Access dashboard: http://localhost:14250
```

### Option 2: Deploy and Configure Later
```bash
# 1. Deploy with demo settings (safe!)
./deploy.sh

# 2. Configure when ready
./update_openai_credentials.sh
```

📖 **See [QUICK_START.md](QUICK_START.md) for detailed setup options**

## 🏗️ Project Structure

### Prerequisites

- Node.js (with pnpm installed)
- Python (with UV installed)

### Installation

1. **Install all dependencies (frontend and backend):**

   ```bash
   pnpm run install:all
   ```

### Running the Development Servers

To run both the frontend and backend development servers concurrently:

```bash
pnpm run dev
```

This will start:
- The backend server (FastAPI/Uvicorn) with auto-reloading.
- The frontend development server (Vite).

### Building the Project

To build both the frontend and backend:

```bash
pnpm run build
```

This will:
- Build the frontend for production.
- (Note: Backend build step is currently a placeholder and not fully implemented.)
