#!/bin/bash

echo "Starting Uptime Returns application..."

# First, install ODBC drivers if needed
echo "Checking ODBC drivers..."
if [ -f /home/site/wwwroot/install_odbc.sh ]; then
    chmod +x /home/site/wwwroot/install_odbc.sh
    /home/site/wwwroot/install_odbc.sh
else
    echo "install_odbc.sh not found, skipping ODBC installation"
fi

# Navigate to web directory where the app is
cd /home/site/wwwroot/web

# Start the application directly (dependencies should be pre-installed during build)
echo "Starting FastAPI application..."
echo "Using app_v2.py to force Azure to use updated code"
python app_v2.py