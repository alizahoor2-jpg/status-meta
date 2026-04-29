#!/bin/bash
# Setup cron job to run status check every 30 minutes

SCRIPT_DIR="/Users/macbookm2air/Documents/Status Meta"
PYTHON="/usr/bin/python3"

# Remove any existing cron job
crontab -l 2>/dev/null | grep -v "status_check.py" > /tmp/current_cron

# Add new cron job (every 30 minutes)
echo "*/30 * * * * cd '$SCRIPT_DIR' && $PYTHON status_check.py >> ~/.whatsapp_status_monitor/cron.log 2>&1" >> /tmp/current_cron

# Install new crontab
crontab /tmp/current_cron
rm /tmp/current_cron

# Create log directory
mkdir -p ~/.whatsapp_status_monitor

echo "Cron job installed:"
echo "*/30 * * * *  →  Runs every 30 minutes"
echo ""
echo "View logs: tail -f ~/.whatsapp_status_monitor/cron.log"
echo "View status: python3 status_check.py view"
echo ""
echo "To remove: crontab -e (then delete the line)"

# Show current crontab
echo ""
echo "Current crontab:"
crontab -l