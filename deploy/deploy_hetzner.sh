#!/bin/bash
# Quantum Retail Terminal — Hetzner / Generic VPS (Ubuntu/Debian) Setup
# Run as: sudo bash deploy_hetzner.sh

set -e

echo "=== Quantum Retail Terminal — VPS Setup ==="

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3.11 python3.11-venv python3.11-dev git curl ufw

# If python3.11 not available from default repos, add deadsnakes
if ! command -v python3.11 &> /dev/null; then
    echo "Python 3.11 not found in default repos, adding deadsnakes PPA..."
    apt install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    apt install -y python3.11 python3.11-venv python3.11-dev
fi

# Create app user
useradd -m -s /bin/bash quantum || true

# Clone repo
su - quantum -c "git clone https://github.com/carlos060798/terminal-de-inverisones-y-trading.git app"

# Create virtual environment and install dependencies
su - quantum -c "cd app && python3.11 -m venv venv"
su - quantum -c "cd app && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# Create secrets file
mkdir -p /home/quantum/app/.streamlit
cat > /home/quantum/app/.streamlit/secrets.toml << 'SECRETS'
# ADD YOUR API KEYS HERE
FRED_API_KEY = ""
GROQ_API_KEY = ""
OPENROUTER_API_KEY = ""
GEMINI_API_KEY = ""
SECRETS
chown -R quantum:quantum /home/quantum/app

# Create systemd service
cat > /etc/systemd/system/quantum-terminal.service << 'SERVICE'
[Unit]
Description=Quantum Retail Terminal
After=network.target

[Service]
Type=simple
User=quantum
WorkingDirectory=/home/quantum/app
ExecStart=/home/quantum/app/venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

# Enable and start service
systemctl daemon-reload
systemctl enable quantum-terminal
systemctl start quantum-terminal

# Configure UFW firewall
ufw allow 22/tcp
ufw allow 8501/tcp
ufw --force enable

echo ""
echo "=== SETUP COMPLETE ==="
echo "Your terminal is running at: http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo "IMPORTANT: Edit your API keys at:"
echo "  /home/quantum/app/.streamlit/secrets.toml"
echo ""
echo "Commands:"
echo "  sudo systemctl status quantum-terminal"
echo "  sudo systemctl restart quantum-terminal"
echo "  sudo journalctl -u quantum-terminal -f"
echo ""
echo "Optional — Set up Nginx reverse proxy + SSL:"
echo "  apt install -y nginx certbot python3-certbot-nginx"
echo "  # Configure Nginx, then: certbot --nginx -d yourdomain.com"
