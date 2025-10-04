# Claude Clone - Simple Authentication Guide

## 🚀 Quick Start (No Browser Automation!)

This version uses a much simpler approach - you just paste your session key from Claude.ai.
No ChromeDriver issues, no popup browsers, just copy and paste!

## How to Use

### Step 1: Start the App
```bash
./run_simple.sh
```

### Step 2: Get Your Session Key

1. **Open claude.ai in your browser** and log in with your Max 20 account
2. **Open Developer Tools** (F12 or right-click → Inspect)
3. **Go to Application tab** → Storage → Cookies → claude.ai
4. **Find "sessionKey"** cookie
5. **Copy the Value** (it's a long string)

### Step 3: Connect

1. **Go to http://localhost:5000**
2. **Paste your session key**
3. **Click "Connect to Claude"**
4. **Start chatting!**

## Alternative Method (Faster)

In Claude.ai, open Console and run:
```javascript
copy(document.cookie.match(/sessionKey=([^;]+)/)[1])
```
This copies your session key to clipboard automatically!

## How It Works

Instead of complex browser automation:
- You manually get your session key from Claude.ai
- The app uses this key to make API calls
- Session is saved locally for 7 days
- When it expires, just get a new key

## Benefits

✅ **No ChromeDriver issues** - No version mismatches
✅ **No popups** - Everything in your existing browser
✅ **Simple** - Just copy and paste
✅ **Reliable** - No automation failures
✅ **Fast** - Instant connection

## Session Key Info

- **What is it?** A temporary authentication token from Claude
- **How long does it last?** Usually 7-14 days
- **Is it safe?** Yes, only stored locally on your machine
- **What if it expires?** Just get a new one the same way

## Files Changed

- `app_simple.py` - Simplified Flask app
- `services/claude_session_service.py` - Session-based service
- `templates/simple_auth.html` - Clean auth UI
- `run_simple.sh` - Launch script

## Troubleshooting

### Session Key Not Working?
- Make sure you're logged into Claude.ai
- Copy the entire value (it's long!)
- Try getting a fresh key

### Session Expired?
- Just get a new key from Claude.ai
- The app will prompt you when needed

### Can't Find sessionKey Cookie?
1. Make sure you're on claude.ai
2. Try refreshing the page
3. Look in Application → Cookies → claude.ai

## Technical Details

The app now:
1. Takes your session key
2. Stores it locally in `data/claude_session.json`
3. Uses it for all Claude API calls
4. Works exactly like being logged into Claude.ai

## To Launch

```bash
cd web-interface
./run_simple.sh
```

Then follow the on-screen instructions!

---

This approach is much simpler and more reliable than browser automation. It's how most unofficial Claude clients work, and it's perfectly fine for personal use with your valid subscription.