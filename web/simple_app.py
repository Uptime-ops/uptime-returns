"""
Simple FastAPI app that works without SQLAlchemy issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.responses import FileResponse
import sqlite3
import json

app = FastAPI()

@app.get("/")
async def root():
    """Serve the main HTML dashboard"""
    return FileResponse("templates/index.html")

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    conn = sqlite3.connect('../warehance_returns.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM returns")
    total_returns = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM returns WHERE processed = 0")
    pending_returns = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM returns WHERE processed = 1")
    processed_returns = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT id) FROM clients")
    total_clients = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT id) FROM warehouses")
    total_warehouses = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_returns": total_returns,
        "pending_returns": pending_returns,
        "processed_returns": processed_returns,
        "total_clients": total_clients,
        "total_warehouses": total_warehouses,
        "returns_today": 0,
        "returns_this_week": 0,
        "returns_this_month": 0,
        "unshared_returns": total_returns,
        "last_sync": None
    }

@app.get("/api/clients")
async def get_clients():
    conn = sqlite3.connect('../warehance_returns.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM clients ORDER BY name")
    clients = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()
    return clients

@app.get("/api/warehouses")
async def get_warehouses():
    conn = sqlite3.connect('../warehance_returns.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM warehouses ORDER BY name")
    warehouses = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()
    return warehouses

@app.post("/api/returns/search")
async def search_returns(filter_params: dict):
    conn = sqlite3.connect('../warehance_returns.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Extract filter parameters
    page = filter_params.get('page', 1)
    limit = filter_params.get('limit', 20)
    client_id = filter_params.get('client_id')
    status = filter_params.get('status')
    search = filter_params.get('search') or ''
    search = search.strip() if search else ''
    
    # Build query with filters
    query = """
    SELECT r.id, r.status, r.created_at, r.tracking_number, 
           r.processed, r.api_id, c.name as client_name, 
           w.name as warehouse_name, r.client_id
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    WHERE 1=1
    """
    
    params = []
    
    if client_id:
        query += " AND r.client_id = ?"
        params.append(client_id)
    
    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"
    
    if search:
        query += " AND (r.tracking_number LIKE ? OR r.id LIKE ? OR c.name LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    # Get total count for pagination
    count_query = f"SELECT COUNT(*) FROM ({query}) as filtered"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Add pagination
    query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, (page - 1) * limit])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    returns = []
    for row in rows:
        returns.append({
            "id": row['id'],
            "status": row['status'] or '',
            "created_at": row['created_at'],
            "tracking_number": row['tracking_number'],
            "processed": bool(row['processed']),
            "api_id": row['api_id'],
            "client_name": row['client_name'],
            "warehouse_name": row['warehouse_name'],
            "is_shared": False
        })
    
    conn.close()
    
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "returns": returns,
        "total_count": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.get("/api/analytics/return-reasons")
async def get_return_reasons():
    return []  # Empty for now

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)