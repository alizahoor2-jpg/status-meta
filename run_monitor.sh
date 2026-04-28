#!/bin/bash
# WhatsApp Business API Status Monitor Launcher
# Run this to start the monitor

cd "$(dirname "$0")"

# Check for dependencies
if ! python3 -c "import requests, bs4" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install requests beautifulsoup4
fi

# Run the monitor
exec python3 status_monitor.py "$@"