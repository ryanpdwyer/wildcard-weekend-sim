# Wildcard Weekend 2026 - Win Probability Simulator

Monte Carlo simulation for fantasy football wildcard weekend contest.

## Features

- Real-time win probability calculation (10,000 simulations)
- Live ESPN data integration
- Teased betting lines based on draft round
- Excel-inspired spreadsheet UI
- Demo mode for testing (`?demo=1`)

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5050

## Server Deployment (nginx + gunicorn)

### 1. Clone and setup

```bash
cd /var/www
git clone https://github.com/ryanpdwyer/wildcard-weekend-sim.git
cd wildcard-weekend-sim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create systemd service

Create `/etc/systemd/system/wildcard-sim.service`:

```ini
[Unit]
Description=Wildcard Weekend Simulator
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/wildcard-weekend-sim
ExecStart=/var/www/wildcard-weekend-sim/.venv/bin/gunicorn app:app --bind 127.0.0.1:5050 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wildcard-sim
sudo systemctl start wildcard-sim
```

Check status:

```bash
sudo systemctl status wildcard-sim
sudo journalctl -u wildcard-sim -f  # view logs
```

### 3. Configure nginx (path-based routing)

Add to your existing nginx site config:

```nginx
location /wildcard/ {
    proxy_pass http://127.0.0.1:5050/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /wildcard;
}
```

Reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Access at: `https://yourdomain.com/wildcard/`

### 4. Updating

```bash
cd /var/www/wildcard-weekend-sim
git pull
sudo systemctl restart wildcard-sim
```
