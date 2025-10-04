#!/bin/bash

# Claude Clone - Run Script with Browser Authentication

echo "🚀 Starting Claude Clone with Browser Authentication..."
echo "   This version uses your Claude Max 20 subscription"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
fi

# Create necessary directories
mkdir -p data static/uploads

# Install dependencies if needed
echo "📦 Checking dependencies..."

# Check for browser automation dependencies
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "import selenium" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing browser automation dependencies..."
    /opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install selenium undetected-chromedriver
fi

# Check for Flask dependencies
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing Flask dependencies..."
    /opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install flask flask-cors flask-socketio flask-sqlalchemy flask-login
fi

# Check for Chrome/Chromium
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null; then
    echo "⚠️  Chrome/Chromium not found. Installing..."
    if command -v brew &> /dev/null; then
        brew install --cask google-chrome
    else
        echo "❌ Please install Google Chrome manually from https://www.google.com/chrome/"
        exit 1
    fi
fi

# Run the application with browser auth
echo "✅ Starting Flask application with browser authentication..."
echo "🌐 Open http://localhost:5000 in your browser"
echo ""
echo "📝 Note: You'll be prompted to log in with your Claude Max 20 account"
echo "   The browser will open automatically for authentication"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

/opt/homebrew/opt/python@3.11/bin/python3.11 app_browser.py