# Azure App Service Deployment Guide for Uptime Returns

## Prerequisites
- Azure subscription (your existing one with Azure AD)
- Azure CLI installed locally (optional but helpful)
- Git installed locally

## Step 1: Create Azure App Service

### Via Azure Portal (Easy Method):

1. **Log in to Azure Portal**
   - Go to https://portal.azure.com
   - Sign in with your admin account

2. **Create a Resource Group** (if needed)
   - Search for "Resource groups" in the top search bar
   - Click "+ Create"
   - Name: `rg-uptime-returns`
   - Region: `East US` (or your preferred region)
   - Click "Review + create" → "Create"

3. **Create App Service Plan**
   - Search for "App Service plans" 
   - Click "+ Create"
   - Resource Group: `rg-uptime-returns`
   - Name: `asp-uptime-returns`
   - Operating System: `Linux`
   - Region: Same as resource group
   - Pricing Tier: `B1` (Basic - good for start, ~$13/month)
     - Can scale up later if needed
   - Click "Review + create" → "Create"

4. **Create Web App**
   - Search for "App Services"
   - Click "+ Create" → "Web App"
   - Fill in:
     - Resource Group: `rg-uptime-returns`
     - Name: `uptime-returns` (URL will be uptime-returns.azurewebsites.net)
     - Publish: `Code`
     - Runtime stack: `Python 3.11`
     - Operating System: `Linux`
     - Region: Same as resource group
     - App Service Plan: `asp-uptime-returns` (the one you created)
   - Click "Next: Deployment" → Skip
   - Click "Next: Networking" → Skip  
   - Click "Next: Monitoring" → Skip
   - Click "Review + create" → "Create"

## Step 2: Configure Application Settings

1. **Navigate to your App Service**
   - Go to App Services → `uptime-returns`

2. **Add Environment Variables**
   - In left menu, under "Settings", click "Configuration"
   - Click "New application setting" for each:

   ```
   Name: AZURE_TENANT_ID
   Value: [Your Tenant ID from OAuth setup]
   
   Name: AZURE_CLIENT_ID
   Value: [Your Client ID from OAuth setup]
   
   Name: AZURE_CLIENT_SECRET
   Value: [Your Client Secret from OAuth setup]
   
   Name: WAREHANCE_API_KEY
   Value: [Your Warehance API key]
   
   Name: DATABASE_PATH
   Value: /home/warehance_returns.db
   
   Name: PORT
   Value: 8000
   
   Name: WEBSITES_PORT
   Value: 8015
   
   Name: SCM_DO_BUILD_DURING_DEPLOYMENT
   Value: true
   
   Name: WEBSITE_WEBDEPLOY_USE_SCM
   Value: true
   ```
   
   - Click "Save" at the top
   - Click "Continue" when prompted

3. **Configure Startup Command**
   - Still in Configuration
   - Go to "General settings" tab
   - Startup Command: `cd web && python enhanced_app.py`
   - Click "Save"

## Step 3: Prepare Your Code for Deployment

1. **Create Azure-specific files in your project root:**

### Create `.deployment` file:
```ini
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT = true
command = deploy.cmd
```

### Create `deploy.cmd` file:
```batch
@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Starting application...
cd web
python enhanced_app.py
```

### Create `startup.sh` file (for Linux):
```bash
#!/bin/bash
cd /home/site/wwwroot
pip install -r requirements.txt
cd web
python enhanced_app.py
```

### Update `requirements.txt` (already created):
Make sure it includes all dependencies

### Create `.gitignore`:
```
*.pyc
__pycache__/
venv/
.env
*.db-journal
logs/
```

## Step 4: Deploy Using Git

### Option A: Deploy from Local Git

1. **Initialize Git repository** (if not already done):
```bash
cd "C:\Users\ccayo\OneDrive\Desktop\Warehance Returns"
git init
git add .
git commit -m "Initial commit for Azure deployment"
```

