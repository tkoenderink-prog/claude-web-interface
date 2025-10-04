#!/bin/bash

# Simple startup script for Claude Clone

echo "🚀 Starting Claude Clone with Browser Authentication..."

# Create necessary directories
mkdir -p data static/uploads

# Start the app
echo "✅ Launching application..."
echo "🌐 Open http://localhost:5000 in your browser"
echo ""

/opt/homebrew/opt/python@3.11/bin/python3.11 app_browser.py