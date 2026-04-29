#!/usr/bin/env python3
"""
WhatsApp Business API Status Monitor - Server Edition
For running on a cloud server (DigitalOcean, Vultr, AWS, etc.)
Sends email only on status changes.
"""

import json
import re
import smtplib
import requests
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

STATE_FILE = Path("/var/whatsapp_monitor/state.json")
CONFIG_FILE = Path("/var/whatsapp_monitor/config.json")

@dataclass
class StatusData:
    timestamp: str
    overall: str
    components: dict

class EmailNotifier:
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {}
    
    def save_config(self, config: dict):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    def send(self, subject: str, html_body: str):
        if not all([self.config.get('smtp_host'), self.config.get('smtp_port'), 
                    self.config.get('email_from'), self.config.get('email_to'), 
                    self.config.get('email_password')]):
            print("Email not configured. Run: python3 server_status.py configure")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config['email_from']
            msg['To'] = self.config['email_to']
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(self.config['smtp_host'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['email_from'], self.config['email_password'])
                server.send_message(msg)
            
            print(f"Email sent to {self.config['email_to']}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

class StatusChecker:
    BASE_URL = "https://metastatus.com/whatsapp-business-api"
    
    def check(self) -> StatusData:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            import urllib.request
            req = urllib.request.Request(self.BASE_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8')
        except Exception as e:
            print(f"HTTP request failed: {e}")
            return None
        
        overall = "unknown"
        if 'no_known_issues' in html:
            overall = "operational"
        elif 'partial_outage' in html:
            overall = "partial_outage"
        elif 'major_outage' in html:
            overall = "major_outage"
        elif 'degraded_performance' in html:
            overall = "degraded"
        
        services = re.findall(r'<p class="[^"]*_serviceName[^"]*">([^<]+)</p>', html)
        status_icons = [s for s in re.findall(r'alt="([^"]+)"', html) if 'icon' in s.lower()]
        
        components = {}
        for i, service in enumerate(services):
            service = service.strip()
            if service:
                status = "operational"
                if i < len(status_icons):
                    alt = status_icons[i].lower()
                    if 'no known' in alt:
                        status = "operational"
                    elif 'degraded' in alt:
                        status = "degraded"
                    elif 'partial' in alt:
                        status = "partial_outage"
                    elif 'outage' in alt or 'major' in alt:
                        status = "major_outage"
                    elif 'maintenance' in alt:
                        status = "maintenance"
                
                components[service] = status
        
        return StatusData(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            overall=overall,
            components=components
        )

class StatusMonitor:
    def __init__(self):
        self.checker = StatusChecker()
        self.notifier = EmailNotifier()
    
    def load_last_state(self) -> StatusData:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                data = json.load(f)
                return StatusData(
                    timestamp=data.get('timestamp', ''),
                    overall=data.get('overall', 'unknown'),
                    components=data.get('components', {})
                )
        return StatusData(timestamp='', overall='', components={})
    
    def save_state(self, data: StatusData):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'timestamp': data.timestamp,
                'overall': data.overall,
                'components': data.components
            }, f, indent=2)
    
    def format_email(self, current: StatusData, changes: list, old_overall: str) -> tuple:
        if not changes:
            return None, None
        
        emoji = "🔴" if any('outage' in c['new'].lower() or 'major' in c['new'].lower() for c in changes) else \
                "🟡" if any('degraded' in c['new'].lower() for c in changes) else "✅"
        
        subject = f"{emoji} WhatsApp Business API: {len(changes)} change(s)"
        if old_overall != current.overall:
            subject += f" ({old_overall} → {current.overall})"
        
        rows = []
        for c in changes:
            status_emoji = "✅" if 'operational' in c['new'].lower() else \
                          "🔴" if 'outage' in c['new'].lower() or 'major' in c['new'].lower() else \
                          "🟡" if 'degraded' in c['new'].lower() or 'partial' in c['new'].lower() else "🔧"
            rows.append(f"""
            <tr>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee;">
                    <strong>{status_emoji} {c['component']}</strong>
                </td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee; 
                          color: {self.status_color(c['old'])};">{c['old']}</td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #eee; 
                          color: {self.status_color(c['new'])}; font-weight: bold;">{c['new']}</td>
            </tr>
            """)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                    background: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; 
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
                <div style="background: linear-gradient(135deg, #0084ff, #00a1ff); padding: 25px;">
                    <h1 style="color: white; margin: 0; font-size: 20px;">🔔 WhatsApp Business API Status Change</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0;">
                        {current.timestamp}
                    </p>
                </div>
                
                {f'<div style="background: #fff3cd; padding: 15px; margin: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">'
                 f'<strong>Overall Status:</strong> {old_overall} → <strong>{current.overall}</strong></div>' 
                 if old_overall != current.overall else ''}
                
                <div style="padding: 20px;">
                    <h3 style="margin: 0 0 15px; color: #333;">Changed Components</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="padding: 10px; text-align: left;">Component</th>
                                <th style="padding: 10px; text-align: left;">Previous</th>
                                <th style="padding: 10px; text-align: left;">Current</th>
                            </tr>
                        </thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                </div>
                
                <div style="padding: 15px 20px; background: #f8f9fa; border-top: 1px solid #eee;">
                    <p style="margin: 0; color: #666; font-size: 12px;">
                        Source: <a href="https://metastatus.com/whatsapp-business-api" style="color: #0084ff;">
                        metastatus.com/whatsapp-business-api</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, html
    
    def status_color(self, status: str) -> str:
        s = status.lower()
        if 'operational' in s: return "#27ae60"
        if 'outage' in s or 'major' in s: return "#e74c3c"
        if 'degraded' in s or 'partial' in s: return "#f39c12"
        if 'maintenance' in s: return "#3498db"
        return "#95a5a6"
    
    def run(self) -> bool:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking WhatsApp Business API...")
        
        current = self.checker.check()
        if not current:
            print("Failed to fetch status")
            return False
        
        last = self.load_last_state()
        changes = []
        
        if last.overall and last.overall != current.overall:
            changes.append({'component': 'Overall Status', 'old': last.overall, 'new': current.overall})
        
        for name, status in current.components.items():
            if name in last.components:
                if last.components[name] != status:
                    changes.append({'component': name, 'old': last.components[name], 'new': status})
            else:
                changes.append({'component': name, 'old': 'new', 'new': status})
        
        if changes:
            subject, html = self.format_email(current, changes, last.overall)
            if subject and html:
                self.notifier.send(subject, html)
                print(f"Change detected: {len(changes)} update(s)")
        else:
            print("No changes - all systems operational")
        
        self.save_state(current)
        return len(changes) > 0

def configure():
    config = {}
    
    print("\nEmail Configuration")
    print("="*50)
    
    config['smtp_host'] = input("SMTP Host (gmail=smtp.gmail.com): ").strip() or "smtp.gmail.com"
    config['smtp_port'] = int(input("SMTP Port (587): ").strip() or "587")
    config['email_from'] = input("From email: ").strip()
    config['email_password'] = input("App Password: ").strip()
    config['email_to'] = input("To email: ").strip() or config['email_from']
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Configured!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'configure':
        configure()
    else:
        monitor = StatusMonitor()
        monitor.run()