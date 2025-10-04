#!/bin/bash

# Claude Clone - Simple Session Key Authentication

echo "🚀 Starting Claude Clone with Simple Authentication..."
echo "   No browser automation - just paste your session key!"
echo ""

# Create necessary directories
mkdir -p data static/uploads

# Install minimal dependencies if needed
echo "📦 Checking dependencies..."
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing Flask dependencies..."
    /opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install flask flask-cors flask-socketio flask-sqlalchemy flask-login aiohttp
fi

# Run the application
echo "✅ Starting Flask application..."
echo "🌐 Open http://localhost:5000 in your browser"
echo ""
echo "📝 How to connect:"
echo "   1. Go to claude.ai and log in"
echo "   2. Open DevTools → Application → Cookies"
echo "   3. Copy the 'sessionKey' value"
echo "   4. Paste it in the app"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

/opt/homebrew/opt/python@3.11/bin/python3.11 app_simple.py