#!/bin/bash

echo "Starting Uptime Returns application..."

# Navigate to web directory where the app is
cd /home/site/wwwroot/web

# Start the application directly (dependencies should be pre-installed during build)
echo "Starting FastAPI application..."
python enhanced_app.py