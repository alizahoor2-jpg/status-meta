#!/usr/bin/env python3
"""
WhatsApp Business API Status Monitor Agent
Uses Playwright to monitor metastatus.com/whatsapp-business-api
Notifies on any status changes: downtime, degradation, incidents, resolved, etc.
"""

import json
import time
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

STATE_FILE = Path.home() / ".whatsapp_status_monitor" / "last_state.json"
CONFIG_FILE = Path.home() / ".whatsapp_status_monitor" / "config.json"

@dataclass
class ComponentStatus:
    name: str
    status: str
    status_type: str
    description: Optional[str] = None
    section: Optional[str] = None
    link: Optional[str] = None

@dataclass
class StatusChange:
    component: str
    old_status: str
    new_status: str
    timestamp: str
    section: Optional[str] = None
    description: Optional[str] = None
    severity: str = "info"

@dataclass 
class MonitorState:
    timestamp: str
    components: Dict[str, str] = field(default_factory=dict)
    overall_status: str = "unknown"

class Config:
    def __init__(self):
        self.load()
    
    def load(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                self.check_interval = data.get('check_interval', 300)
                self.email_enabled = data.get('email_enabled', False)
                self.email_to = data.get('email_to', '')
                self.email_from = data.get('email_from', '')
                self.email_password = data.get('email_password', '')
                self.smtp_server = data.get('smtp_server', 'smtp.gmail.com')
                self.smtp_port = data.get('smtp_port', 587)
                self.webhook_enabled = data.get('webhook_enabled', False)
                self.webhook_url = data.get('webhook_url', '')
                self.terminal_notify = data.get('terminal_notify', True)
                self.mac_notify = data.get('mac_notify', True)
                self.pushover_enabled = data.get('pushover_enabled', False)
                self.pushover_token = data.get('pushover_token', '')
                self.pushover_user = data.get('pushover_user', '')
        else:
            self.check_interval = 300
            self.email_enabled = False
            self.email_to = ''
            self.email_from = ''
            self.email_password = ''
            self.smtp_server = 'smtp.gmail.com'
            self.smtp_port = 587
            self.webhook_enabled = False
            self.webhook_url = ''
            self.terminal_notify = True
            self.mac_notify = True
            self.pushover_enabled = False
            self.pushover_token = ''
            self.pushover_user = ''
            self.save()
    
    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'check_interval': self.check_interval,
                'email_enabled': self.email_enabled,
                'email_to': self.email_to,
                'email_from': self.email_from,
                'email_password': self.email_password,
                'smtp_server': self.smtp_server,
                'smtp_port': self.smtp_port,
                'webhook_enabled': self.webhook_enabled,
                'webhook_url': self.webhook_url,
                'terminal_notify': self.terminal_notify,
                'mac_notify': self.mac_notify,
                'pushover_enabled': self.pushover_enabled,
                'pushover_token': self.pushover_token,
                'pushover_user': self.pushover_user
            }, f, indent=2)

