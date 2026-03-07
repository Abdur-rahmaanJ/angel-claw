# Production Deployment Guide

This document provides guidelines for deploying Angel Claw in a production environment.

---

## 1. Architecture Overview

For production, we recommend separating the **Web UI** from the **Bridge Worker** to ensure stability and independent scaling.

- **Web Server**: Handles the Dashboard and API requests.
- **Bridge Worker**: Manages Telegram, WhatsApp, and Cron jobs.
- **Persistence Layer**: Shared filesystem or S3-compatible storage for user roots.

## 2. Recommended Stack

- **OS**: Ubuntu 22.04+ or Amazon Linux 2023.
- **Python**: 3.10+
- **Process Manager**: Systemd or Supervisor.
- **Reverse Proxy**: Nginx with SSL (Certbot/Let's Encrypt).
- **Database**: PostgreSQL (Recommended for Shopyo identity) + SQLite (per-user history).

## 3. Environment Hardening

Ensure the following variables are set in your production `.env`:

```env
# Disable Debug Mode
DEBUG=False

# Generate a strong salt for the Vault
ANGEL_CLAW_VAULT_SALT=your-long-random-salt

# Enforce secure webhook triggers
WEBHOOK_KEY=your-secure-webhook-key

# Enable Docker Sandboxing (Recommended for public SaaS)
DOCKER_SANDBOXING_ENABLED=True
DOCKER_RUNTIME=runsc
```

## 4. Systemd Service Templates

### Web Gateway (`angel-claw-web.service`)
```ini
[Unit]
Description=Angel Claw Web Gateway
After=network.target

[Service]
User=angelclaw
Group=angelclaw
WorkingDirectory=/opt/angel-claw
Environment=PYTHONPATH=/opt/angel-claw/src
ExecStart=/opt/angel-claw/.venv/bin/angel-claw serve --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
```

### Bridge Worker (`angel-claw-worker.service`)
```ini
[Unit]
Description=Angel Claw Bridge Worker
After=network.target

[Service]
User=angelclaw
Group=angelclaw
WorkingDirectory=/opt/angel-claw
Environment=PYTHONPATH=/opt/angel-claw/src
ExecStart=/opt/angel-claw/.venv/bin/angel-claw bridges
Restart=always

[Install]
WantedBy=multi-user.target
```

## 5. Security Checklist

1.  [ ] **Firewall**: Restrict port 5000 to Nginx (localhost) only.
2.  [ ] **SSL**: Always run the Gateway behind HTTPS.
3.  [ ] **User Permissions**: Run the service under a dedicated low-privilege user.
4.  [ ] **Backups**: Implement daily snapshots of the `~/.angelclaw` directory.
5.  [ ] **Sandboxing**: Install `gvisor` and configure Docker to use the `runsc` runtime.
