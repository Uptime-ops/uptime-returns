# Clean FastAPI app - routes only
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import io
import asyncio
from datetime import datetime
from typing import Optional, Dict

# Import clean services
from services.sync_service import CleanSyncService
from services.export_service import CleanExportService
from models.database import create_tables, get_table_counts
from config.settings import APP_VERSION
from config.database import test_connection

# Initialize FastAPI app
app = FastAPI(title="Warehance Returns - Clean", version=APP_VERSION)

# Global sync status
sync_status = {"is_running": False, "last_sync": None}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Warehance Returns - Clean</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </head>
    <body>
        <div class="container mt-4">
            <div class="row">
                <div class="col-12">
                    <h1>🔄 Warehance Returns - Clean Architecture</h1>
                    <p class="text-muted">Simplified, reliable returns management</p>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">🔄 Sync Management</h5>
                            <button class="btn btn-primary" onclick="triggerSync()">Start Sync</button>
                            <button class="btn btn-secondary" onclick="checkStatus()">Check Status</button>
                            <div id="sync-status" class="mt-3"></div>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">📤 Export Data</h5>
                            <button class="btn btn-success" onclick="exportCSV()">Export CSV</button>
                            <div id="export-status" class="mt-3"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">📊 Database Stats</h5>
                            <button class="btn btn-outline-info" onclick="loadStats()">Refresh Stats</button>
                            <div id="stats-container" class="mt-3"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function triggerSync() {
                $('#sync-status').html('<div class="text-info">Starting sync...</div>');

                fetch('/api/sync/trigger', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                })
                .then(response => response.json())
                .then(data => {
                    $('#sync-status').html(`<div class="alert alert-${data.status === 'success' ? 'success' : 'danger'}">${data.message}</div>`);
                })
                .catch(error => {
                    $('#sync-status').html(`<div class="alert alert-danger">Error: ${error}</div>`);
                });
            }

            function checkStatus() {
                fetch('/api/sync/status')
                .then(response => response.json())
                .then(data => {
                    const statusHtml = `
                        <div class="alert alert-info">
                            <strong>Status:</strong> ${data.status}<br>
                            <strong>Last Sync:</strong> ${data.last_sync || 'Never'}<br>
                            <strong>Version:</strong> ${data.version}
                        </div>
                    `;
                    $('#sync-status').html(statusHtml);
                })
                .catch(error => {
                    $('#sync-status').html(`<div class="alert alert-danger">Error: ${error}</div>`);
                });
            }

            function exportCSV() {
                $('#export-status').html('<div class="text-info">Generating CSV...</div>');

                fetch('/api/export/csv')
                .then(response => {
                    if (response.ok) {
                        return response.blob();
                    }
                    throw new Error('Export failed');
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = `returns_export_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.csv`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    $('#export-status').html('<div class="alert alert-success">CSV downloaded!</div>');
                })
                .catch(error => {
                    $('#export-status').html(`<div class="alert alert-danger">Export failed: ${error}</div>`);
                });
            }

            function loadStats() {
                fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    let statsHtml = '<div class="row">';
                    for (const [table, count] of Object.entries(data)) {
                        statsHtml += `
                            <div class="col-md-3 mb-2">
                                <div class="text-center">
                                    <h6>${table}</h6>
                                    <span class="badge bg-primary fs-6">${count}</span>
                                </div>
                            </div>
                        `;
                    }
                    statsHtml += '</div>';
                    $('#stats-container').html(statsHtml);
                })
                .catch(error => {
                    $('#stats-container').html(`<div class="alert alert-danger">Error loading stats: ${error}</div>`);
                });
            }

            // Load stats on page load
            $(document).ready(function() {
                loadStats();
                checkStatus();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/sync/trigger")
async def trigger_sync():
    """Trigger clean sync process"""
    global sync_status

    if sync_status["is_running"]:
        return {"status": "error", "message": "Sync already running"}

    try:
        sync_status["is_running"] = True

        # Run sync in background
        async def run_sync():
            try:
                sync_service = CleanSyncService()
                result = sync_service.run_full_sync()
                sync_status["last_sync"] = datetime.now().isoformat()
                sync_status["is_running"] = False
                print(f"✅ Background sync completed: {result}")
            except Exception as e:
                sync_status["is_running"] = False
                print(f"❌ Background sync failed: {e}")

        asyncio.create_task(run_sync())

        return {
            "status": "success",
            "message": "Clean sync started successfully"
        }

    except Exception as e:
        sync_status["is_running"] = False
        print(f"❌ Failed to start sync: {e}")
        return {
            "status": "error",
            "message": f"Failed to start sync: {str(e)}"
        }

@app.get("/api/sync/status")
async def get_sync_status():
    """Get current sync status"""
    return {
        "status": "running" if sync_status["is_running"] else "idle",
        "last_sync": sync_status["last_sync"],
        "version": APP_VERSION
    }

@app.get("/api/export/csv")
async def export_csv():
    """Export returns as CSV"""
    try:
        export_service = CleanExportService()
        csv_output = export_service.export_returns_csv()

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"returns_export_clean_{timestamp}.csv"

        # Return as streaming response
        csv_output.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        print(f"❌ CSV export failed: {e}")
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")

@app.get("/api/stats")
async def get_database_stats():
    """Get database table statistics"""
    try:
        stats = get_table_counts()
        return stats
    except Exception as e:
        print(f"❌ Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        db_healthy = test_connection()
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected",
            "version": APP_VERSION,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": APP_VERSION,
            "timestamp": datetime.now().isoformat()
        }

@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    print(f"🚀 Starting clean Warehance Returns app - Version {APP_VERSION}")

    # Test database connection
    try:
        if test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
    except Exception as e:
        print(f"❌ Database startup error: {e}")

    # Create tables if needed
    try:
        create_tables()
        print("✅ Database tables verified")
    except Exception as e:
        print(f"❌ Table creation error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8016)