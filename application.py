#!/usr/bin/env python
"""
APPLICATION.PY - FASTAPI ASGI with SQL FIX
THIS IS THE REAL WORKING CODE - VERSION 2025-09-10-SQL-FIX
"""
print("!!!! CRITICAL: APPLICATION.PY IS RUNNING !!!!")
print("!!!! VERSION: 2025-09-10-SQL-FIX !!!!")
print("!!!! CONFIGURING FOR UVICORN/ASGI with SQL syntax fix !!!!")

import sys
import os

# Force output to be visible
sys.stdout.flush()

# Add both current directory and web directory to path for maximum compatibility
current_dir = os.path.dirname(os.path.abspath(__file__))
web_path = os.path.join(current_dir, 'web')
sys.path.insert(0, current_dir)
sys.path.insert(0, web_path)
print(f"!!!! Added {current_dir} to path !!!!")
print(f"!!!! Added {web_path} to path !!!!")

# Show directory contents for debugging
print(f"!!!! Files in root: {os.listdir(current_dir)[:10]} !!!!")
if os.path.exists(web_path):
    print(f"!!!! Files in web: {os.listdir(web_path)[:10]} !!!!")

# Import the WORKING app with multiple fallback strategies
app = None
import_success = False

try:
    print("!!!! Strategy 1: Importing from web.app_v2 !!!!")
    from web.app_v2 import app
    import_success = True
    print("!!!! SUCCESS: web.app_v2 imported - FastAPI app exposed for ASGI !!!!")
except ImportError as e:
    print(f"!!!! Strategy 1 failed: {e} !!!!")

if not import_success:
    try:
        print("!!!! Strategy 2: Direct app_v2 import !!!!")
        import app_v2
        app = app_v2.app
        import_success = True
        print("!!!! SUCCESS: Direct app_v2 import worked !!!!")
    except ImportError as e2:
        print(f"!!!! Strategy 2 failed: {e2} !!!!")

if not import_success:
    try:
        print("!!!! Strategy 3: Importing from web directory explicitly !!!!")
        sys.path.insert(0, os.path.join(current_dir, 'web'))
        import app_v2
        app = app_v2.app
        import_success = True
        print("!!!! SUCCESS: Explicit web directory import worked !!!!")
    except ImportError as e3:
        print(f"!!!! Strategy 3 failed: {e3} !!!!")

if not import_success:
    print("!!!! ALL IMPORT STRATEGIES FAILED - Creating emergency test app !!!!")
    
    # Create a minimal working app to prove deployment works
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.get("/")
    def root():
        return {
            "status": "EMERGENCY APP RUNNING - MAIN APP IMPORT FAILED",
            "message": "Azure deployment successful but app_v2 import failed",
            "version": "2025-09-10-SQL-FIX-EMERGENCY",
            "sql_fix": "SQLite parameterized query syntax fixed (%s -> ?)",
            "instruction": "Check app_v2.py import issues",
            "paths_tried": [current_dir, web_path]
        }
    
    @app.get("/api/test")
    def test():
        return {"test": "working", "asgi": "configured", "emergency_mode": True}

# CRITICAL: Export the app object for uvicorn
# Azure should run: python -m uvicorn application:app --host 0.0.0.0 --port 8000
print("!!!! APPLICATION.PY COMPLETE - app object exported for uvicorn !!!!")
sys.stdout.flush()