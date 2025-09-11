#!/usr/bin/env python3
"""
Azure Service Monitoring Script
Monitors the Warehance Returns Azure deployment and logs status
"""

import requests
import time
import json
from datetime import datetime
import sys
import traceback

# Azure service configuration
AZURE_URL = "https://uptime-returns.azurewebsites.net"
CHECK_INTERVAL = 30  # seconds between checks
MAX_CHECKS = 60  # maximum checks to perform (30 minutes total)

def log_message(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Remove emojis for Windows compatibility
    message = message.encode('ascii', errors='ignore').decode('ascii')
    print(f"[{timestamp}] {level}: {message}")
    
def check_service_health():
    """Check basic service health"""
    try:
        response = requests.get(f"{AZURE_URL}/api/database/health", timeout=30)
        return {
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "content": response.text[:500] if response.text else "",
            "headers": dict(response.headers),
            "success": response.status_code == 200
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": 0,
            "error": str(e),
            "success": False
        }

def check_deployment_version():
    """Check deployed version"""
    try:
        response = requests.get(f"{AZURE_URL}/api/sync/status", timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                "version": data.get("deployment_version", "Unknown"),
                "status": data.get("current_sync", {}),
                "last_sync": data.get("last_sync"),
                "success": True
            }
        else:
            return {
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "success": False
            }
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }

def test_sync_trigger():
    """Test if sync can be triggered"""
    try:
        response = requests.post(f"{AZURE_URL}/api/sync/trigger", timeout=60)
        return {
            "status_code": response.status_code,
            "response": response.text[:500] if response.text else "",
            "success": response.status_code in [200, 202]
        }
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }

def main():
    """Main monitoring loop"""
    log_message("Starting Azure service monitoring...")
    log_message(f"Target URL: {AZURE_URL}")
    log_message(f"Check interval: {CHECK_INTERVAL} seconds")
    log_message(f"Maximum checks: {MAX_CHECKS}")
    
    deployment_detected = False
    version_detected = None
    check_count = 0
    
    while check_count < MAX_CHECKS:
        check_count += 1
        log_message(f"Check {check_count}/{MAX_CHECKS}")
        
        # Check basic service health
        health = check_service_health()
        if health["success"]:
            log_message("✓ Service is responding")
            if not deployment_detected:
                log_message("🎉 DEPLOYMENT DETECTED - Service is now online!")
                deployment_detected = True
                
            # Check version
            version_info = check_deployment_version()
            if version_info["success"]:
                current_version = version_info["version"]
                if version_detected != current_version:
                    log_message(f"📋 Version detected: {current_version}")
                    version_detected = current_version
                    
                if "V16" in current_version:
                    log_message("✅ V16 DEPLOYMENT CONFIRMED!")
                    
                # Log sync status
                sync_status = version_info.get("status", {})
                if sync_status:
                    log_message(f"🔄 Sync Status: {sync_status.get('status', 'unknown')}")
                    
            else:
                log_message(f"⚠️ Could not get version info: {version_info.get('error', 'Unknown error')}")
                
        else:
            log_message(f"❌ Service health check failed: {health.get('error', 'Unknown error')}")
            
        # If deployment detected and V16 confirmed, test sync
        if deployment_detected and version_detected and "V16" in version_detected and check_count % 10 == 0:
            log_message("🧪 Testing sync functionality...")
            sync_result = test_sync_trigger()
            if sync_result["success"]:
                log_message("✅ Sync trigger test successful!")
                log_message(f"Response: {sync_result.get('response', 'No response body')[:200]}")
            else:
                log_message(f"❌ Sync trigger test failed: {sync_result.get('error', 'Unknown error')}")
        
        # Sleep between checks (except last check)
        if check_count < MAX_CHECKS:
            time.sleep(CHECK_INTERVAL)
    
    log_message("Monitoring complete.")
    if deployment_detected:
        log_message("✅ Summary: Deployment was detected and monitored successfully")
        if version_detected:
            log_message(f"Final version: {version_detected}")
    else:
        log_message("❌ Summary: No successful deployment detected during monitoring period")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("Monitoring interrupted by user", "WARN")
    except Exception as e:
        log_message(f"Monitoring failed: {e}", "ERROR")
        traceback.print_exc()