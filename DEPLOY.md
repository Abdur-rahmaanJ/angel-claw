# 🪽 Angel Claw Deployment Guide (Pro Package Mode)

This guide assumes you have installed `angel-claw` as a package (e.g., via `pip install .` or from a wheel).

## 1. Professional Data Architecture
Unlike development mode, Angel Claw in production stores all persistent data in a standardized user directory:
*   **Database**: `~/.angelclaw/angelclaw.db`
*   **Memory/Vaults**: `~/.angelclaw/vaults/`
*   **Bridge Pairings**: `~/.angelclaw/bridges/`

This allows you to update the package code without ever touching your users' data.

## 2. Systemd Service Templates

### Web Service (`/etc/systemd/system/angel-claw-web.service`)
```ini
[Unit]
Description=🪽 Angel Claw Web UI
After=network.target

[Service]
User=appinv
Group=www-data
# No need to be in a specific directory!
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "angel_claw.app.app:create_app('production')"
Restart=always
Environment="USER_DATA_ROOT=/home/appinv/.angelclaw"

[Install]
WantedBy=multi-user.target
```

### Bridge Worker (`/etc/systemd/system/angel-claw-bridge.service`)
**CRITICAL**: Only run ONE instance.
```ini
[Unit]
Description=🪽 Angel Claw Bridge Worker
After=network.target angel-claw-web.service

[Service]
User=appinv
Group=appinv
ExecStart=/path/to/venv/bin/angel-claw bridges
Restart=always
Environment="USER_DATA_ROOT=/home/appinv/.angelclaw"

[Install]
WantedBy=multi-user.target
```

## 3. Nginx Configuration
Since the static files are inside the package, use our helper command to find the path for your Nginx `alias`:
```bash
angel-claw locate-static
# Example Output: /path/to/venv/lib/python3.12/site-packages/angel_claw/app/static
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }

    # Use the output from 'angel-claw locate-static' here:
    location /static/ {
        alias /path/to/your/static/folder/;
    }
}
```

## 4. Production Management
```bash
# To sync/seed the database manually in production:
# (Uses your environment variables to create the admin user)
angel-claw serve --sync # Then Ctrl+C after it finishes syncing

# Standard service management
sudo systemctl daemon-reload
sudo systemctl enable --now angel-claw-web angel-claw-bridge
```
