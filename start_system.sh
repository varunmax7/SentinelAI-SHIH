#!/bin/bash
# Quick Start Script for Real-Time Volunteer Notifications

echo "🚀 STARTING DISASTER MANAGEMENT SYSTEM"
echo "=========================================="
echo ""

# Check if app is already running
if lsof -i :5001 >/dev/null 2>&1; then
    echo "⚠️  Port 5001 is already in use. Killing existing process..."
    lsof -i :5001 | grep -v COMMAND | awk '{print $2}' | xargs kill -9
    sleep 1
fi

# Start Flask app
echo "1️⃣  Starting Flask app..."
cd /Users/ramavathvarun/Downloads/disaster_management
python3 app.py &
APP_PID=$!
echo "✅ App started (PID: $APP_PID)"
sleep 2

# Check if app started successfully
if ! lsof -i :5001 >/dev/null 2>&1; then
    echo "❌ Failed to start app. Check errors above."
    exit 1
fi

echo ""
echo "2️⃣  Check ngrok tunnel status..."
if lsof -i :4040 >/dev/null 2>&1; then
    echo "⚠️  ngrok is already running. Get the URL from ngrok web interface (http://localhost:4040)"
else
    echo "ℹ️  ngrok not running. Start with:"
    echo "   ./ngrok http 5001"
    echo ""
fi

echo ""
echo "=========================================="
echo "✅ SYSTEM READY"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Start ngrok (in another terminal):"
echo "   ./ngrok http 5001"
echo ""
echo "2. Open browser tabs:"
echo "   Tab 1 (Official): https://<ngrok-url>/volunteer_management"
echo "   Tab 2 (Volunteer): Login as 'maxx'"
echo ""
echo "3. Click 'Assign Volunteer' in Tab 1"
echo ""
echo "4. Watch Tab 2:"
echo "   ✓ Bell icon should show red badge with number"
echo "   ✓ Toast notification should slide in from top-right"
echo "   ✓ Within 3 seconds total"
echo ""
echo "5. Click bell icon to view notification"
echo ""
echo "6. Click 'Accept' to accept assignment"
echo ""
echo "=========================================="
echo "Logs: tail -f /tmp/app.log"
echo "=========================================="