class StatusFetcher:
    BASE_URL = "https://metastatus.com/whatsapp-business-api"
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
    
    def _get_browser(self):
        """Lazy initialization of Playwright browser"""
        if self.browser is None:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
        return self.page
    
    def fetch_status(self) -> Tuple[str, List[ComponentStatus], List[Dict]]:
        """Fetch current status from metastatus.com using Playwright"""
        try:
            page = self._get_browser()
            page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            
            components = []
            incidents = []
            
            data = page.evaluate('''() => {
                const root = document.getElementById('root');
                return root ? root.innerHTML : '';
            }''')
            
            html_content = data
            
            overall_status = self._extract_overall_status(html_content)
            
            sections = self._extract_sections(html_content)
            
            for section_name, section_components in sections.items():
                for comp in section_components:
                    components.append(ComponentStatus(
                        name=comp['name'],
                        status=comp['status'],
                        status_type=comp['status_type'],
                        description=comp.get('description'),
                        section=section_name
                    ))
            
            incidents = self._extract_incidents(html_content)
            
            logger.info(f"Fetched {len(components)} components across {len(sections)} sections, overall: {overall_status}, {len(incidents)} incidents")
            return overall_status, components, incidents
            
        except Exception as e:
            logger.error(f"Failed to fetch status: {e}")
            return "error", [], []
    
    def _extract_overall_status(self, html: str) -> str:
        """Extract overall status from page"""
        if 'no_known_issues' in html:
            return "operational"
        elif 'partial_outage' in html:
            return "partial_outage"
        elif 'major_outage' in html:
            return "major_outage"
        elif 'degraded_performance' in html:
            return "degraded"
        return "unknown"
    
    def _extract_sections(self, html: str) -> Dict[str, List[Dict]]:
        """Extract all service sections and their components"""
        import re
        
        services = re.findall(r'<p class="[^"]*_serviceName[^"]*">([^<]+)</p>', html)
        status_icons = re.findall(r'alt="([^"]+)"', html)
        
        relevant_status = [s for s in status_icons if 'icon' in s.lower()]
        
        sections = {"WhatsApp Business API": []}
        
        for i, service in enumerate(services):
            service = service.strip()
            if service and service not in ['', 'undefined']:
                status = "operational"
                if i < len(relevant_status):
                    status = self._get_status_type(relevant_status[i])
                
                sections["WhatsApp Business API"].append({
                    'name': service,
                    'status': status,
                    'status_type': status,
                    'description': None
                })
        
        return sections if sections else self._fallback_extract(html)
    
    def _get_status_type(self, status_icon: str) -> str:
        """Convert status icon alt text to status type"""
        status_lower = status_icon.lower()
        if 'no known issues' in status_lower or 'operational' in status_lower:
            return "operational"
        elif 'degraded' in status_lower:
            return "degraded_performance"
        elif 'partial' in status_lower:
            return "partial_outage"
        elif 'major' in status_lower or 'outage' in status_lower:
            return "major_outage"
        elif 'maintenance' in status_lower:
            return "under_maintenance"
        return "unknown"
    
    def _fallback_extract(self, html: str) -> Dict[str, List[Dict]]:
        """Fallback extraction if primary method fails"""
        import re
        sections = {"WhatsApp Business API": []}
        
        patterns = [
            (r'<p class="[^"]*_serviceName[^"]*">([^<]+)</p>', 'service'),
            (r'alt="([^"]*known issues[^"]*)"', 'status'),
            (r'alt="([^"]*degraded[^"]*)"', 'status'),
            (r'alt="([^"]*outage[^"]*)"', 'status'),
        ]
        
        services = re.findall(r'<p class="[^"]*_serviceName[^"]*">([^<]+)</p>', html)
        status_matches = re.findall(
            r'alt="([^"]*(?:known|degraded|outage|operational|issue)[^"]*)"',
            html,
            re.IGNORECASE
        )
        
        for i, service in enumerate(services):
            status = "operational"
            if i < len(status_matches):
                status = self._get_status_type(status_matches[i])
            
            sections["WhatsApp Business API"].append({
                'name': service.strip(),
                'status': status,
                'status_type': status,
                'description': None
            })
        
        return sections
    
    def _extract_incidents(self, html: str) -> List[Dict]:
        """Extract any active or recent incidents"""
        import re
        incidents = []
        
        incident_patterns = [
            r'<div class="[^"]*_incident[^"]*"[^>]*>(.*?)</div>',
            r'<div class="[^"]*incidentContainer[^"]*"(.*?)</div>',
        ]
        
        for pattern in incident_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title_match = re.search(r'<h[34][^>]*>([^<]+)</h[34]>', match)
                if title_match:
                    incidents.append({
                        'title': title_match.group(1).strip(),
                        'detail': match[:200]
                    })
        
        return incidents
    
    def close(self):
        """Close browser when done"""
        if self.browser:
            self.browser.close()
            self.browser = None
            self.page = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

