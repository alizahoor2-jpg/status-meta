#!/usr/bin/env python3
"""
WhatsApp Business API Status Monitor
Sends email ONLY when status changes
Uses Playwright to fetch JavaScript-rendered page
"""

import json
import re
import smtplib
import os
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

STATE_FILE = Path("state.json")

@dataclass
class ComponentStatus:
    name: str
    status: str
    details: str

class EmailNotifier:
    def __init__(self):
        self.email_from = 'mohdalizahoor@gmail.com'
        self.email_password = 'qlwb lerb nwom owna'
        self.email_to = 'mohdalizahoor@gmail.com'
        self.smtp_host = 'smtp.gmail.com'
        self.smtp_port = 587
    
    def send(self, subject: str, html_body: str):
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            print(f"Email sent to {self.email_to}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

class StatusChecker:
    BASE_URL = "https://metastatus.com/whatsapp-business-api"
    
    def check(self):
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            
            html = page.evaluate('() => document.getElementById("root").innerHTML')
            browser.close()
        
        overall_status = "unknown"
        
        if 'no_known_issues' in html:
            overall_status = "Operational"
        elif 'partial_outage' in html:
            overall_status = "Partial Outage"
        elif 'major_outage' in html:
            overall_status = "Major Outage"
        elif 'degraded_performance' in html:
            overall_status = "Degraded"
        
        date_match = re.search(r'Updated\s+([A-Za-z]+ \d+ \d+ \d+:\d+\s+[AP]M\s+[A-Za-z0-9+]+)', html)
        last_updated = date_match.group(1) if date_match else datetime.now().strftime("%b %d %Y %I:%M %p GMT+5")
        
        services = re.findall(r'<p class="[^"]*_serviceName[^"]*">([^<]+)</p>', html)
        status_icons = re.findall(r'alt="([^"]+)"', html)
        relevant_icons = [s for s in status_icons if 'icon' in s.lower()]
        
        components = []
        for i, service in enumerate(services):
            service = service.strip()
            if service:
                status = "Operational"
                details = "The service is up and running with no known issues"
                
                if i < len(relevant_icons):
                    icon = relevant_icons[i].lower()
                    if 'no known' in icon:
                        status = "Operational"
                        details = "The service is up and running with no known issues"
                    elif 'degraded' in icon:
                        status = "Degraded"
                        details = "Service is experiencing degraded performance"
                    elif 'partial' in icon:
                        status = "Partial Outage"
                        details = "Some users may experience issues"
                    elif 'major' in icon or 'outage' in icon:
                        status = "Major Outage"
                        details = "Service is currently down"
                    elif 'maintenance' in icon:
                        status = "Maintenance"
                        details = "Service is under maintenance"
                
                components.append(ComponentStatus(
                    name=service,
                    status=status,
                    details=details
                ))
        
        return last_updated, components

class StatusMonitor:
    def __init__(self):
        self.checker = StatusChecker()
        self.notifier = EmailNotifier()
    
    def load_state(self):
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {"timestamp": "", "components": {}}
    
    def save_state(self, last_updated, components):
        data = {
            "timestamp": last_updated,
            "components": {c.name: c.status for c in components}
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f)
    
    def format_email(self, last_updated, changes):
        subject = f"🔔 WhatsApp Business API Status Update - {len(changes)} change(s)"
        
        rows = []
        for change in changes:
            comp = change['component']
            new_status = change['new_status']
            old_status = change['old_status']
            status_color = self.status_color(new_status)
            new_details = change['new_details']
            
            rows.append(f"""
            <tr>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee;">
                    <strong>{comp}</strong>
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee; color: #888;">
                    {old_status}
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee; color: {status_color}; font-weight: bold;">
                    {new_status}
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee;">
                    {new_details}
                </td>
            </tr>
            """)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5;">
            <div style="max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
                <div style="background: linear-gradient(135deg, #e74c3c, #c0392b); padding: 25px;">
                    <h1 style="color: white; margin: 0; font-size: 20px;">🔔 Status Change Detected</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0;">{last_updated} • {len(changes)} change(s)</p>
                </div>
                <div style="padding: 20px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="padding: 12px; text-align: left;">Type</th>
                                <th style="padding: 12px; text-align: left;">Previous</th>
                                <th style="padding: 12px; text-align: left;">Current</th>
                                <th style="padding: 12px; text-align: left;">Details</th>
                            </tr>
                        </thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                </div>
                <div style="padding: 15px 20px; background: #f8f9fa; border-top: 1px solid #eee;">
                    <p style="margin: 0; color: #666; font-size: 12px;">
                        Source: <a href="https://metastatus.com/whatsapp-business-api" style="color: #0084ff;">metastatus.com/whatsapp-business-api</a>
                        <br>Powered by GitHub Actions + cron-job.org (every 5 min)
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, html
    
    def status_color(self, status):
        s = status.lower()
        if 'operational' in s: return "#27ae60"
        if 'outage' in s or 'major' in s: return "#e74c3c"
        if 'degraded' in s or 'partial' in s: return "#f39c12"
        if 'maintenance' in s: return "#3498db"
        return "#95a5a6"
    
    def run(self):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking...")
        
        last_updated, current_components = self.checker.check()
        
        if not current_components:
            print("Failed to fetch status")
            return False
        
        last_state = self.load_state()
        old_components = last_state.get("components", {})
        
        changes = []
        for comp in current_components:
            old_status = old_components.get(comp.name)
            if old_status and old_status != comp.status:
                changes.append({
                    "component": comp.name,
                    "old_status": old_status,
                    "new_status": comp.status,
                    "new_details": comp.details
                })
        
        if changes:
            subject, html = self.format_email(last_updated, changes)
            self.notifier.send(subject, html)
            print(f"Changed! Email sent: {len(changes)} update(s)")
        else:
            print("No changes - no email")
        
        self.save_state(last_updated, current_components)
        
        return len(changes) > 0

if __name__ == "__main__":
    monitor = StatusMonitor()
    monitor.run()