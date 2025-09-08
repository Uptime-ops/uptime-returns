# Git Deployment Guide for Azure (From OneDrive Folder)

## Important: OneDrive Considerations

Since your project is in OneDrive, follow these steps carefully to avoid sync conflicts:

## Step 1: Initialize Git in Your Current Folder

```bash
# Navigate to your project folder
cd "C:\Users\ccayo\OneDrive\Desktop\Warehance Returns"

# Initialize git
git init

# IMPORTANT: Tell OneDrive to ignore .git folder
# Right-click .git folder → "Always keep on this device" → Then "Free up space"
# This prevents OneDrive from syncing git internals
```

## Step 2: Prepare for Deployment

### Clean up local-only files:
```bash
# Remove the local SQLite database from tracking (you're using Azure SQL now)
echo "warehance_returns.db" >> .gitignore
echo "*.db" >> .gitignore

# Remove any test/temporary files
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore

# Stage all files
git add .

# Create first commit
git commit -m "Initial commit - Uptime Returns System"
```

## Step 3: Choose Deployment Method

### Option A: Direct to Azure (Simpler)

```bash
# Get your Azure Git URL from Azure Portal
# App Service → Deployment Center → Local Git → Copy Git Clone Uri

# Add Azure as remote
git remote add azure https://uptime-returns.scm.azurewebsites.net/uptime-returns.git

# Push directly to Azure
git push azure master

# Enter credentials when prompted:
# Username: $uptime-returns (from Deployment Center)
# Password: (from Deployment Center → Local Git/FTPS credentials)
```

### Option B: Via GitHub (Recommended - Better for team collaboration)

```bash
# Create a new private repository on GitHub first
# Then:

# Add GitHub remote
git remote add origin https://github.com/[your-username]/uptime-returns.git

# Push to GitHub
git push -u origin master

# Then in Azure Portal:
# 1. App Service → Deployment Center
# 2. Source: GitHub
# 3. Authorize and select your repo
# 4. Azure will auto-deploy when you push to GitHub
```

## Step 4: Important Files to Update Before Deployment

### 1. Update startup.sh (already created):
```bash
#!/bin/bash
cd /home/site/wwwroot
pip install -r requirements.txt
cd web
# Use the Azure SQL version if you created it
python enhanced_app.py  # or enhanced_app_azure_sql.py
```

### 2. Update requirements.txt to include Azure SQL dependencies:
```txt
# Add these for Azure SQL:
pyodbc==5.0.1
pymssql==2.2.11
sqlalchemy==2.0.23
```

### 3. Ensure .gitignore includes:
```
# Local database (not needed with Azure SQL)
*.db
*.db-journal
*.sqlite

# Local config
.env
.env.local

# OneDrive
.tmp.drivedownload/
~$*

# Python
__pycache__/
*.pyc
```

## Step 5: Environment Variables in Azure

Since you're using Azure SQL, make sure these are set in Azure Portal:

```
DATABASE_URL = [Your Azure SQL connection string]
AZURE_TENANT_ID = [From OAuth setup]
AZURE_CLIENT_ID = [From OAuth setup]
AZURE_CLIENT_SECRET = [From OAuth setup]
WAREHANCE_API_KEY = [Your API key]
```

## Workflow Going Forward

### For Updates:
```bash
# Make changes to your code

# Stage and commit
git add .
git commit -m "Description of changes"

# Push to Azure (or GitHub)
git push azure master  # or: git push origin master
```

### Best Practices with OneDrive:

1. **Don't sync .git folder** - Let OneDrive ignore it
2. **Use Azure SQL** - No local database files to worry about
3. **Commit frequently** - Git is your version control, not OneDrive
4. **Test locally** - But deploy to Azure for team access

## What Changes from Original Deployment Guide?

✅ **Same**: Git initialization and push process
✅ **Same**: Azure Portal configuration
❌ **Different**: No local database to worry about
❌ **Different**: Need Azure SQL connection string
✅ **Better**: No database sync issues with OneDrive

## Quick Checklist

- [ ] Git initialized in project folder
- [ ] .gitignore updated for OneDrive and Azure SQL
- [ ] Azure SQL database created
- [ ] Connection string added to Azure App Service
- [ ] Code committed to Git
- [ ] Pushed to Azure (or GitHub)
- [ ] App running at uptime-returns.azurewebsites.net

## Troubleshooting

### OneDrive Sync Issues:
- If OneDrive causes issues, pause syncing while doing Git operations
- Or move project outside OneDrive (optional)

### Database Connection Fails:
- Check firewall rules on Azure SQL
- Verify connection string in App Service Configuration
- Ensure "Allow Azure services" is enabled

### Deployment Fails:
- Check Python version (should be 3.11)
- Verify all packages in requirements.txt
- Check startup command in Azure