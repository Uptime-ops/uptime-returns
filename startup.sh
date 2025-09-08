#!/bin/bash

echo "Starting Uptime Returns application..."

# Navigate to the application directory
cd /home/site/wwwroot

# Install Python dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Navigate to web directory
cd web

# Start the application
echo "Starting FastAPI application..."
python enhanced_app.py