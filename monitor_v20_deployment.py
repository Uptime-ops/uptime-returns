#!/usr/bin/env python3
"""
V20 Dashboard Stats Debug Deployment Monitor
"""

import requests
import json
import time
from datetime import datetime

AZURE_URL = "https://uptime-returns-adc7ath0dccye4bh.eastus2-01.azurewebsites.net"

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def wait_for_v20_deployment():
    """Wait for V20 to deploy"""
    log("=== WAITING FOR V20 DEPLOYMENT ===")
    
    max_checks = 20
    for i in range(max_checks):
        try:
            response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
            if response.status_code == 200:
                data = response.json()
                version = data.get("deployment_version", "Unknown")
                log(f"Check {i+1}/{max_checks}: Current version = {version}")
                
                if "V20" in version:
                    log("SUCCESS: V20 DEPLOYMENT DETECTED!")
                    return True
            else:
                log(f"Check {i+1}/{max_checks}: Service error {response.status_code}")
        except Exception as e:
            log(f"Check {i+1}/{max_checks}: Connection error - {str(e)[:50]}")
        
        if i < max_checks - 1:
            time.sleep(30)  # Wait 30 seconds between checks
    
    log("WARNING: V20 not detected within time limit")
    return False

def test_v20_dashboard_debugging():
    """Test the V20 dashboard debugging"""
    log("=== TESTING V20 DASHBOARD DEBUGGING ===")
    
    # Test dashboard stats with debugging
    try:
        log("Testing dashboard stats with V20 debugging...")
        response = requests.get(f"{AZURE_URL}/api/dashboard/stats", timeout=30)
        log(f"Dashboard stats: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            error = data.get("error")
            
            log(f"Stats returned: {stats}")
            log(f"Total returns: {stats.get('total_returns', 'MISSING')}")
            log(f"Debug error: {error}")
            
            if 'count_error' in stats:
                log(f"COUNT query error: {stats['count_error']}")
            
            if stats.get('total_returns', 0) > 0:
                log("SUCCESS: Dashboard stats now showing returns!")
                return True
            else:
                log("Dashboard still showing 0 returns - need to check Azure logs")
                return False
        else:
            log(f"Dashboard error: {response.status_code} - {response.text[:200]}")
            return False
            
    except Exception as e:
        log(f"Dashboard test error: {e}")
        return False

def main():
    """Main monitoring function"""
    log("=== V20 DASHBOARD DEBUG DEPLOYMENT MONITOR ===")
    
    # Step 1: Wait for V20 deployment
    if not wait_for_v20_deployment():
        log("FAILED: V20 deployment not detected")
        return
    
    # Step 2: Test dashboard debugging
    if test_v20_dashboard_debugging():
        log("SUCCESS: V20 dashboard debugging working!")
    else:
        log("Need to check Azure App Service logs for detailed debugging output")
    
    log("=== V20 MONITORING COMPLETE ===")

if __name__ == "__main__":
    main()