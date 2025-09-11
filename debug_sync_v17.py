#!/usr/bin/env python3
"""
Debug the V17 sync issue by testing individual components
"""

import requests
import json
import time
from datetime import datetime

AZURE_URL = "https://uptime-returns-adc7ath0dccye4bh.eastus2-01.azurewebsites.net"

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def test_sync_components():
    """Test individual sync components to isolate the issue"""
    log("=== DEBUGGING V17 SYNC ISSUE ===")
    
    # Test 1: Check that all the pieces work individually
    log("Step 1: Testing Warehance API connectivity...")
    try:
        response = requests.get(f"{AZURE_URL}/api/test-warehance", timeout=30)
        if response.status_code == 200:
            data = response.json()
            log(f"✓ Warehance API: {data.get('total_count', 0)} returns available")
            log(f"✓ API Key: {data.get('api_key_used', 'Unknown')}")
        else:
            log(f"✗ Warehance API test failed: {response.status_code}")
            return False
    except Exception as e:
        log(f"✗ Warehance API error: {e}")
        return False
    
    # Test 2: Database table initialization
    log("Step 2: Testing database initialization...")
    try:
        response = requests.post(f"{AZURE_URL}/api/database/init", timeout=30)
        if response.status_code == 200:
            data = response.json()
            log(f"✓ Database init: {data.get('message', 'Success')}")
        else:
            log(f"✗ Database init failed: {response.status_code}")
    except Exception as e:
        log(f"✗ Database init error: {e}")
    
    # Test 3: Basic database operations
    log("Step 3: Testing basic database operations...")
    try:
        response = requests.get(f"{AZURE_URL}/api/clients", timeout=30)
        if response.status_code == 200:
            clients = response.json()
            log(f"✓ Clients table: {len(clients) if isinstance(clients, list) else 'Error'} records")
        
        response = requests.get(f"{AZURE_URL}/api/warehouses", timeout=30)
        if response.status_code == 200:
            warehouses = response.json()
            log(f"✓ Warehouses table: {len(warehouses) if isinstance(warehouses, list) else 'Error'} records")
        
        response = requests.get(f"{AZURE_URL}/api/dashboard/stats", timeout=30)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            log(f"✓ Returns table: {stats.get('total_returns', 0)} records")
        else:
            log(f"✗ Dashboard stats failed: {response.status_code}")
            
    except Exception as e:
        log(f"✗ Database operations error: {e}")
    
    # Test 4: Trigger sync and monitor in extreme detail
    log("Step 4: Testing sync with detailed monitoring...")
    
    # Get initial status
    try:
        response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
        if response.status_code == 200:
            initial_data = response.json()
            log(f"Pre-sync status: {initial_data.get('current_sync', {}).get('status', 'unknown')}")
        
        # Trigger sync
        log("Triggering sync...")
        response = requests.post(f"{AZURE_URL}/api/sync/trigger", json={}, timeout=10)
        log(f"Sync trigger: {response.status_code} - {response.text}")
        
        if response.status_code != 200:
            log("✗ Sync trigger failed")
            return False
        
        # Monitor sync with very frequent checks
        log("Monitoring sync every 2 seconds for 60 seconds...")
        for i in range(30):  # 30 * 2 = 60 seconds
            time.sleep(2)
            
            try:
                response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    current_sync = data.get("current_sync", {})
                    status = current_sync.get("status", "unknown")
                    items = current_sync.get("items_synced", 0)
                    message = data.get("last_sync_message", "No message")
                    
                    log(f"[{i*2:2d}s] {status:10s} | {items:4d} items | {message}")
                    
                    if status == "completed":
                        log("✓ Sync completed successfully!")
                        return True
                    elif status == "error":
                        log(f"✗ Sync error: {message}")
                        log("Full error status:")
                        log(json.dumps(data, indent=2))
                        return False
                else:
                    log(f"[{i*2:2d}s] Status check failed: {response.status_code}")
                    
            except Exception as e:
                log(f"[{i*2:2d}s] Status check error: {e}")
        
        log("✗ Sync monitoring timed out")
        return False
        
    except Exception as e:
        log(f"✗ Sync test error: {e}")
        return False

def main():
    """Main debug function"""
    if test_sync_components():
        log("🎉 SYNC DEBUGGING: SUCCESS - Issue resolved!")
    else:
        log("❌ SYNC DEBUGGING: FAILED - Issue persists")
        log("Recommendation: Check Azure App Service logs directly for more details")

if __name__ == "__main__":
    main()