#!/bin/bash

# Claude Agent SDK Web Interface Launcher

echo "🚀 Claude Agent SDK Web Interface"
echo "================================="
echo ""

# Check Python 3.11
if [ ! -f "/opt/homebrew/opt/python@3.11/bin/python3.11" ]; then
    echo "❌ Python 3.11 not found at /opt/homebrew/opt/python@3.11"
    echo "   Please install with: brew install python@3.11"
    exit 1
fi

# Create necessary directories
mkdir -p data static/uploads

# Check for .env file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cat > .env << 'EOF'
# Claude Configuration
# Leave ANTHROPIC_API_KEY unset to use Claude subscription
# Uncomment and set to use API billing instead:
# ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Database
DATABASE_URL=sqlite:///data/claude_clone.db

# Obsidian Vault Paths
OBSIDIAN_PRIVATE_PATH=/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-Private
OBSIDIAN_POA_PATH=/Users/tijlkoenderink/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian-POA

# Server Settings
SERVER_HOST=127.0.0.1
SERVER_PORT=5000
DEBUG=True

# Security
SECRET_KEY=your-secret-key-change-this-in-production

# Features
ENABLE_PROJECT_KNOWLEDGE=True
ENABLE_TOOLS=True
EOF
    echo "✅ Created .env file - please review settings"
fi

# Check which port to use
PORT=5000
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 5000 is in use (likely macOS AirPlay)"
    PORT=5001
    echo "✅ Using port 5001 instead"
fi

# Kill any existing servers on the target port
lsof -ti:$PORT | xargs kill -9 2>/dev/null

echo ""
echo "✅ Starting server on port $PORT..."
echo "🌐 Open http://localhost:$PORT in your browser"
echo ""
echo "📝 Authentication:"
echo "   - Claude subscription: Leave ANTHROPIC_API_KEY unset (default)"
echo "   - API billing: Set ANTHROPIC_API_KEY in .env file"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application
SERVER_PORT=$PORT /opt/homebrew/opt/python@3.11/bin/python3.11 app.py