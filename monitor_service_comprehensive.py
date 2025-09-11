#!/usr/bin/env python3
"""
Comprehensive Azure Service Monitoring and Sync Testing
"""

import requests
import json
import time
from datetime import datetime

# Correct Azure URL from workflow
AZURE_URL = "https://uptime-returns-adc7ath0dccye4bh.eastus2-01.azurewebsites.net"

def log(message):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def check_deployment_status():
    """Check current deployment version and status"""
    try:
        response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "version": data.get("deployment_version", "Unknown"),
                "sync_status": data.get("current_sync", {}),
                "last_sync": data.get("last_sync"),
                "database_type": data.get("database_type", "Unknown")
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def test_database_health():
    """Test database connectivity"""
    try:
        response = requests.get(f"{AZURE_URL}/api/database/health", timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "database_type": data.get("database_type", "Unknown"),
                "connection": data.get("connection", "Unknown"),
                "returns_count": data.get("returns_count", 0),
                "tables_exist": data.get("table_exists", False)
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def trigger_sync():
    """Trigger sync with proper request body"""
    try:
        # Try with empty JSON body first
        response = requests.post(f"{AZURE_URL}/api/sync/trigger", 
                               json={}, 
                               timeout=120)
        return {
            "success": response.status_code in [200, 202],
            "status_code": response.status_code,
            "response": response.text[:500] if response.text else "No response"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def monitor_deployment_and_test():
    """Main monitoring function"""
    log("=== AZURE SERVICE COMPREHENSIVE MONITORING ===")
    log(f"Target URL: {AZURE_URL}")
    
    deployment_checks = 0
    max_deployment_checks = 20  # 10 minutes
    v16_detected = False
    
    # Phase 1: Wait for V16 deployment
    log("PHASE 1: Monitoring for V16 deployment...")
    
    while deployment_checks < max_deployment_checks and not v16_detected:
        deployment_checks += 1
        log(f"Deployment check {deployment_checks}/{max_deployment_checks}")
        
        status = check_deployment_status()
        if status["success"]:
            version = status["version"]
            log(f"Current version: {version}")
            
            if "V16" in version:
                log("SUCCESS: V16 DEPLOYMENT DETECTED!")
                v16_detected = True
                break
            else:
                log(f"Still on older version, waiting...")
        else:
            log(f"Status check failed: {status['error']}")
        
        if not v16_detected:
            time.sleep(30)  # Wait 30 seconds
    
    if not v16_detected:
        log("WARNING: V16 deployment not detected within time limit")
        log("Proceeding with current version testing...")
    
    # Phase 2: Test database connectivity
    log("PHASE 2: Testing database connectivity...")
    
    db_health = test_database_health()
    if db_health["success"]:
        log(f"Database status: {db_health['connection']}")
        log(f"Database type: {db_health['database_type']}")
        log(f"Returns in DB: {db_health['returns_count']}")
        log(f"Tables exist: {db_health['tables_exist']}")
    else:
        log(f"Database health check FAILED: {db_health['error']}")
    
    # Phase 3: Test sync functionality
    log("PHASE 3: Testing sync functionality...")
    
    # Get initial sync status
    initial_status = check_deployment_status()
    if initial_status["success"]:
        initial_sync = initial_status["sync_status"]
        log(f"Initial sync status: {initial_sync.get('status', 'unknown')}")
        log(f"Last sync: {initial_status['last_sync'] or 'Never'}")
    
    # Trigger sync
    log("Triggering sync...")
    sync_result = trigger_sync()
    
    if sync_result["success"]:
        log("SUCCESS: Sync triggered successfully!")
        log(f"Response: {sync_result['response']}")
        
        # Monitor sync progress
        log("Monitoring sync progress...")
        for i in range(12):  # Monitor for 2 minutes
            time.sleep(10)
            
            current_status = check_deployment_status()
            if current_status["success"]:
                sync_info = current_status["sync_status"]
                sync_status = sync_info.get("status", "unknown")
                items_synced = sync_info.get("items_synced", 0)
                
                log(f"Sync progress [{i+1}/12]: {sync_status}, {items_synced} items")
                
                if sync_status == "completed":
                    log("SUCCESS: Sync completed successfully!")
                    break
                elif sync_status == "error":
                    log(f"SYNC ERROR: {sync_info.get('error', 'Unknown error')}")
                    break
            else:
                log("Could not get sync status")
    else:
        log(f"SYNC TRIGGER FAILED: {sync_result['error'] if 'error' in sync_result else sync_result['response']}")
    
    # Final status report
    log("=== FINAL STATUS REPORT ===")
    final_status = check_deployment_status()
    if final_status["success"]:
        log(f"Final version: {final_status['version']}")
        log(f"Final sync status: {final_status['sync_status'].get('status', 'unknown')}")
        log(f"Final last sync: {final_status['last_sync'] or 'Never'}")
        
        if "V16" in final_status["version"]:
            log("DEPLOYMENT SUCCESS: V16 is active")
        else:
            log("DEPLOYMENT WARNING: V16 not detected")
            
        sync_status = final_status['sync_status'].get('status', 'unknown')
        if sync_status == 'completed':
            log("SYNC SUCCESS: Returns sync completed")
        else:
            log(f"SYNC STATUS: {sync_status}")
    
    log("=== MONITORING COMPLETE ===")

if __name__ == "__main__":
    monitor_deployment_and_test()