class NotificationService:
    def __init__(self, config: Config):
        self.config = config
    
    def send_notification(self, changes: List[StatusChange], overall_change: Optional[str] = None):
        if not changes and not overall_change:
            return
        
        message = self.format_message(changes, overall_change)
        
        if self.config.terminal_notify:
            self.send_terminal(message)
        
        if self.config.mac_notify:
            self.send_mac_notification(message)
        
        if self.config.email_enabled:
            self.send_email(message, changes, overall_change)
        
        if self.config.webhook_enabled:
            self.send_webhook(message, changes, overall_change)
        
        if self.config.pushover_enabled:
            self.send_pushover(message, changes)
    
    def format_message(self, changes: List[StatusChange], overall_change: Optional[str] = None) -> str:
        lines = [
            "",
            "=" * 60,
            "🔔 WhatsApp Business API Status Change Detected",
            "=" * 60,
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"URL: https://metastatus.com/whatsapp-business-api",
            "-" * 60
        ]
        
        if overall_change:
            lines.append(f"📊 OVERALL STATUS: {overall_change}")
            lines.append("")
        
        if changes:
            lines.append(f"📋 Component Changes ({len(changes)}):")
            lines.append("")
            
            for change in changes:
                emoji = self.get_status_emoji(change.new_status)
                severity_marker = self.get_severity_marker(change.severity)
                
                lines.append(f"{emoji} {severity_marker} {change.component}")
                lines.append(f"   Status: {change.old_status} → {change.new_status}")
                
                if change.section:
                    lines.append(f"   Section: {change.section}")
                
                if change.description:
                    lines.append(f"   📝 {change.description}")
                
                lines.append(f"   ⏰ {change.timestamp}")
                lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_status_emoji(self, status: str) -> str:
        status_lower = status.lower()
        if 'operational' in status_lower or 'resolved' in status_lower:
            return "✅"
        elif 'degraded' in status_lower:
            return "⚠️"
        elif 'partial' in status_lower:
            return "🟡"
        elif 'outage' in status_lower or 'major' in status_lower:
            return "🔴"
        elif 'maintenance' in status_lower:
            return "🔧"
        else:
            return "🟠"
    
    def get_severity_marker(self, severity: str) -> str:
        markers = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '⚡',
            'low': 'ℹ️',
            'info': '📢'
        }
        return markers.get(severity, '📢')
    
    def send_terminal(self, message: str):
        print("\n" + message)
    
    def send_mac_notification(self, message: str):
        """Send macOS notification"""
        try:
            import subprocess
            lines = message.split('\n')
            title = "WhatsApp Business API Status"
            body_lines = [l for l in lines if l.strip() and not l.startswith('=') and not l.startswith('-')]
            body = '\n'.join(body_lines[:6]) if body_lines else "Status change detected"
            
            script = f'display notification "{body}" with title "{title}" sound name "default"'
            subprocess.run(['osascript', '-e', script], capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to send mac notification: {e}")
    
    def send_email(self, message: str, changes: List[StatusChange], overall_change: Optional[str]):
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            msg['Subject'] = f"⚠️ WhatsApp Business API Status - {len(changes)} change(s)"
            
            html_content = self.format_html_email(changes, overall_change)
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.email_from, self.config.email_password)
                server.send_message(msg)
            
            logger.info("Email notification sent")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def format_html_email(self, changes: List[StatusChange], overall_change: Optional[str]) -> str:
        rows = []
        for change in changes:
            color = self.get_status_color(change.new_status)
            rows.append(f"""
            <tr style="background: #{'ffebee' if 'outage' in change.new_status else 'f5f5f5'}">
                <td style="padding: 15px; border-bottom: 1px solid #ddd;">
                    <strong>{change.component}</strong>
                    {f'<br><small style="color:#666">{change.section}</small>' if change.section else ''}
                </td>
                <td style="padding: 15px; border-bottom: 1px solid #ddd; color: {self.get_status_color(change.old_status)};">
                    {change.old_status}
                </td>
                <td style="padding: 15px; border-bottom: 1px solid #ddd; color: {color}; font-weight: bold;">
                    {change.new_status}
                </td>
                <td style="padding: 15px; border-bottom: 1px solid #ddd; color: #666; font-size: 12px;">
                    {change.timestamp}
                </td>
            </tr>
            """)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5;">
            <div style="max-width: 700px; margin: 20px auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #0084ff 0%, #00a1ff 100%); padding: 25px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">🔔 WhatsApp Business API Status Change</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">
                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} • {len(changes)} change(s)
                    </p>
                </div>
                
                {f'<div style="background: #fff3cd; padding: 15px; margin: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">'
                 f'<strong>📊 Overall Status:</strong> {overall_change}</div>' if overall_change else ''}
                
                <div style="padding: 20px;">
                    <h3 style="margin-top: 0; color: #333;">Component Changes</h3>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Component</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Previous</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Current</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(rows) if rows else '<tr><td colspan="4" style="padding: 20px; text-align: center; color: #666;">No component changes</td></tr>'}
                        </tbody>
                    </table>
                </div>
                
                <div style="padding: 20px; background: #f8f9fa; border-top: 1px solid #dee2e6; border-radius: 0 0 8px 8px;">
                    <p style="margin: 0; color: #666; font-size: 12px;">
                        Source: <a href="https://metastatus.com/whatsapp-business-api" style="color: #0084ff;">metastatus.com/whatsapp-business-api</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def get_status_color(self, status: str) -> str:
        status_lower = status.lower()
        if 'operational' in status_lower:
            return "#27ae60"
        elif 'degraded' in status_lower:
            return "#f39c12"
        elif 'outage' in status_lower or 'major' in status_lower:
            return "#e74c3c"
        elif 'maintenance' in status_lower:
            return "#3498db"
        elif 'partial' in status_lower:
            return "#e67e22"
        else:
            return "#95a5a6"
    
    def send_webhook(self, message: str, changes: List[StatusChange], overall_change: Optional[str]):
        """Send webhook notification (Slack, Discord, etc.)"""
        try:
            import urllib.request
            
            color = 0x27ae60
            if overall_change:
                if 'outage' in overall_change.lower():
                    color = 0xe74c3c
                elif 'degraded' in overall_change.lower():
                    color = 0xf39c12
                elif 'partial' in overall_change.lower():
                    color = 0xe67e22
            
            fields = []
            for change in changes:
                fields.append({
                    "name": change.component,
                    "value": f"`{change.old_status}` → `{change.new_status}`",
                    "inline": True
                })
            
            payload = {
                "text": "WhatsApp Business API Status Change",
                "embeds": [{
                    "title": f"🔔 {len(changes)} Status Change(s) Detected",
                    "color": color,
                    "fields": fields[:25],
                    "footer": {
                        "text": f"metastatus.com/whatsapp-business-api • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }]
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.config.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10):
                logger.info("Webhook notification sent")
                
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
    
    def send_pushover(self, message: str, changes: List[StatusChange]):
        """Send Pushover notification"""
        try:
            import urllib.request
            
            priority = 0
            if any('outage' in c.new_status.lower() for c in changes):
                priority = 2
            
            payload = {
                'token': self.config.pushover_token,
                'user': self.config.pushover_user,
                'message': message,
                'title': 'WhatsApp Business API Status',
                'priority': priority,
                'html': 1
            }
            
            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(
                'https://api.pushover.net/1/messages.json',
                data=data
            )
            with urllib.request.urlopen(req, timeout=10):
                logger.info("Pushover notification sent")
        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")
    
    def close(self):
        """Cleanup if needed"""
        pass

class StatusMonitor:
    def __init__(self):
        self.config = Config()
        self.fetcher = StatusFetcher()
        self.notifier = NotificationService(self.config)
        self.state_file = STATE_FILE
    
    def load_last_state(self) -> MonitorState:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    return MonitorState(
                        timestamp=data.get('timestamp'),
                        components=data.get('components', {}),
                        overall_status=data.get('overall_status', 'unknown')
                    )
            except json.JSONDecodeError:
                pass
        return MonitorState(timestamp=None, components={}, overall_status="unknown")
    
    def save_current_state(self, components: List[ComponentStatus], overall_status: str):
        state = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "components": {c.name: c.status for c in components}
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def check_for_changes(
        self, 
        current_components: List[ComponentStatus], 
        overall_status: str
    ) -> Tuple[List[StatusChange], Optional[str]]:
        last_state = self.load_last_state()
        changes = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        current_dict = {c.name: c for c in current_components}
        last_components = last_state.components
        
        overall_change = None
        if last_state.overall_status and last_state.overall_status != overall_status:
            overall_change = f"{last_state.overall_status} → {overall_status}"
        
        for name, current in current_dict.items():
            old_status = last_components.get(name)
            if old_status and old_status != current.status:
                severity = self._determine_severity(old_status, current.status)
                changes.append(StatusChange(
                    component=name,
                    old_status=old_status,
                    new_status=current.status,
                    timestamp=timestamp,
                    section=current.section,
                    description=current.description,
                    severity=severity
                ))
                logger.info(f"Status change: {name}: {old_status} -> {current.status} (severity: {severity})")
        
        for name in current_dict:
            if name not in last_components:
                severity = self._determine_severity("unknown", current_dict[name].status)
                changes.append(StatusChange(
                    component=name,
                    old_status="new",
                    new_status=current_dict[name].status,
                    timestamp=timestamp,
                    section=current_dict[name].section,
                    description=current_dict[name].description,
                    severity=severity
                ))
                logger.info(f"New component: {name} ({current_dict[name].status})")
        
        for name in last_components:
            if name not in current_dict:
                changes.append(StatusChange(
                    component=name,
                    old_status=last_components[name],
                    new_status="removed",
                    timestamp=timestamp,
                    severity="low"
                ))
                logger.info(f"Component removed: {name}")
        
        return changes, overall_change
    
    def _determine_severity(self, old_status: str, new_status: str) -> str:
        """Determine the severity of a status change"""
        old_lower = old_status.lower()
        new_lower = new_status.lower()
        
        if 'outage' in new_lower or 'major' in new_lower:
            return 'critical'
        elif 'outage' in old_lower and 'operational' in new_lower:
            return 'high'
        elif 'partial' in new_lower or 'degraded' in new_lower:
            return 'high'
        elif 'operational' in new_lower and any(x in old_lower for x in ['partial', 'degraded', 'outage']):
            return 'medium'
        elif 'maintenance' in new_lower:
            return 'low'
        return 'info'
    
    def run_once(self) -> bool:
        """Run a single check"""
        overall_status, components, incidents = self.fetcher.fetch_status()
        
        if not components:
            logger.warning("No components found, might be a parsing issue")
            return False
        
        changes, overall_change = self.check_for_changes(components, overall_status)
        
        if changes or overall_change:
            self.notifier.send_notification(changes, overall_change)
            logger.info(f"Sent {len(changes)} notification(s)")
        
        self.save_current_state(components, overall_status)
        
        if incidents:
            logger.info(f"Active incidents: {len(incidents)}")
        
        return True
    
    def run_continuous(self):
        """Run continuous monitoring"""
        logger.info(f"Starting WhatsApp Business API Status Monitor")
        logger.info(f"Check interval: {self.config.check_interval} seconds")
        logger.info(f"URL: https://metastatus.com/whatsapp-business-api")
        logger.info("Press Ctrl+C to stop\n")
        
        while True:
            try:
                self.run_once()
                time.sleep(self.config.check_interval)
            except KeyboardInterrupt:
                logger.info("\nMonitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Error during check: {e}")
                time.sleep(60)
    
    def close(self):
        """Cleanup resources"""
        self.fetcher.close()
        self.notifier.close()

def interactive_setup():
    """Interactive configuration setup"""
    config = Config()
    
    print("\n" + "=" * 60)
    print("WhatsApp Business API Status Monitor - Setup")
    print("=" * 60)
    
    print("\n📋 General Settings")
    print("-" * 40)
    interval = input(f"Check interval in seconds (default: {config.check_interval}): ") or str(config.check_interval)
    config.check_interval = int(interval)
    
    print("\n📱 Notification Settings")
    print("-" * 40)
    
    print("\n1. Terminal Notifications (default: y)")
    response = input("Enable? [Y/n]: ") or "y"
    config.terminal_notify = response.lower() != 'n'
    
    print("\n2. macOS Notifications (default: y)")
    response = input("Enable? [Y/n]: ") or "y"
    config.mac_notify = response.lower() != 'n'
    
    print("\n3. Email Notifications")
    response = input("Enable? [y/N]: ") or "n"
    if response.lower() == 'y':
        config.email_enabled = True
        config.email_to = input("  To email: ")
        config.email_from = input("  From email: ")
        config.email_password = input("  App password: ")
        config.smtp_server = input(f"  SMTP server (default: {config.smtp_server}): ") or config.smtp_server
        config.smtp_port = int(input(f"  SMTP port (default: {config.smtp_port}): ") or config.smtp_port)
    
    print("\n4. Webhook Notifications (Slack/Discord)")
    response = input("Enable? [y/N]: ") or "n"
    if response.lower() == 'y':
        config.webhook_enabled = True
        config.webhook_url = input("  Webhook URL: ")
    
    print("\n5. Pushover Notifications")
    response = input("Enable? [y/N]: ") or "n"
    if response.lower() == 'y':
        config.pushover_enabled = True
        config.pushover_token = input("  App Token: ")
        config.pushover_user = input("  User Key: ")
    
    config.save()
    print("\n" + "=" * 60)
    print("✅ Configuration saved!")
    print("=" * 60)
    
    return config

if __name__ == "__main__":
    import sys
    import urllib.parse
    
    monitor = StatusMonitor()
    
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "setup":
                interactive_setup()
            elif sys.argv[1] == "once":
                monitor.run_once()
            elif sys.argv[1] == "status":
                state = monitor.load_last_state()
                print(json.dumps({
                    'timestamp': state.timestamp,
                    'overall_status': state.overall_status,
                    'components': state.components,
                    'config': {
                        'check_interval': monitor.config.check_interval,
                        'email_enabled': monitor.config.email_enabled,
                        'webhook_enabled': monitor.config.webhook_enabled,
                        'pushover_enabled': monitor.config.pushover_enabled,
                        'terminal_notify': monitor.config.terminal_notify,
                        'mac_notify': monitor.config.mac_notify
                    }
                }, indent=2))
            elif sys.argv[1] == "test":
                print("Testing notifications...")
                test_changes = [
                    StatusChange(
                        component="Cloud API",
                        old_status="operational",
                        new_status="degraded_performance",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                        section="WhatsApp Business API",
                        severity="high"
                    )
                ]
                monitor.notifier.send_notification(test_changes, "operational → degraded_performance")
                print("Test complete!")
            else:
                print(f"Usage: {sys.argv[0]} [setup|once|status|test]")
        else:
            monitor.run_continuous()
    finally:
        monitor.close()