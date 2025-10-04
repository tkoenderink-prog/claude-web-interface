#!/bin/bash

echo "================================================================"
echo "Claude Web Interface v0.3.0 - Complete Verification"
echo "================================================================"
echo ""

# Change to web-interface directory
cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Step 1: Running Test Suite..."
echo "----------------------------------------------------------------"
/opt/homebrew/opt/python@3.11/bin/python3.11 tests/test_v030.py
TEST_RESULT=$?

echo ""
echo "🗄️  Step 2: Verifying Database Migration..."
echo "----------------------------------------------------------------"
/opt/homebrew/opt/python@3.11/bin/python3.11 verify_v030_migration.py
DB_RESULT=$?

echo ""
echo "⚙️  Step 3: Checking Services..."
echo "----------------------------------------------------------------"
/opt/homebrew/opt/python@3.11/bin/python3.11 << 'PYTHON'
from app import app
from services.mode_service import get_mode_service
from services.export_service import get_export_service

with app.app_context():
    mode_service = get_mode_service()
    export_service = get_export_service()
    print("✅ Mode service: OK")
    print("✅ Export service: OK")
PYTHON
SERVICE_RESULT=$?

echo ""
echo "📁 Step 4: Verifying Files..."
echo "----------------------------------------------------------------"

FILES=(
    "models/models.py"
    "services/mode_service.py"
    "services/export_service.py"
    "static/js/mobile.js"
    "static/css/mobile.css"
    "tests/test_v030.py"
)

FILE_CHECK=0
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file - MISSING"
        FILE_CHECK=1
    fi
done

echo ""
echo "================================================================"
echo "VERIFICATION SUMMARY"
echo "================================================================"

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Test Suite: PASSED${NC}"
else
    echo -e "${RED}❌ Test Suite: FAILED${NC}"
fi

if [ $DB_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Database Migration: COMPLETE${NC}"
else
    echo -e "${RED}❌ Database Migration: INCOMPLETE${NC}"
fi

if [ $SERVICE_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Services: OK${NC}"
else
    echo -e "${RED}❌ Services: ERROR${NC}"
fi

if [ $FILE_CHECK -eq 0 ]; then
    echo -e "${GREEN}✅ Files: ALL PRESENT${NC}"
else
    echo -e "${RED}❌ Files: MISSING${NC}"
fi

echo ""

# Overall status
if [ $TEST_RESULT -eq 0 ] && [ $DB_RESULT -eq 0 ] && [ $SERVICE_RESULT -eq 0 ] && [ $FILE_CHECK -eq 0 ]; then
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}✅ v0.3.0 IS READY FOR PRODUCTION${NC}"
    echo -e "${GREEN}================================================================${NC}"
    exit 0
else
    echo -e "${RED}================================================================${NC}"
    echo -e "${RED}❌ v0.3.0 HAS ISSUES - REVIEW ABOVE${NC}"
    echo -e "${RED}================================================================${NC}"
    exit 1
fi
