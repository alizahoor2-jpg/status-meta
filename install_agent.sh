#!/bin/bash
# Install WhatsApp Status Monitor as a LaunchAgent

SCRIPT_DIR="/Users/macbookm2air/Documents/Status Meta"
PLIST="$HOME/Library/LaunchAgents/com.whatsapp.statusmonitor.plist"

echo "Installing WhatsApp Status Monitor..."
echo ""

# Create directory
mkdir -p "$HOME/.whatsapp_status_monitor"
mkdir -p "$HOME/Library/LaunchAgents"

# Copy plist
cp "/Users/macbookm2air/Library/LaunchAgents/com.whatsapp.statusmonitor.plist" "$PLIST"

# Load the agent
launchctl load "$PLIST"

echo "✅ LaunchAgent installed!"
echo ""
echo "What it does:"
echo "  • Runs every 30 minutes (1800 seconds)"
echo "  • Sends email only when status changes"
echo "  • Logs to: ~/.whatsapp_status_monitor/agent.log"
echo ""
echo "Commands:"
echo "  launchctl list | grep whatsapp     # Check if running"
echo "  launchctl stop com.whatsapp.statusmonitor   # Stop"
echo "  launchctl start com.whatsapp.statusmonitor  # Start"
echo ""
echo "To uninstall:"
echo "  launchctl unload $PLIST && rm $PLIST"
echo ""

# Check status
echo "Current status:"
launchctl list | grep whatsapp || echo "Agent loaded, will run next cycle"