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

# Navigate to root directory where application.py is
cd /home/site/wwwroot

# Start the application with uvicorn for FastAPI ASGI support
echo "Starting FastAPI application with uvicorn..."
echo "Using application.py which imports app_v2"
python -m uvicorn application:app --host 0.0.0.0 --port 8000