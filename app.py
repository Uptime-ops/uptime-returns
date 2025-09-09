"""
Root app.py - Azure default entry point
Redirects to the actual application
"""
import sys
import os

print("=== ROOT APP.PY STARTING ===")
print("=== Redirecting to web/app_v2.py ===")

# Add web directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))

# Import and run the actual app
from web.app_v2 import *

print("=== Application started via root app.py ===")