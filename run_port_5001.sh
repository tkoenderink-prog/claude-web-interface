#!/bin/bash

# Claude Clone - Run on Port 5001 (Avoids AirPlay conflict)

echo "🚀 Starting Claude Clone on Port 5001..."
echo "   (Port 5000 is used by macOS AirPlay Receiver)"
echo ""

# Create necessary directories
mkdir -p data static/uploads

# Kill any existing servers on 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null

echo "✅ Server starting..."
echo "🌐 Open http://localhost:5001 in your browser"
echo ""
echo "📝 Using Claude Agent SDK"
echo "   - For Claude subscription: Leave ANTHROPIC_API_KEY unset"
echo "   - For API billing: Set ANTHROPIC_API_KEY in .env file"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the main app on port 5001
SERVER_PORT=5001 /opt/homebrew/opt/python@3.11/bin/python3.11 app.py