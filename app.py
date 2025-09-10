"""
Root app.py - Azure default entry point with SQL fix
DEPLOYMENT VERSION: 2025-09-10-SIMPLE-FIXED-V1
"""
import sys
import os

print("=== ROOT APP.PY STARTING - VERSION 2025-09-10-SIMPLE-FIXED-V1 ===")
print("=== Loading app_v2 with SQL syntax fix ===")

# Add web directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(current_dir, 'web')
sys.path.insert(0, web_dir)
sys.path.insert(0, current_dir)

print(f"Current dir: {current_dir}")
print(f"Web dir: {web_dir}")

try:
    # Import the fixed app_v2 with SQL syntax correction
    import app_v2
    app = app_v2.app
    print("=== SUCCESS: app_v2 imported with SQL syntax fix ===")
    print("=== SQL parameterized queries fixed: %s -> ? ===")
except ImportError as e:
    print(f"=== ERROR importing app_v2: {e} ===")
    # Create emergency fallback
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/")
    def emergency():
        return {"error": f"Could not import app_v2: {e}", "version": "2025-09-10-EMERGENCY"}

print("=== Application loaded via root app.py ===")