# WhatsApp Business API Status Monitor

Monitor WhatsApp Business API status and receive email notifications when anything changes.

## How It Works

```
GitHub Actions (every 30 min)
    ↓
Fetches metastatus.com/whatsapp-business-api
    ↓
Compares with previous state
    ↓
If changed → Email notification
```

**Free, runs 24/7, no server needed**

## Setup

### 1. Add Secrets to GitHub

Go to your repo: **Settings → Secrets → Actions → New secret**

| Secret | Value |
|--------|-------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `EMAIL_FROM` | Your Gmail address |
| `EMAIL_PASSWORD` | Gmail App Password |
| `EMAIL_TO` | Email to receive alerts |

**Getting a Gmail App Password:**
1. Enable 2-Factor Authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Create a new App Password (16 characters)
4. Use that as `EMAIL_PASSWORD`

### 2. Push to GitHub

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

### 3. Enable Actions

1. Go to **Actions** tab in your repo
2. You should see the "WhatsApp Business API Status Monitor" workflow
3. Click on it and enable if needed

## Components Monitored

- Cloud API
- Cloud API - Calling
- WhatsApp Business Account Management
- Embedded Signup
- WhatsApp Flows
- Marketing Messages API for WhatsApp
- Coexistence - Messaging
- Coexistence - Onboarding

## Status Types

| Status | Meaning |
|--------|---------|
| `operational` | All good |
| `degraded` | Slow performance |
| `partial_outage` | Some issues |
| `major_outage` | Major problems |
| `maintenance` | Scheduled maintenance |

## Manual Trigger

Go to **Actions → WhatsApp Business API Status Monitor → Run workflow** to trigger manually.

## Logs

Check the Actions tab for run history and logs.