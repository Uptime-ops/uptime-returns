# Configuration settings for clean Warehance Returns app
import os

# API Configuration - same as old app
WAREHANCE_API_KEY = os.getenv('WAREHANCE_API_KEY')
if not WAREHANCE_API_KEY:
    raise ValueError("WAREHANCE_API_KEY environment variable must be set. Please configure it in Azure App Service Application Settings.")

WAREHANCE_BASE_URL = "https://api.warehance.com/v1"

# Database Configuration (Azure SQL only)
DATABASE_URL = os.getenv("DATABASE_URL", "mssql+pyodbc://server/database?driver=ODBC+Driver+17+for+SQL+Server")

# App Configuration
APP_VERSION = "V1.6-CLEAN-DEBUG-LOGS"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Sync Configuration
SYNC_BATCH_SIZE = 100
REQUEST_TIMEOUT = 30

print(f"Settings loaded - Version: {APP_VERSION}")
print(f"API Key: {WAREHANCE_API_KEY[:15]}..." if WAREHANCE_API_KEY else "No API key configured")