# Deployment Guide for returns.uptimeops.net

## Overview
This guide will help you deploy the Uptime Returns system to be accessible at returns.uptimeops.net for your team.

## Deployment Options

### Option 1: Windows Server with IIS (If you have Windows infrastructure)

#### Requirements:
- Windows Server 2016 or later
- IIS with URL Rewrite module
- Python 3.11+

#### Steps:
1. **Install Python and dependencies**
```powershell
# Install Python from python.org
# Install required packages
cd "C:\inetpub\wwwroot\uptime-returns"
pip install -r requirements.txt
```

2. **Configure IIS**
- Install URL Rewrite and Application Request Routing (ARR)
- Create a new site pointing to returns.uptimeops.net
- Set up reverse proxy to localhost:8015

3. **Create Windows Service**
Use NSSM to run the app as a service:
```powershell
nssm install UptimeReturns "C:\Python311\python.exe" "C:\inetpub\wwwroot\uptime-returns\web\enhanced_app.py"
nssm start UptimeReturns
```

### Option 2: Linux Server with Nginx (Recommended for production)

#### Requirements:
- Ubuntu 20.04+ or similar Linux distribution
- Nginx
- Python 3.11+
- SSL certificate for returns.uptimeops.net

#### Steps:

1. **Transfer files to server**
```bash
# On your server, create directory
sudo mkdir -p /var/www/uptime-returns
sudo chown -R $USER:$USER /var/www/uptime-returns

# Copy files (from your local machine)
scp -r "C:\Users\ccayo\OneDrive\Desktop\Warehance Returns\*" user@yourserver:/var/www/uptime-returns/
```

2. **Install dependencies**
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx
cd /var/www/uptime-returns
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlite3 msal requests
```

3. **Create systemd service**
```bash
sudo nano /etc/systemd/system/uptime-returns.service
```

Add:
```ini
[Unit]
Description=Uptime Returns Management System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/uptime-returns/web
Environment="PATH=/var/www/uptime-returns/venv/bin"
ExecStart=/var/www/uptime-returns/venv/bin/python enhanced_app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

4. **Configure Nginx**
```bash
sudo nano /etc/nginx/sites-available/returns.uptimeops.net
```

Add:
```nginx
server {
    listen 80;
    server_name returns.uptimeops.net;

    location / {
        proxy_pass http://127.0.0.1:8015;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

5. **Enable site and start services**
```bash
sudo ln -s /etc/nginx/sites-available/returns.uptimeops.net /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable uptime-returns
sudo systemctl start uptime-returns
```

6. **Set up SSL with Let's Encrypt**
```bash
sudo certbot --nginx -d returns.uptimeops.net
```

### Option 3: Cloud Hosting (Azure App Service)

Since you're already using Azure AD, Azure App Service would be a natural fit:

1. **Create Azure App Service**
   - Go to Azure Portal
   - Create new App Service
   - Choose Python 3.11 runtime
   - Set custom domain: returns.uptimeops.net

2. **Deploy via Git**
```bash
git init
git add .
git commit -m "Initial deployment"
git remote add azure https://uptime-returns.scm.azurewebsites.net/uptime-returns.git
git push azure master
```

3. **Configure App Settings**
   - Add environment variables for OAuth credentials
   - Set startup command: `python web/enhanced_app.py`

## DNS Configuration

Add these DNS records at your domain provider:

### For Option 1 & 2 (Self-hosted):
```
Type: A
Name: returns
Value: [Your server's public IP]
TTL: 3600
```

### For Option 3 (Azure):
```
Type: CNAME
Name: returns
Value: uptime-returns.azurewebsites.net
TTL: 3600
```

## Security Considerations

1. **Firewall Rules**
   - Open port 443 (HTTPS) to public
   - Open port 80 (HTTP) for redirect only
   - Close port 8015 to external access

2. **Application Security**
   - Move sensitive configs to environment variables
   - Enable HTTPS only
   - Add authentication for team access

3. **Database Backup**
   - Set up daily backups of warehance_returns.db
   - Store backups in secure location

## Team Access Control

### Add Basic Authentication (Quick Solution):

1. **Install authentication package**
```bash
pip install python-multipart python-jose[cryptography] passlib[bcrypt]
```

2. **Add to enhanced_app.py** (I can help implement this):
- User login system
- Session management
- Team member management

### Or Use Azure AD (Recommended):

Since you have Azure AD, you can use it for SSO:
- Configure Azure AD authentication
- Only allow @uptimeops.net emails
- Automatic team access management

## Environment Variables

Create `.env` file for production:
```env
# OAuth Settings
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# App Settings
APP_URL=https://returns.uptimeops.net
DATABASE_PATH=/var/www/uptime-returns/warehance_returns.db

# Warehance API
WAREHANCE_API_KEY=your-api-key
```

## Monitoring

1. **Application Monitoring**
```bash
# Check service status
sudo systemctl status uptime-returns

# View logs
sudo journalctl -u uptime-returns -f
```

2. **Set up alerts**
   - Use Azure Monitor if using Azure
   - Or set up Uptime Robot for basic monitoring

## Quick Start Commands

### Start the application:
```bash
sudo systemctl start uptime-returns
```

### Stop the application:
```bash
sudo systemctl stop uptime-returns
```

### Restart after changes:
```bash
sudo systemctl restart uptime-returns
```

### View logs:
```bash
tail -f /var/log/uptime-returns.log
```

## Next Steps

1. Choose your deployment option
2. Set up DNS records
3. Configure SSL certificate
4. Add team authentication
5. Test with your team

Would you like me to:
1. Help implement user authentication?
2. Create Azure deployment scripts?
3. Set up a specific deployment option?