2. **Get deployment credentials**:
   - In Azure Portal, go to your App Service
   - Left menu → "Deployment Center"
   - Click "Local Git" 
   - Click "Save"
   - Go to "Local Git/FTPS credentials" tab
   - Copy the Git Clone Uri (like: https://uptime-returns.scm.azurewebsites.net/uptime-returns.git)
   - Note the username (like: $uptime-returns)

3. **Add Azure remote and push**:
```bash
git remote add azure https://uptime-returns.scm.azurewebsites.net/uptime-returns.git
git push azure master
```
   - Enter the password from deployment credentials when prompted

### Option B: Deploy from GitHub (Recommended)

1. **Create GitHub repository**:
   - Go to https://github.com/new
   - Name: `uptime-returns`
   - Private repository: Yes
   - Create repository

2. **Push code to GitHub**:
```bash
git remote add origin https://github.com/yourusername/uptime-returns.git
git branch -M main
git push -u origin main
```

3. **Connect Azure to GitHub**:
   - In Azure Portal, go to your App Service
   - Left menu → "Deployment Center"
   - Source: "GitHub"
   - Authorize Azure to access GitHub
   - Organization: Your GitHub username
   - Repository: `uptime-returns`
   - Branch: `main`
   - Click "Save"

## Step 5: Configure Custom Domain (returns.uptimeops.net)

1. **In Azure Portal**:
   - Go to your App Service
   - Left menu → "Custom domains"
   - Click "+ Add custom domain"
   - Custom domain: `returns.uptimeops.net`
   - Validate → You'll see DNS records needed

2. **Add DNS Records** (at your DNS provider):
   
   **Option 1 - CNAME (Easier)**:
   ```
   Type: CNAME
   Name: returns
   Value: uptime-returns.azurewebsites.net
   TTL: 3600
   ```
   
   **Option 2 - A Record**:
   ```
   Type: A
   Name: returns
   Value: [IP shown in Azure Portal]
   TTL: 3600
   ```
   
   And also add:
   ```
   Type: TXT
   Name: asuid.returns
   Value: [Verification ID from Azure]
   TTL: 3600
   ```

3. **Verify and Add**:
   - Back in Azure Portal
   - Click "Validate" again
   - Once validated, click "Add"

4. **Enable HTTPS**:
   - Still in Custom domains
   - Next to returns.uptimeops.net
   - HTTPS Only: "On"
   - TLS/SSL certificate: Click "Add certificate"
   - Choose "Create App Service Managed Certificate" (Free!)
   - Click "Create"

## Step 6: Update Application Code for Azure

Update `enhanced_app.py` to use environment variables:

```python
import os
from pathlib import Path

# Get configuration from environment variables
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET', '')
WAREHANCE_API_KEY = os.getenv('WAREHANCE_API_KEY', '')

# Database path
if os.getenv('WEBSITE_INSTANCE_ID'):  # Running in Azure
    DATABASE_PATH = '/home/warehance_returns.db'
else:  # Running locally
    DATABASE_PATH = '../warehance_returns.db'

# Update database connections to use DATABASE_PATH
conn = sqlite3.connect(DATABASE_PATH)

# Update the port
if __name__ == "__main__":
    port = int(os.getenv('PORT', 8015))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

## Step 7: Enable Application Logging

1. **In Azure Portal**:
   - Go to your App Service
   - Left menu → "App Service logs"
   - Application Logging (Filesystem): "On"
   - Level: "Information"
   - Click "Save"

2. **View logs**:
   - Left menu → "Log stream"
   - You'll see real-time logs here

## Step 8: Add Authentication (Optional but Recommended)

### Option A: Azure AD Authentication (Best for your team)

1. **In Azure Portal**:
   - Go to your App Service
   - Left menu → "Authentication"
   - Click "Add identity provider"
   - Choose "Microsoft"
   - Configure:
     - Name: `Uptime Returns Auth`
     - Supported account types: "Current tenant - Single tenant"
     - Redirect URI: Will be auto-populated
   - Permissions: Leave defaults
   - Click "Add"

2. **Restrict access**:
   - Authentication settings:
     - Require authentication: "Yes"
     - Unauthenticated requests: "HTTP 302 Found redirect"
     - Redirect to: "Microsoft"
   - Click "Save"

Now only users with @uptimeops.net accounts can access the app!

### Option B: Basic Authentication (Quick setup)

Add to your code (I can help implement this).

## Step 9: Database Persistence

Azure App Service storage is temporary. For persistent database:

### Option 1: Azure Storage Mount (Recommended)
1. Create Azure Storage Account
2. Create a File Share
3. Mount it to your App Service at `/home/data`
4. Update DATABASE_PATH to `/home/data/warehance_returns.db`

### Option 2: Use Azure SQL Database
1. Migrate from SQLite to Azure SQL
2. More scalable but requires code changes

## Step 10: Monitor and Scale

1. **Set up Monitoring**:
   - Left menu → "Application Insights"
   - Enable Application Insights
   - This gives you performance monitoring, error tracking, etc.

2. **Set up Alerts**:
   - Left menu → "Alerts"
   - Create alerts for:
     - High response time
     - Errors
     - Availability

3. **Scale if needed**:
   - Left menu → "Scale up (App Service plan)"
   - Choose higher tier if you need more performance

## Troubleshooting

### If deployment fails:
1. Check "Deployment Center" → "Logs"
2. Check "Log stream" for runtime errors
3. Use "Console" to debug:
   - Left menu → "Development Tools" → "Console"
   - You can run commands here

### Common issues:
- **Module not found**: Check requirements.txt
- **Port binding**: Make sure using PORT env variable
- **Database errors**: Check DATABASE_PATH and permissions

## Quick Commands

### Restart app:
```
In Azure Portal → Overview → Restart
```

### View logs:
```
In Azure Portal → Log stream
```

### SSH into container:
```
In Azure Portal → Development Tools → SSH
```

## Costs

- **B1 App Service Plan**: ~$13/month
- **Custom domain SSL**: Free with App Service
- **Storage (if used)**: ~$1/month for 10GB
- **Total**: ~$14-15/month

## Success Checklist

- [ ] App Service created
- [ ] Environment variables configured
- [ ] Code deployed successfully
- [ ] Custom domain configured
- [ ] SSL certificate active
- [ ] Authentication enabled
- [ ] Application running at https://returns.uptimeops.net

## Next Steps

1. Test the deployment at https://uptime-returns.azurewebsites.net
2. Configure custom domain DNS
3. Enable authentication
4. Share with your team!