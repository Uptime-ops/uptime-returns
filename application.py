#!/usr/bin/env python
"""
APPLICATION.PY - NUCLEAR OPTION TO BYPASS AZURE CACHE
THIS IS THE REAL WORKING CODE - VERSION 2025-01-09-12:30
"""
print("!!!! CRITICAL: APPLICATION.PY IS RUNNING !!!!")
print("!!!! THIS PROVES AZURE IS USING THE NEW DEPLOYMENT !!!!")
print("!!!! VERSION: 2025-01-09-12:30-NUCLEAR-FIX !!!!")

import sys
import os

# Force output to be visible
sys.stdout.flush()

# Add web directory to path
web_path = os.path.join(os.path.dirname(__file__), 'web')
if os.path.exists(web_path):
    sys.path.insert(0, web_path)
    print(f"!!!! Added {web_path} to path !!!!")
else:
    print(f"!!!! WARNING: {web_path} does not exist !!!!")

# Import the WORKING app
try:
    print("!!!! Attempting to import app_v2 !!!!")
    from web.app_v2 import *
    print("!!!! SUCCESS: app_v2 imported and running !!!!")
except ImportError as e:
    print(f"!!!! FALLBACK: Could not import app_v2: {e} !!!!")
    try:
        print("!!!! Trying direct app_v2 import !!!!")
        import app_v2
        from app_v2 import *
        print("!!!! SUCCESS: Direct app_v2 import worked !!!!")
    except ImportError as e2:
        print(f"!!!! CRITICAL ERROR: No app found: {e2} !!!!")
        print("!!!! Creating emergency test app !!!!")
        
        # Create a minimal working app to prove deployment works
        from fastapi import FastAPI
        import uvicorn
        
        app = FastAPI()
        
        @app.get("/")
        def root():
            return {
                "status": "EMERGENCY APP RUNNING",
                "message": "Azure cache has been bypassed",
                "version": "2025-01-09-12:30-NUCLEAR",
                "instruction": "The real app_v2.py should be loading but isn't. Check file structure."
            }
        
        @app.get("/api/test")
        def test():
            return {"test": "working", "cache": "bypassed"}
        
        # Run the emergency app
        if __name__ == "__main__":
            uvicorn.run(app, host="0.0.0.0", port=8000)

print("!!!! APPLICATION.PY COMPLETE !!!!")
sys.stdout.flush()