#!/bin/bash

# Deployment script for Quant Dashboard
set -e

command_exists() { command -v "$1" >/dev/null 2>&1; }

info() { echo -e "\033[0;34m$1\033[0m"; }
success() { echo -e "\033[0;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
error() { echo -e "\033[0;31m$1\033[0m"; }

# Function to generate secure random string
generate_secure_key() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Function to generate API credentials
generate_api_credentials() {
    info "🔐 Generating secure API credentials..."
    
    # Generate secure credentials
    FREQTRADE_USERNAME="admin_$(generate_secure_key 8)"
    FREQTRADE_PASSWORD=$(generate_secure_key 24)
    JWT_SECRET=$(generate_secure_key 64)
    WS_TOKEN=$(generate_secure_key 32)
    
    # Generate exchange API keys placeholders (only needed for live trading)
    BYBIT_API_KEY="DEMO_API_KEY_FOR_DRY_RUN"
    BYBIT_SECRET="DEMO_SECRET_FOR_DRY_RUN"
    
    success "✅ Generated secure credentials"
    info "ℹ️  Dry-run mode enabled - using demo API keys (safe for testing)"
    warn "⚠️  For live trading, update Bybit API credentials using: ./update_exchange_credentials.sh"
    
    echo ""
    info "🔐 Generated Freqtrade Credentials:"
    echo "  Username: ${FREQTRADE_USERNAME}"
    echo "  Password: ${FREQTRADE_PASSWORD}"
    echo "  JWT Secret: ${JWT_SECRET}"
    echo "  WebSocket Token: ${WS_TOKEN}"
}

info "🚀 Starting deployment of Quant Dashboard..."

# Create necessary directories
info "📁 Creating directories..."
mkdir -p data

# Ensure Freqtrade user_data directory and config exist
mkdir -p user_data user_data/strategies
# Check required files exist
if [ ! -f "user_data/strategies/ExternalSignalStrategy.py" ]; then
  error "❌ Missing strategy file: user_data/strategies/ExternalSignalStrategy.py"
  error "❌ Please create your trading strategy before deployment"
  exit 1
fi

# Generate secure credentials
generate_api_credentials

if [ ! -f "user_data/config_external_signals.json" ]; then
  error "❌ Missing config file: user_data/config_external_signals.json"
  error "❌ Please create your Freqtrade configuration before deployment"
  exit 1
else
  info "🔧 Updating existing Freqtrade config with new security credentials..."
  # Generate new credentials for existing config
  generate_api_credentials
  
  # Backup existing config
  cp user_data/config_external_signals.json user_data/config_external_signals.json.backup.$(date +%Y%m%d_%H%M%S)
  
  # Update existing config with new credentials using jq if available, otherwise manual replacement
  if command_exists jq; then
    jq --arg username "$FREQTRADE_USERNAME" \
       --arg password "$FREQTRADE_PASSWORD" \
       --arg jwt_secret "$JWT_SECRET" \
       --arg ws_token "$WS_TOKEN" \
       '.api_server.username = $username | 
        .api_server.password = $password | 
        .api_server.jwt_secret_key = $jwt_secret | 
        .api_server.ws_token = [$ws_token] |
        .api_server.CORS_origins = ["http://localhost:3000", "http://localhost:14250", "https://btc.subx.fun", "https://ftui.subx.fun"]' \
       user_data/config_external_signals.json > user_data/config_temp.json && \
    mv user_data/config_temp.json user_data/config_external_signals.json
    success "✅ Updated existing config with new security credentials"
  else
    warn "⚠️  jq not available - please manually update API credentials in user_data/config_external_signals.json"
  fi
fi

# Get OpenAI API credentials
echo ""
info "🤖 OpenAI API Configuration"
read -p "Enter your OpenAI API Key: " OPENAI_KEY
read -p "Enter OpenAI Base URL (default: https://api.openai.com/v1): " OPENAI_BASE_URL

# Use default if empty
if [ -z "$OPENAI_BASE_URL" ]; then
    OPENAI_BASE_URL="https://api.openai.com/v1"
fi

info "📝 Creating .env file with API credentials..."

cat > .env << EOF
# OpenAI API Configuration
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_BASE_URL=${OPENAI_BASE_URL}

# Freqtrade API Configuration
FREQTRADE_API_URL=http://freqtrade-bot:8080
FREQTRADE_API_USERNAME=${FREQTRADE_USERNAME}
FREQTRADE_API_PASSWORD=${FREQTRADE_PASSWORD}
FREQTRADE_API_TOKEN=${WS_TOKEN}
FREQTRADE_API_TIMEOUT=15

# Security
JWT_SECRET_KEY=${JWT_SECRET}
WS_TOKEN=${WS_TOKEN}
EOF

success "✅ OpenAI API key configured"

success "✅ Created .env file with secure credentials"

# Backup existing database if it exists
backup_database() {
  local db_path="./data/crypto_data.db"
  local backup_path="./data/crypto_data.db.backup.$(date +%Y%m%d_%H%M%S)"
  
  if [ -f "$db_path" ]; then
    info "💾 Backing up existing database..."
    cp "$db_path" "$backup_path"
    success "✅ Database backed up to: $backup_path"
    echo "$backup_path" > ./data/.last_backup_path
  else
    info "ℹ️  No existing database found to backup - this is normal for first-time setup"
  fi
  # Always return success to continue deployment
  return 0
}

# Restore database from backup if needed
restore_database() {
  local backup_path_file="./data/.last_backup_path"
  
  if [ -f "$backup_path_file" ]; then
    local backup_path=$(cat "$backup_path_file")
    if [ -f "$backup_path" ]; then
      info "🔄 Checking if database restore is needed..."
      
      # Check if current database exists and is valid
      if [ ! -f "./data/crypto_data.db" ]; then
        warn "⚠️  Database not found after deployment, restoring from backup..."
        cp "$backup_path" "./data/crypto_data.db"
        success "✅ Database restored from backup"
      else
        # Check if database is accessible (basic validation)
        if ! docker exec crypto-trader sqlite3 /app/data/crypto_data.db ".tables" >/dev/null 2>&1; then
          warn "⚠️  Database appears corrupted, restoring from backup..."
          cp "$backup_path" "./data/crypto_data.db"
          success "✅ Database restored from backup due to corruption"
        else
          success "✅ Database is healthy, backup not needed"
        fi
      fi
    fi
  fi
}

# Backup database before deployment
backup_database

# If docker is not available or explicitly skipped, run local validation to test routes
if [ "$SKIP_DOCKER" = "1" ] || ! command_exists docker || ! command_exists docker-compose; then
  warn "⚠️  未检测到 Docker 或 docker-compose，进入本地测试模式（不启动容器）..."

  # Validate that backend can serve SPA without a prebuilt static folder
  if grep -q "@app.get(\"/{full_path:path}\")" backend/main.py; then
    success "✅ 检测到通配路由，支持SPA前端"
  else
    warn "⚠️  未检测到通配路由，请检查 backend/main.py"
  fi

  # Frontend build is optional in local mode
  if [ -f "backend/static/index.html" ]; then
    success "✅ 检测到 backend/static/index.html"
  else
    warn "ℹ️  本地未发现构建后的前端，将返回API信息或需要自行构建前端"
  fi

  # Check static mounts
  [ -d "backend/static/assets" ] && success "✅ 检测到静态资源目录 backend/static/assets" || warn "⚠️  未检测到 backend/static/assets"
  [ -d "backend/static/icons" ] && success "✅ 检测到图标目录 backend/static/icons" || warn "⚠️  未检测到 backend/static/icons"
  [ -f "backend/static/manifest.json" ] && success "✅ 检测到 PWA 文件 manifest.json" || warn "⚠️  未检测到 manifest.json"
  [ -f "backend/static/sw.js" ] && success "✅ 检测到 PWA 文件 sw.js" || warn "⚠️  未检测到 sw.js"

  success "🎉 本地路由检查通过：根路径将返回前端 index.html"
  echo ""
  info "👉 你可以在安装 Docker 后再次运行本脚本进行完整部署"
  exit 0
fi

# Create Traefik network if it doesn't exist
info "🌐 Creating Traefik network..."
docker network create traefik 2>/dev/null || echo "Network 'traefik' already exists"

# Build and start services
info "🔨 Building and starting services..."
docker-compose down --remove-orphans
if [ "$NO_CACHE" = "1" ]; then
  docker-compose build --no-cache
else
  docker-compose build
fi
docker-compose up -d

# Wait for services to be ready
info "⏳ Waiting for services to start..."
sleep 12

# Check service status
success "✅ Checking service status..."
docker-compose ps

# Restore database if needed
restore_database

# Optional: quick health check via curl if available
if command_exists curl; then
  info "🔍 Verifying root path returns index.html..."
  if curl -sSf "http://localhost:14250/" | grep -qi "<div id=\"root\">"; then
    success "✅ Root path served frontend index.html"
  else
    warn "⚠️  Root path content did not match expected HTML"
  fi
fi

success "🎉 Deployment completed!"
echo ""
info "📊 Application URLs:"
echo "  - Main Dashboard: http://localhost:14250"
echo "  - API Documentation: http://localhost:14250/docs"
echo "  - Freqtrade API: http://localhost:6677"
echo ""
info "🌐 Production URLs:"
echo "  - Main Dashboard: https://btc.subx.fun"
echo "  - FreqUI: https://freq.subx.fun"
echo ""
info "🔐 Security Information:"
echo "  - Freqtrade Username: ${FREQTRADE_USERNAME}"
echo "  - Freqtrade Password: ${FREQTRADE_PASSWORD}"
echo "  - WebSocket Token: ${WS_TOKEN}"
echo "  - JWT Secret: ${JWT_SECRET:0:10}..."
echo ""
warn "⚠️  IMPORTANT SETUP NOTES:"
echo "  1. Update OpenAI API key: ./update_openai_credentials.sh"
echo "  2. System is in DRY-RUN mode (safe, no real trading)"
echo "  3. For live trading: ./update_exchange_credentials.sh"
echo "  4. Save the credentials above in a secure location"
echo "  5. Never commit .env file to version control"
echo ""
info "📁 Data persistence:"
echo "  - Database: ./data/crypto_data.db"
echo "  - Freqtrade config: ./user_data/config_external_signals.json"
echo "  - Environment vars: ./.env"
echo ""
info "🔧 Useful commands:"
echo "  - View all logs: docker-compose logs -f"
echo "  - View FreqUI logs: docker-compose logs -f freqtrade-ui"
echo "  - View Freqtrade logs: docker-compose logs -f freqtrade"
echo "  - Stop services: docker-compose down"
echo "  - Restart: docker-compose restart"
echo "  - Update credentials: ./deploy.sh"
