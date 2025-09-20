#!/usr/bin/env python3
"""
Simple runner for the clean Warehance Returns app
"""
import sys
import os

# Add the clean_app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from app import app

    print("🚀 Starting clean Warehance Returns app on port 8016...")
    print("📍 Access at: http://localhost:8016")
    print("🔗 Health check: http://localhost:8016/api/health")

    uvicorn.run(app, host="0.0.0.0", port=8016, reload=True)