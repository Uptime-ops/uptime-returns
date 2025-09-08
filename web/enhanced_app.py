"""
REDIRECT TO APP_V2.PY - Azure is caching this file
"""
import sys
import os

print("=== ENHANCED_APP.PY REDIRECT ===")
print("=== Azure is caching this file - redirecting to app_v2.py ===")

# Import and run app_v2 instead
from app_v2 import *

# This ensures that when Azure runs enhanced_app.py, it actually runs app_v2.py code
print("=== Now running app_v2.py code through enhanced_app.py ===")