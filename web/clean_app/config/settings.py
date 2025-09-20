# Configuration settings for clean Warehance Returns app
import os

# API Configuration
WAREHANCE_API_KEY = os.getenv("WAREHANCE_API_KEY", "dev-key-here")
WAREHANCE_BASE_URL = "https://api.warehance.com/v1"

# Database Configuration (Azure SQL only)
DATABASE_URL = os.getenv("DATABASE_URL", "mssql+pyodbc://server/database?driver=ODBC+Driver+17+for+SQL+Server")

# App Configuration
APP_VERSION = "V1.0-CLEAN"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Sync Configuration
SYNC_BATCH_SIZE = 100
REQUEST_TIMEOUT = 30

print(f"Settings loaded - Version: {APP_VERSION}")
print(f"API Key: {WAREHANCE_API_KEY[:15]}..." if WAREHANCE_API_KEY else "No API key configured")