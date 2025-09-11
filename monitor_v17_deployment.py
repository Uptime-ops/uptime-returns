#!/usr/bin/env python3
"""
V17 Deployment Monitoring and Sync Testing
Focus on verifying the critical parameterization fixes
"""

import requests
import json
import time
from datetime import datetime

AZURE_URL = "https://uptime-returns-adc7ath0dccye4bh.eastus2-01.azurewebsites.net"

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def wait_for_v17_deployment():
    """Wait for V17 to deploy"""
    log("=== WAITING FOR V17 DEPLOYMENT ===")
    
    max_checks = 20
    for i in range(max_checks):
        try:
            response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
            if response.status_code == 200:
                data = response.json()
                version = data.get("deployment_version", "Unknown")
                log(f"Check {i+1}/{max_checks}: Current version = {version}")
                
                if "V17" in version:
                    log("SUCCESS: V17 DEPLOYMENT DETECTED!")
                    return True
            else:
                log(f"Check {i+1}/{max_checks}: Service error {response.status_code}")
        except Exception as e:
            log(f"Check {i+1}/{max_checks}: Connection error - {str(e)[:50]}")
        
        if i < max_checks - 1:
            time.sleep(30)  # Wait 30 seconds between checks
    
    log("WARNING: V17 not detected within time limit")
    return False

def test_v17_sync():
    """Test the sync functionality with V17"""
    log("=== TESTING V17 SYNC FUNCTIONALITY ===")
    
    # Get initial database state
    try:
        response = requests.get(f"{AZURE_URL}/api/dashboard/stats", timeout=30)
        if response.status_code == 200:
            data = response.json()
            initial_returns = data.get("stats", {}).get("total_returns", 0)
            log(f"Initial returns count: {initial_returns}")
        else:
            initial_returns = 0
            log("Could not get initial stats")
    except Exception as e:
        initial_returns = 0
        log(f"Initial stats error: {e}")
    
    # Test Warehance API connectivity first
    log("Testing Warehance API connectivity...")
    try:
        response = requests.get(f"{AZURE_URL}/api/test-warehance", timeout=30)
        if response.status_code == 200:
            data = response.json()
            available_returns = data.get("total_count", 0)
            log(f"Warehance API: {available_returns} returns available")
        else:
            log(f"Warehance API test failed: {response.status_code}")
            return False
    except Exception as e:
        log(f"Warehance API test error: {e}")
        return False
    
    # Trigger sync
    log("Triggering sync...")
    try:
        response = requests.post(f"{AZURE_URL}/api/sync/trigger", json={}, timeout=10)
        if response.status_code == 200:
            log(f"Sync triggered successfully: {response.text}")
        else:
            log(f"Sync trigger failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log(f"Sync trigger error: {e}")
        return False
    
    # Monitor sync progress
    log("Monitoring sync progress (will check for 5 minutes)...")
    
    max_sync_time = 300  # 5 minutes
    check_interval = 15   # Check every 15 seconds
    checks = max_sync_time // check_interval
    
    for i in range(checks):
        try:
            response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
            if response.status_code == 200:
                data = response.json()
                current_sync = data.get("current_sync", {})
                status = current_sync.get("status", "unknown")
                items = current_sync.get("items_synced", 0)
                message = data.get("last_sync_message", "No message")
                
                log(f"[{i*check_interval:3d}s] Status: {status:10s} | Items: {items:4d} | Message: {message}")
                
                if status == "completed":
                    log("SUCCESS: Sync completed!")
                    # Check final database state
                    try:
                        response = requests.get(f"{AZURE_URL}/api/dashboard/stats", timeout=30)
                        if response.status_code == 200:
                            data = response.json()
                            final_returns = data.get("stats", {}).get("total_returns", 0)
                            log(f"Final returns count: {final_returns}")
                            log(f"Returns synced this session: {final_returns - initial_returns}")
                            
                            if final_returns > initial_returns:
                                log("SUCCESS: Data was written to database!")
                                return True
                            else:
                                log("WARNING: No new data was written")
                                return False
                        else:
                            log("Could not get final stats")
                            return True  # Assume success if sync completed
                    except Exception as e:
                        log(f"Final stats error: {e}")
                        return True  # Assume success if sync completed
                
                elif status == "error":
                    log(f"SYNC ERROR: {message}")
                    return False
                    
            else:
                log(f"[{i*check_interval:3d}s] Status check failed: {response.status_code}")
                
        except Exception as e:
            log(f"[{i*check_interval:3d}s] Status check error: {str(e)[:50]}")
        
        if i < checks - 1:
            time.sleep(check_interval)
    
    log("Sync monitoring timed out")
    return False

def test_returns_endpoints():
    """Test if returns endpoints work after sync"""
    log("=== TESTING RETURNS ENDPOINTS ===")
    
    # Test search endpoint
    try:
        response = requests.post(f"{AZURE_URL}/api/returns/search",
                               json={"page": 1, "limit": 5},
                               timeout=30)
        log(f"Returns search endpoint: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            returns_count = len(data.get("returns", []))
            total = data.get("total", 0)
            log(f"SUCCESS: Found {returns_count} returns (total: {total})")
            
            if returns_count > 0:
                sample = data["returns"][0]
                log(f"Sample return: ID={sample.get('id', 'N/A')}, Status={sample.get('status', 'N/A')}")
            return True
        else:
            log(f"Search endpoint error: {response.text[:100]}")
            return False
            
    except Exception as e:
        log(f"Search endpoint error: {e}")
        return False

def main():
    """Main monitoring function"""
    log("=== V17 DEPLOYMENT AND SYNC MONITORING ===")
    
    # Step 1: Wait for V17 deployment
    if not wait_for_v17_deployment():
        log("FAILED: V17 deployment not detected")
        return
    
    # Step 2: Test sync functionality
    if test_v17_sync():
        log("SUCCESS: V17 sync completed successfully!")
        
        # Step 3: Test endpoints
        if test_returns_endpoints():
            log("SUCCESS: Returns endpoints working!")
        else:
            log("WARNING: Returns endpoints not working properly")
    else:
        log("FAILED: V17 sync did not complete successfully")
    
    # Final status
    log("=== FINAL V17 STATUS ===")
    try:
        response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
        if response.status_code == 200:
            data = response.json()
            log(f"Final version: {data.get('deployment_version', 'Unknown')}")
            log(f"Final sync status: {data.get('current_sync', {}).get('status', 'unknown')}")
            log(f"Last sync: {data.get('last_sync', 'Never')}")
        
        response = requests.get(f"{AZURE_URL}/api/dashboard/stats", timeout=30)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            log(f"Total returns in database: {stats.get('total_returns', 0)}")
    except Exception as e:
        log(f"Final status error: {e}")
    
    log("=== MONITORING COMPLETE ===")

if __name__ == "__main__":
    main()