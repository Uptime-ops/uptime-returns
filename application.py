#!/usr/bin/env python
"""
APPLICATION.PY - FASTAPI ASGI FIX
THIS IS THE REAL WORKING CODE - VERSION 2025-01-09-ASGI-FIX
"""
print("!!!! CRITICAL: APPLICATION.PY IS RUNNING !!!!")
print("!!!! VERSION: 2025-01-09-ASGI-FIX !!!!")
print("!!!! CONFIGURING FOR UVICORN/ASGI !!!!")

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
    from web.app_v2 import app
    print("!!!! SUCCESS: app_v2 imported - FastAPI app exposed for ASGI !!!!")
except ImportError as e:
    print(f"!!!! FALLBACK: Could not import app_v2: {e} !!!!")
    try:
        print("!!!! Trying direct app_v2 import !!!!")
        import app_v2
        app = app_v2.app
        print("!!!! SUCCESS: Direct app_v2 import worked !!!!")
    except ImportError as e2:
        print(f"!!!! CRITICAL ERROR: No app found: {e2} !!!!")
        print("!!!! Creating emergency test app !!!!")
        
        # Create a minimal working app to prove deployment works
        from fastapi import FastAPI
        
        app = FastAPI()
        
        @app.get("/")
        def root():
            return {
                "status": "EMERGENCY APP RUNNING",
                "message": "Azure needs uvicorn for FastAPI",
                "version": "2025-01-09-ASGI-FIX",
                "instruction": "Set startup command: python -m uvicorn application:app --host 0.0.0.0 --port 8000"
            }
        
        @app.get("/api/test")
        def test():
            return {"test": "working", "asgi": "configured"}

# CRITICAL: Export the app object for uvicorn
# Azure should run: python -m uvicorn application:app --host 0.0.0.0 --port 8000
print("!!!! APPLICATION.PY COMPLETE - app object exported for uvicorn !!!!")
sys.stdout.flush()