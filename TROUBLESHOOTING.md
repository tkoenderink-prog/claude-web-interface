# Troubleshooting Guide

## "Access to 127.0.0.1 was denied" Error

### Solution 1: Use localhost instead
Try: **http://localhost:5000** instead of http://127.0.0.1:5000

### Solution 2: Use the new start script
```bash
./start.sh
```
This binds to all interfaces (0.0.0.0) which should work better.

### Solution 3: Check your browser
1. **Clear browser cache** for localhost
2. **Try incognito/private mode**
3. **Try a different browser** (Chrome, Firefox, Safari)
4. **Disable browser extensions** that might block local connections

### Solution 4: Check firewall
On Mac, check if firewall is blocking:
```bash
# Check firewall status
sudo pfctl -s info

# Temporarily allow all local connections
sudo pfctl -d  # Disable firewall temporarily
```

### Solution 5: Use a different port
Edit `.env` file:
```
SERVER_PORT=8080
```
Then access: http://localhost:8080

### Solution 6: Check if port is already in use
```bash
# Check what's using port 5000
lsof -i :5000

# Kill any process using it
kill -9 <PID>
```

### Solution 7: Direct Python run
```bash
cd web-interface
/opt/homebrew/opt/python@3.11/bin/python3.11 -m flask run --host=0.0.0.0 --port=5000 --app=app_simple
```

## Other Common Issues

### "No module named 'aiohttp'"
```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install aiohttp
```

### Database errors
```bash
rm data/claude_clone.db
mkdir -p data
```

### Session key not working
- Make sure you're copying the entire value
- The key should be very long (100+ characters)
- Try logging out and back into Claude.ai

## Quick Test

Test if Flask is working at all:
```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -c "
from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello(): return 'Flask is working!'
app.run(host='0.0.0.0', port=5000)
"
```

Then try: http://localhost:5000

If this works, the issue is with the app, not Flask or your network.