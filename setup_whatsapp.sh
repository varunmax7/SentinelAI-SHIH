#!/bin/bash

# WhatsApp Integration Setup Script for Sentinel AI (Local Version)
# This script helps you set up ngrok and configure the Twilio webhook

echo "============================================================"
echo "🛡️  Sentinel AI - WhatsApp Integration Setup"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if ngrok is already in the current directory
echo -e "${BLUE}📦 Checking for ngrok...${NC}"
if [ -f "./ngrok" ]; then
    echo -e "${GREEN}✅ Local ngrok found${NC}"
    ./ngrok version
elif command -v ngrok &> /dev/null; then
    echo -e "${GREEN}✅ System ngrok found${NC}"
    ngrok version
else
    echo -e "${YELLOW}⚠️  ngrok not found. Downloading...${NC}"
    
    # Download ngrok for Mac
    curl -O https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip
    
    # Unzip
    echo "Extracting..."
    unzip -o ngrok-v3-stable-darwin-amd64.zip
    
    # Clean up
    rm ngrok-v3-stable-darwin-amd64.zip
    
    echo -e "${GREEN}✅ ngrok downloaded successfully!${NC}"
    ./ngrok version
fi

# Determine which ngrok to use
NGROK="./ngrok"
if ! [ -f "./ngrok" ]; then
    NGROK="ngrok"
fi

echo ""
echo "============================================================"
echo "🚀 Starting Setup"
echo "============================================================"
echo ""

# Check if Flask app is running
echo -e "${BLUE}🔍 Checking if Flask app is running on port 5001...${NC}"
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${GREEN}✅ Flask app is running on port 5001${NC}"
else
    echo -e "${RED}❌ Flask app is not running on port 5001${NC}"
    echo -e "${YELLOW}Please make sure your python app is running!${NC}"
fi

echo ""
echo "============================================================"
echo "🌐 Starting ngrok tunnel"
echo "============================================================"
echo ""
echo -e "${YELLOW}⚠️  Important Instructions:${NC}"
echo "1. Run this command manually to see the output:"
echo "   $NGROK http 5001"
echo "2. Copy the HTTPS URL (e.g., https://xxxx.ngrok-free.app)"
echo "3. Go to: http://localhost:5001/whatsapp-setup"
echo "4. Paste your ngrok URL to generate the webhook URL"
echo "5. Configure the webhook in Twilio Console"
echo ""

# To avoid blocking the terminal, we just show the instructions now
# But we can try to start it in background and show the URL if possible
echo -e "${BLUE}Starting ngrok in background...${NC}"
$NGROK http 5001 --log=stdout > ngrok.log &
NGROK_PID=$!

sleep 5

# Try to get the public URL from the local ngrok API
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok-free.app' | head -n 1)

if [ -z "$PUBLIC_URL" ]; then
    echo -e "${RED}❌ Could not automatically retrieve public URL.${NC}"
    echo -e "${YELLOW}Please check ngrok.log or run ngrok manually.${NC}"
else
    echo -e "${GREEN}✅ ngrok is running!${NC}"
    echo -e "Public URL: ${CYAN}$PUBLIC_URL${NC}"
    echo -e "Webhook URL: ${GREEN}$PUBLIC_URL/webhook/whatsapp${NC}"
fi

echo ""
echo "============================================================"
echo "📱 Next Steps"
echo "============================================================"
echo ""
echo -e "${GREEN}1. Use this Webhook URL in Twilio Console:${NC}"
echo "   ${GREEN}$PUBLIC_URL/webhook/whatsapp${NC}"
echo ""
echo -e "${GREEN}2. Join WhatsApp Sandbox:${NC}"
echo "   - Send to: +1 415 523 8886"
echo "   - Message: join <your-sandbox-code>"
echo ""
echo -e "${GREEN}3. Link your account:${NC}"
echo "   - Send 'hi' to the bot"
echo ""
echo "============================================================"

# Wait for background ngrok to finish (which it won't unless killed)
echo -e "${YELLOW}ngrok is running in background (PID: $NGROK_PID).${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop it or kill $NGROK_PID later.${NC}"
wait $NGROK_PID
