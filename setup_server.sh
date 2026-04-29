#!/bin/bash
# Setup script for server deployment
# Run this on your cloud server (DigitalOcean, Vultr, etc.)

echo "==================================="
echo "WhatsApp Status Monitor - Server Setup"
echo "==================================="
echo ""

# Create directory
mkdir -p /var/whatsapp_monitor

# Copy script
cp server_status.py /var/whatsapp_monitor/

# Install cron (every 30 minutes)
CRON_JOB="*/30 * * * * /usr/bin/python3 /var/whatsapp_monitor/server_status.py >> /var/whatsapp_monitor/monitor.log 2>&1"

# Add to crontab
(crontab -l 2>/dev/null | grep -v "whatsapp_monitor"; echo "$CRON_JOB") | crontab -

echo "✅ Installed!"
echo ""
echo "Run: python3 server_status.py configure"
echo "Then: python3 server_status.py"
echo ""
echo "Crontab: */30 * * * * (every 30 min)"
echo "Logs: /var/whatsapp_monitor/monitor.log"