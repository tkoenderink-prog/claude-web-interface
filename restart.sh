#!/bin/bash

# Kill any existing servers
echo "🛑 Stopping any running servers..."
lsof -ti:5001 | xargs kill -9 2>/dev/null
sleep 1

# Start fresh
echo "🚀 Starting Claude Clone with Real API..."
echo ""
echo "✅ Using your session key for real Claude responses!"
echo "🌐 Open http://localhost:5001"
echo ""

./run_port_5001.sh