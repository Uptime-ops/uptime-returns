"""
Enhanced FastAPI app with product details and CSV export
"""
import sys
import os

# VERSION IDENTIFIER - Update this when deploying
import datetime
DEPLOYMENT_VERSION = "V87.185-DEBUG-INTEGER-OVERFLOW-IDS"
DEPLOYMENT_TIME = datetime.datetime.now().isoformat()
print(f"=== STARTING APP_V2.PY VERSION: {DEPLOYMENT_VERSION} ===")
print(f"=== DEPLOYMENT TIME: {DEPLOYMENT_TIME} ===")
print("=== THIS IS THE NEW APP_V2.PY FILE ===")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database drivers early
import sqlite3
try:
    import pyodbc
    print("pyodbc imported successfully")
except ImportError:
    pyodbc = None  # Will use SQLite if pyodbc not available
    print("pyodbc not available")
    
# Try pymssql as fallback for Azure SQL
try:
    import pymssql
    print("pymssql imported successfully")
except ImportError:
    pymssql = None
    print("pymssql not available")

# Azure Environment Detection
IS_AZURE = os.getenv('WEBSITE_INSTANCE_ID') is not None

# Configuration from environment variables
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET', '')
WAREHANCE_API_KEY = os.getenv('WAREHANCE_API_KEY')
if not WAREHANCE_API_KEY:
    raise ValueError("WAREHANCE_API_KEY environment variable must be set. Please configure it in Azure App Service Application Settings.")

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_AZURE_SQL = bool(DATABASE_URL and ('database.windows.net' in DATABASE_URL or 'database.azure.com' in DATABASE_URL))

# Debug database configuration
print(f"=== DATABASE CONFIGURATION ===")
print(f"DATABASE_URL exists: {bool(DATABASE_URL)}")
print(f"USE_AZURE_SQL: {USE_AZURE_SQL}")
print(f"IS_AZURE: {IS_AZURE}")
if DATABASE_URL:
    print(f"DATABASE_URL preview: {DATABASE_URL[:50]}...")
else:
    print("DATABASE_URL is empty - will use SQLite fallback")

# SQL parameterization helper - Azure SQL uses %s, SQLite uses ?
def get_param_placeholder():
    """Get the correct parameter placeholder for the current database"""
    return "%s" if USE_AZURE_SQL else "?"

def format_in_clause(count):
    """Format IN clause with correct placeholders"""
    placeholder = get_param_placeholder()
    return ','.join([placeholder] * count)

def format_limit_clause(limit, offset=0):
    """Format LIMIT clause with correct syntax for database type"""
    if USE_AZURE_SQL:
        # Azure SQL uses OFFSET/FETCH syntax
        if offset > 0:
            return f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
        else:
            return f"OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
    else:
        # SQLite uses LIMIT/OFFSET syntax
        if offset > 0:
            return f"LIMIT {limit} OFFSET {offset}"
        else:
            return f"LIMIT {limit}"

if USE_AZURE_SQL:
    print(f"Using Azure SQL Database")
    
    # First, list all available ODBC drivers for diagnostics
    print("=== ODBC Driver Diagnostics ===")
    try:
        available_drivers = pyodbc.drivers()
        print(f"Available ODBC drivers: {available_drivers}")
        if not available_drivers:
            print("WARNING: No ODBC drivers detected! This may be a configuration issue.")
    except Exception as e:
        print(f"ERROR listing drivers: {e}")
    print("================================")
    
    def get_db_connection():
        """Get Azure SQL connection with comprehensive fallback"""
        import re
        import subprocess
        
        print(f"DATABASE_URL exists: {bool(DATABASE_URL)}")
        print(f"DATABASE_URL starts with: {DATABASE_URL[:50] if DATABASE_URL else 'Empty'}...")
        
        # First try pymssql as it's simpler and doesn't need ODBC drivers
        if pymssql:
            try:
                print("Attempting pymssql connection...")
                # Parse DATABASE_URL - same parsing logic as pyodbc
                conn_params = {}
                for part in DATABASE_URL.split(';'):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        conn_params[key.strip().upper()] = value.strip()
                
                # Extract connection parameters
                server = conn_params.get('SERVER', '').replace('tcp:', '').replace(',1433', '')
                database = conn_params.get('DATABASE', '') or conn_params.get('INITIAL CATALOG', '') or 'uptime-returns-db'
                username = conn_params.get('USER ID', '') or conn_params.get('USER', '') or conn_params.get('UID', '')
                password = conn_params.get('PASSWORD', '') or conn_params.get('PWD', '')
                
                # If database is empty, use a default name
                if not database:
                    database = 'uptime-returns-db'
                    print(f"No database specified, using default: {database}")
                
                if server and database and username and password:
                    print(f"Connecting to {server}/{database} as {username}")
                    
                    # Connect using pymssql
                    conn = pymssql.connect(
                        server=server,
                        user=username,
                        password=password,
                        database=database,
                        as_dict=True,
                        port=1433
                    )
                    print("SUCCESS: Connected with pymssql")
                    return conn
                else:
                    print(f"pymssql: Missing connection parameters - server:{bool(server)}, db:{bool(database)}, user:{bool(username)}, pwd:{bool(password)}")
            except Exception as e:
                print(f"pymssql failed: {str(e)[:300]}")
        
        # Try pyodbc with multiple approaches
        if pyodbc:
            try:
                # List available drivers
                available_drivers = pyodbc.drivers()
                print(f"Available ODBC drivers: {available_drivers}")
                
                # Parse the connection string to get components
                # Expected format: Server=tcp:server.database.windows.net,1433;Database=dbname;User ID=user;Password=pass
                conn_params = {}
                for part in DATABASE_URL.split(';'):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        conn_params[key.strip().upper()] = value.strip()
                
                # Extract connection parameters
                server = conn_params.get('SERVER', '').replace('tcp:', '')
                if ',' in server:
                    server = server.split(',')[0]  # Remove port if present
                database = conn_params.get('DATABASE', '') or conn_params.get('INITIAL CATALOG', '') or 'uptime-returns-db'
                username = conn_params.get('USER ID', '') or conn_params.get('USER', '') or conn_params.get('UID', '')
                password = conn_params.get('PASSWORD', '') or conn_params.get('PWD', '')
                
                # If database is empty, use a default name
                if not database:
                    database = 'uptime-returns-db'
                    print(f"No database specified, using default: {database}")
                
                print(f"Parsed - Server: {server}, Database: {database}, User: {username}")
                
                # Build list of drivers to try
                drivers_to_try = []
                
                # Add detected drivers first
                if 'ODBC Driver 18 for SQL Server' in available_drivers:
                    drivers_to_try.append('ODBC Driver 18 for SQL Server')
                if 'ODBC Driver 17 for SQL Server' in available_drivers:
                    drivers_to_try.append('ODBC Driver 17 for SQL Server')
                
                # Try each driver with properly formatted connection string
                for driver in drivers_to_try:
                    try:
                        # Build proper ODBC connection string
                        test_conn_str = (
                            f"DRIVER={{{driver}}};"
                            f"SERVER={server};"
                            f"DATABASE={database};"
                            f"UID={username};"
                            f"PWD={password};"
                            f"TrustServerCertificate=yes;"
                            f"Encrypt=yes"
                        )
                        
                        print(f"Trying driver: {driver}")
                        print(f"Connection string format: DRIVER={{...}};SERVER={server};DATABASE={database};UID={username[:3]}...;PWD=***")
                        
                        conn = pyodbc.connect(test_conn_str, timeout=10)
                        
                        # Configure encoding
                        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
                        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
                        conn.setencoding(encoding='utf-8')
                        
                        print(f"SUCCESS: Connected with {driver if driver else 'default driver'}")
                        return conn
                        
                    except Exception as e:
                        error_msg = str(e)[:100]
                        if driver:
                            print(f"Failed with {driver}: {error_msg}")
                        continue
                
                # If nothing worked, try to get more info
                try:
                    result = subprocess.run(['odbcinst', '-j'], capture_output=True, text=True, timeout=5)
                    print(f"ODBC config:\n{result.stdout}")
                except:
                    pass
                    
            except Exception as e:
                print(f"pyodbc error: {str(e)[:300]}")
        
        # If we get here, nothing worked
        error_msg = "Failed to connect to Azure SQL. "
        if not pyodbc and not pymssql:
            error_msg += "No SQL drivers available (neither pyodbc nor pymssql)."
        elif not DATABASE_URL:
            error_msg += "DATABASE_URL environment variable is not set."
        else:
            error_msg += "All connection attempts failed. Check Azure logs for details."
        
        print(f"CRITICAL ERROR: {error_msg}")
        raise Exception(error_msg)
else:
    # SQLite configuration
    if IS_AZURE:
        DATABASE_PATH = '/home/warehance_returns.db'
    else:
        DATABASE_PATH = '../warehance_returns.db'
    
    def get_db_connection():
        """Get SQLite connection"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import csv
import io
from datetime import datetime
import asyncio
import requests
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Import email configuration (optional - can be set via environment or UI)
try:
    from email_config import EMAIL_CONFIG, EMAIL_TEMPLATE, EMAIL_TEMPLATE_PLAIN
except ImportError:
    EMAIL_CONFIG = None
    EMAIL_TEMPLATE = None
    EMAIL_TEMPLATE_PLAIN = None

# Import OAuth email support
try:
    from email_oauth import MicrosoftGraphMailer, GRAPH_CONFIG
    OAUTH_ENABLED = True
except ImportError:
    OAUTH_ENABLED = False
    GRAPH_CONFIG = None

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Global sync status
sync_status = {
    "is_running": False,
    "last_sync": None,
    "last_sync_status": None,
    "last_sync_message": None,
    "items_synced": 0
}

# Helper functions for database row conversion
def row_to_dict(cursor, row):
    """Convert database row to dictionary for both SQLite and Azure SQL"""
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))

def rows_to_dict(cursor, rows):
    """Convert multiple database rows to list of dictionaries"""
    if not rows:
        return []
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

@app.get("/")
async def root():
    """Serve the main HTML dashboard"""
    # Check multiple possible paths for templates
    import os
    possible_paths = [
        "web/templates/index.html",  # When running from root
        "templates/index.html",       # When running from web directory
        "/home/site/wwwroot/web/templates/index.html",  # Azure absolute path
        os.path.join(os.path.dirname(__file__), "templates", "index.html")  # Relative to this file
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    
    # If no template found, return error with debug info
    return {"error": "Template not found", "searched_paths": possible_paths, "cwd": os.getcwd()}

@app.get("/favicon.ico")
async def favicon():
    """Return empty response for favicon to prevent 404 errors"""
    return Response(status_code=204)

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    try:
        conn = get_db_connection()
        if not USE_AZURE_SQL:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get various statistics
        stats = {}
        
        cursor.execute("SELECT COUNT(*) as count FROM returns")
        row = cursor.fetchone()
        stats['total_returns'] = row[0] if row else 0
        
        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 0")
        row = cursor.fetchone()
        stats['pending_returns'] = row[0] if row else 0
        
        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 1")
        row = cursor.fetchone()
        stats['processed_returns'] = row[0] if row else 0
    
        cursor.execute("SELECT COUNT(DISTINCT client_id) as count FROM returns WHERE client_id IS NOT NULL")
        row = cursor.fetchone()
        stats['total_clients'] = row[0] if row else 0
        
        cursor.execute("SELECT COUNT(DISTINCT warehouse_id) as count FROM returns WHERE warehouse_id IS NOT NULL")
        row = cursor.fetchone()
        stats['total_warehouses'] = row[0] if row else 0
    
        # Get return counts by time period
        if USE_AZURE_SQL:
            # Azure SQL syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)")
            row = cursor.fetchone()
            stats['returns_today'] = row[0] if row else 0
            
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -7, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_week'] = row[0] if row else 0
            
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -30, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_month'] = row[0] if row else 0
        else:
            # SQLite syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) = DATE('now')")
            row = cursor.fetchone()
            stats['returns_today'] = row[0] if row else 0
            
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-7 days')")
            row = cursor.fetchone()
            stats['returns_this_week'] = row[0] if row else 0
            
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-30 days')")
            row = cursor.fetchone()
            stats['returns_this_month'] = row[0] if row else 0
    
        # Count of unshared returns
        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id NOT IN (SELECT return_id FROM email_share_items)")
            row = cursor.fetchone()
            stats['unshared_returns'] = row[0] if row else 0
        except:
            # Table might not exist yet
            stats['unshared_returns'] = stats['total_returns']
        
        # Get last sync time
        try:
            cursor.execute("SELECT MAX(completed_at) as last_sync FROM sync_logs WHERE status = 'completed'")
            row = cursor.fetchone()
            stats['last_sync'] = row[0] if row else None
        except:
            stats['last_sync'] = None
        
        # Get product statistics
        try:
            cursor.execute("SELECT COUNT(*) as count FROM products")
            row = cursor.fetchone()
            stats['total_products'] = row[0] if row else 0
        except:
            stats['total_products'] = 0
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM return_items")
            row = cursor.fetchone()
            stats['total_return_items'] = row[0] if row else 0
        except:
            stats['total_return_items'] = 0
        
        try:
            cursor.execute("SELECT SUM(quantity) as total FROM return_items")
            row = cursor.fetchone()
            stats['total_returned_quantity'] = row[0] if row else 0
        except:
            stats['total_returned_quantity'] = 0
    
        conn.close()
        return stats
    except Exception as e:
        print(f"Error in dashboard stats: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return {"error": str(e), "stats": {}}

@app.get("/api/clients")
async def get_clients():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM clients ORDER BY name")
        
        if USE_AZURE_SQL:
            rows = cursor.fetchall()
            clients = rows_to_dict(cursor, rows) if rows else []
        else:
            clients = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        return clients
    except Exception as e:
        print(f"Error in get_clients: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return []

@app.get("/api/warehouses")
async def get_warehouses():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM warehouses ORDER BY name")
        
        if USE_AZURE_SQL:
            rows = cursor.fetchall()
            warehouses = rows_to_dict(cursor, rows) if rows else []
        else:
            warehouses = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        return warehouses
    except Exception as e:
        print(f"Error in get_warehouses: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return []

@app.post("/api/returns/search")
async def search_returns(filter_params: dict):
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Extract filter parameters
    page = filter_params.get('page', 1)
    limit = filter_params.get('limit', 20)
    client_id = filter_params.get('client_id')
    status = filter_params.get('status')
    search = filter_params.get('search') or ''
    search = search.strip() if search else ''
    include_items = filter_params.get('include_items', False)
    
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
        query += " AND r.client_id = %s"
        params.append(client_id)
    
    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"
    
    if search:
        query += " AND (r.tracking_number LIKE %s OR r.id LIKE %s OR c.name LIKE %s)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    # Get total count for pagination
    count_query = f"SELECT COUNT(*) as total_count FROM ({query}) as filtered"
    cursor.execute(count_query, params)
    row = cursor.fetchone()
    total = row[0] if row else 0
    
    # Add pagination (different syntax for Azure SQL vs SQLite)
    if USE_AZURE_SQL:
        query += " ORDER BY r.created_at DESC OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
        params.extend([(page - 1) * limit, limit])
    else:
        query += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, (page - 1) * limit])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    returns = []
    if USE_AZURE_SQL:
        rows = rows_to_dict(cursor, rows) if rows else []
    
    for row in rows:
        if USE_AZURE_SQL:
            return_dict = {
                "id": row['id'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "tracking_number": row['tracking_number'],
                "processed": bool(row['processed']),
                "api_id": row['api_id'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "is_shared": False
            }
        else:
            return_dict = {
                "id": row['id'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "tracking_number": row['tracking_number'],
                "processed": bool(row['processed']),
                "api_id": row['api_id'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "is_shared": False
            }
        
        # Include items if requested
        if include_items:
            return_id = row['id'] if USE_AZURE_SQL else row['id']
            cursor.execute("""
                SELECT ri.*, p.sku, p.name as product_name
                FROM return_items ri
                LEFT JOIN products p ON ri.product_id = p.id
                WHERE ri.return_id = %s
            """, (return_id,))
            
            item_rows = cursor.fetchall()
            if USE_AZURE_SQL:
                item_rows = rows_to_dict(cursor, item_rows) if item_rows else []
            
            items = []
            for item_row in item_rows:
                items.append({
                    "id": item_row['id'],
                    "product_id": item_row['product_id'],
                    "sku": item_row['sku'],
                    "product_name": item_row['product_name'],
                    "quantity": item_row['quantity'],
                    "return_reasons": json.loads(item_row['return_reasons']) if item_row['return_reasons'] else [],
                    "condition_on_arrival": json.loads(item_row['condition_on_arrival']) if item_row['condition_on_arrival'] else [],
                    "quantity_received": item_row['quantity_received'],
                    "quantity_rejected": item_row['quantity_rejected']
                })
            return_dict['items'] = items
        
        returns.append(return_dict)
    
    conn.close()
    
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "returns": returns,
        "total_count": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.get("/api/returns/{return_id}")
async def get_return_detail(return_id: int):
    """Get detailed information for a specific return including order items if available"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get return details
    cursor.execute("""
        SELECT r.*, c.name as client_name, w.name as warehouse_name, r.order_id
        FROM returns r
        LEFT JOIN clients c ON r.client_id = c.id
        LEFT JOIN warehouses w ON r.warehouse_id = w.id
        WHERE r.id = %s
    """, (return_id,))
    
    return_row = cursor.fetchone()
    if not return_row:
        return {"error": "Return not found"}
    
    return_data = dict(return_row)
    order_id = return_data.get('order_id')
    
    items = []
    
    # First check if there are actual return items (there shouldn't be any from API)
    cursor.execute("""
        SELECT ri.*, p.sku, p.name as product_name
        FROM return_items ri
        LEFT JOIN products p ON ri.product_id = p.id
        WHERE ri.return_id = %s
    """, (return_id,))
    
    return_items = cursor.fetchall()
    
    if return_items:
        # If we have return items, use them
        for item_row in return_items:
            items.append({
                "id": item_row['id'],
                "product_id": item_row['product_id'],
                "sku": item_row['sku'],
                "product_name": item_row['product_name'],
                "quantity": item_row['quantity'],
                "return_reasons": json.loads(item_row['return_reasons']) if item_row['return_reasons'] else [],
                "condition_on_arrival": json.loads(item_row['condition_on_arrival']) if item_row['condition_on_arrival'] else [],
                "quantity_received": item_row['quantity_received'],
                "quantity_rejected": item_row['quantity_rejected']
            })
    elif order_id:
        # If no return items but we have an order, fetch order details from API
        import requests
        
        headers = {
            "X-API-KEY": "WH_237eb441_547781417ad5a2dc895ba0915deaf48cb963c1660e2324b3fb25df5bd4df65f1",
            "accept": "application/json"
        }
        
        try:
            response = requests.get(
                f"https://api.warehance.com/v1/orders/{order_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                order_data = response.json()
                if order_data.get("status") == "success":
                    order = order_data.get("data", {})
                    return_data['order_number'] = order.get('order_number')
                    
                    # Get order items and display them as likely returned items
                    order_items = order.get('order_items', [])
                    for item in order_items:
                        # Get the best quantity to display
                        qty = item.get('quantity', 0)
                        qty_shipped = item.get('quantity_shipped', 0)
                        
                        # Use shipped quantity if available, otherwise use ordered quantity
                        # If both are 0, still show the item but mark it as bundle component
                        display_qty = qty_shipped if qty_shipped > 0 else qty
                        
                        # Always show items that have a name, even if quantity is 0
                        if item.get('name'):
                            note = "Original order item"
                            if display_qty == 0 and item.get('bundle_order_item_id'):
                                note = "Bundle component - quantity included in bundle"
                                # Try to set quantity to 1 for display purposes if it's a bundle item
                                display_qty = 1
                            
                            items.append({
                                "id": item.get('id'),
                                "sku": item.get('sku'),
                                "product_name": item.get('name'),
                                "quantity": display_qty,
                                "quantity_ordered": qty,
                                "quantity_shipped": qty_shipped,
                                "unit_price": item.get('unit_price'),
                                "note": note
                            })
                    
                    if items:
                        return_data['items_note'] = "Showing original order items (return-specific quantities not available from API)"
        except Exception as e:
            # If API call fails, just show order info from database
            cursor.execute("""
                SELECT o.order_number
                FROM orders o
                WHERE o.id = %s
            """, (order_id,))
            
            order_row = cursor.fetchone()
            if order_row:
                return_data['order_number'] = order_row['order_number']
                return_data['items_note'] = "Return items not available from API. Order reference shown."
    
    return_data['items'] = items
    
    conn.close()
    return return_data

@app.post("/api/returns/export/csv")
async def export_returns_csv(filter_params: dict):
    """Export returns with product details to CSV"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # First get all returns matching the filter
    query = """
    SELECT r.id as return_id, r.status, r.created_at as return_date, r.tracking_number, 
           r.processed, c.name as client_name, w.name as warehouse_name,
           r.order_id, o.order_number, o.created_at as order_date, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON r.order_id = o.id
    WHERE 1=1
    """
    
    params = []
    client_id = filter_params.get('client_id')
    status = filter_params.get('status')
    search = filter_params.get('search') or ''
    search = search.strip() if search else ''
    
    if client_id:
        query += " AND r.client_id = %s"
        params.append(client_id)
    
    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"
    
    if search:
        query += " AND (r.tracking_number LIKE %s OR r.id LIKE %s OR c.name LIKE %s)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    query += " ORDER BY r.created_at DESC"
    
    cursor.execute(query, params)
    returns = cursor.fetchall()
    
    # Convert rows to dict for Azure SQL
    if USE_AZURE_SQL:
        returns = rows_to_dict(cursor, returns) if returns else []
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header with your requested columns
    writer.writerow([
        'Client', 'Customer Name', 'Order Date', 'Return Date', 
        'Order Number', 'Item Name', 'Order Qty', 'Return Qty', 
        'Reason for Return'
    ])
    
    # Process each return - using data from database including customer names
    for return_row in returns:
        return_id = return_row['return_id']
        order_id = return_row['order_id']
        customer_name = return_row['customer_name'] if return_row['customer_name'] else ''
        
        # Check for return items first (LEFT JOIN to handle NULL product_ids)
        cursor.execute("""
            SELECT ri.id, COALESCE(p.sku, 'N/A') as sku,
                   COALESCE(p.name, 'Unknown Product') as name,
                   ri.quantity as order_quantity,
                   ri.quantity_received as return_quantity,
                   ri.return_reasons, ri.condition_on_arrival
            FROM return_items ri
            LEFT JOIN products p ON ri.product_id = p.id
            WHERE ri.return_id = %s
        """, (return_id,))
        items = cursor.fetchall()
        
        # Convert items to dict for Azure SQL
        if USE_AZURE_SQL:
            raw_items_count = len(items) if items else 0
            # Use explicit column names from the query instead of relying on cursor.description
            if items:
                columns = ['id', 'sku', 'name', 'order_quantity', 'return_quantity', 'return_reasons', 'condition_on_arrival']
                converted_items = []
                for row in items:
                    item_dict = {}
                    for i, col_name in enumerate(columns):
                        if i < len(row):
                            item_dict[col_name] = row[i]
                        else:
                            item_dict[col_name] = None
                    converted_items.append(item_dict)
                items = converted_items
            converted_items_count = len(items) if items else 0
            print(f"🔍 CSV CONVERSION DEBUG: Return {return_id} - raw: {raw_items_count} items, converted: {converted_items_count} items")
            if raw_items_count > 0 and converted_items_count == 0:
                print(f"🚨 CSV CONVERSION FAILED: Manual conversion returned empty for return {return_id}!")
        
        if items:
            # Write return items from database
            for item in items:
                reasons = ''
                if item['return_reasons']:
                    try:
                        reasons_data = json.loads(item['return_reasons'])
                        reasons = ', '.join(reasons_data) if isinstance(reasons_data, list) else str(reasons_data)
                    except:
                        reasons = str(item['return_reasons'])
                
                writer.writerow([
                    return_row['client_name'] or '',
                    customer_name,
                    return_row['order_date'] or '',
                    return_row['return_date'],
                    return_row['order_number'] or '',
                    item['name'] or '',
                    item['order_quantity'] or 0,  # Order Qty
                    item['return_quantity'] or 0,  # Return Qty
                    reasons
                ])
        else:
            # For returns without return_items, write a single row with basic info
            writer.writerow([
                return_row['client_name'] or '',
                customer_name,
                return_row['order_date'] or '',
                return_row['return_date'],
                return_row['order_number'] or '',
                'Return details not available',
                0,
                0,
                'Return items not in database'
            ])
    
    conn.close()
    
    # Return CSV as downloadable file
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"returns_export_{timestamp}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/analytics/return-reasons")
async def get_return_reasons():
    """Get analytics on return reasons"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT return_reasons, COUNT(*) as count
        FROM return_items
        WHERE return_reasons IS NOT NULL AND return_reasons != '[]'
        GROUP BY return_reasons
        ORDER BY count DESC
        {format_limit_clause(20)}
    """)
    
    reasons_count = {}
    for row in cursor.fetchall():
        reasons = json.loads(row[0]) if row[0] else []
        for reason in reasons:
            if reason in reasons_count:
                reasons_count[reason] += row[1]
            else:
                reasons_count[reason] = row[1]
    
    # Convert to list format
    result = [{"reason": k, "count": v} for k, v in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True)]
    
    conn.close()
    return result

@app.get("/api/analytics/top-returned-products")
async def get_top_returned_products():
    """Get top returned products"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT p.sku, p.name, SUM(ri.quantity) as total_quantity, COUNT(ri.id) as return_count
        FROM return_items ri
        JOIN products p ON ri.product_id = p.id
        GROUP BY p.id
        ORDER BY total_quantity DESC
        {format_limit_clause(10)}
    """)
    
    products = []
    for row in cursor.fetchall():
        products.append({
            "sku": row[0],
            "name": row[1],
            "total_quantity": row[2],
            "return_count": row[3]
        })
    
    conn.close()
    return products

@app.get("/api/test-database")
async def test_database_connection():
    """Test database connectivity and return detailed diagnostics"""
    try:
        # Test basic connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test simple query
        cursor.execute("SELECT 1 as test_value")
        result = cursor.fetchone()
        
        # Get database info
        database_type = "Azure SQL" if USE_AZURE_SQL else "SQLite"
        
        # Test if returns table exists
        table_exists = False
        returns_count = 0
        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns")
            result = cursor.fetchone()
            returns_count = result[0] if result else 0
            table_exists = True
        except Exception as table_error:
            table_exists = f"Error: {str(table_error)}"
        
        conn.close()
        
        return {
            "status": "success",
            "database_type": database_type,
            "connection": "working",
            "returns_table_exists": table_exists,
            "returns_count": returns_count,
            "drivers": {
                "pyodbc_available": 'pyodbc' in sys.modules or bool(globals().get('pyodbc')),
                "pymssql_available": 'pymssql' in sys.modules or bool(globals().get('pymssql'))
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_type": "Azure SQL" if USE_AZURE_SQL else "SQLite",
            "connection": "failed",
            "error_type": type(e).__name__,
            "drivers": {
                "pyodbc_available": 'pyodbc' in sys.modules or bool(globals().get('pyodbc')),
                "pymssql_available": 'pymssql' in sys.modules or bool(globals().get('pymssql'))
            }
        }

@app.get("/api/test-warehance")
async def test_warehance_api():
    """Test the Warehance API connection"""
    try:
        api_key = WAREHANCE_API_KEY
        
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }
        
        # Try to fetch just 1 return to test the API
        response = requests.get("https://api.warehance.com/v1/returns?limit=1", headers=headers)
        
        result = {
            "api_key_used": api_key[:15] + "...",
            "status_code": response.status_code,
            "success": response.status_code == 200
        }
        
        if response.status_code == 200:
            data = response.json()
            result["response_keys"] = list(data.keys()) if isinstance(data, dict) else "Not a dict"
            
            if 'data' in data and 'returns' in data['data']:
                result["returns_count"] = len(data['data']['returns'])
                result["total_count"] = data['data'].get('total_count', 0)
            else:
                result["error"] = "Unexpected response format"
                result["response_sample"] = str(data)[:200]
        else:
            result["error"] = response.text[:500]
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "api_key_used": (api_key[:15] + "...") if api_key else "No API key"
        }

@app.post("/api/sync/trigger")
async def trigger_sync(request_data: dict):
    """Trigger a sync with Warehance API"""
    global sync_status
    
    if sync_status["is_running"]:
        return {"message": "Sync already in progress", "status": "running"}
    
    # Start sync in background
    asyncio.create_task(run_sync())
    
    return {"message": "Sync started", "status": "started"}

@app.post("/api/database/migrate")
async def migrate_database():
    """Add missing columns to existing tables for Azure SQL"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL, migration not needed"}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        columns_added = []
        
        # Define missing columns for each table
        migrations = [
            ("returns", "tracking_number", "NVARCHAR(100)"),
            ("returns", "processed", "BIT DEFAULT 0"),
            ("returns", "api_id", "NVARCHAR(100)"),
            ("returns", "paid_by", "NVARCHAR(50)"),
            ("returns", "status", "NVARCHAR(50)"),
            ("returns", "created_at", "DATETIME"),
            ("returns", "updated_at", "DATETIME"),
            ("returns", "processed_at", "DATETIME"),
            ("returns", "warehouse_note", "NVARCHAR(MAX)"),
            ("returns", "customer_note", "NVARCHAR(MAX)"),
            ("returns", "tracking_url", "NVARCHAR(500)"),
            ("returns", "carrier", "NVARCHAR(100)"),
            ("returns", "service", "NVARCHAR(100)"),
            ("returns", "label_cost", "DECIMAL(10,2)"),
            ("returns", "label_pdf_url", "NVARCHAR(500)"),
            ("returns", "rma_slip_url", "NVARCHAR(500)"),
            ("returns", "label_voided", "BIT DEFAULT 0"),
            ("returns", "client_id", "INT"),
            ("returns", "warehouse_id", "INT"),
            ("returns", "order_id", "INT"),
            ("returns", "return_integration_id", "NVARCHAR(100)"),
            ("returns", "last_synced_at", "DATETIME"),
        ]
        
        for table_name, column_name, column_type in migrations:
            try:
                # Check if column exists
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
                """, (table_name, column_name))
                
                result = cursor.fetchone()
                exists = (result['count'] if USE_AZURE_SQL else result[0]) > 0
                
                if not exists:
                    # Add the column
                    cursor.execute(f"ALTER TABLE {table_name} ADD {column_name} {column_type}")
                    conn.commit()
                    columns_added.append(f"{table_name}.{column_name}")
            except Exception as e:
                print(f"Error adding column {table_name}.{column_name}: {e}")
        
        conn.close()
        
        return {
            "status": "success",
            "columns_added": columns_added,
            "message": f"Added {len(columns_added)} missing columns"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/database/reset")
async def reset_database():
    """Drop and recreate all tables (WARNING: This will delete all data!)"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL, reset not needed"}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Drop all tables in correct order (due to foreign keys)
        tables_to_drop = [
            'email_share_items',
            'return_items', 
            'email_history',
            'sync_logs',
            'settings',
            'returns',
            'products',
            'orders',
            'warehouses',
            'clients'
        ]
        
        dropped = []
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                conn.commit()
                dropped.append(table)
            except Exception as e:
                print(f"Error dropping {table}: {e}")
        
        # Now recreate using the init endpoint logic
        conn.close()
        
        # Call the init endpoint
        init_result = await initialize_database()
        
        return {
            "status": "success",
            "tables_dropped": dropped,
            "init_result": init_result,
            "message": "Database reset complete"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/database/init")
async def initialize_database():
    """Initialize database tables for Azure SQL"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL, initialization not needed"}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables exist and create them if not
        tables_created = []
        tables_skipped = []
        
        # Table definitions for Azure SQL
        table_definitions = {
            'clients': """
                CREATE TABLE clients (
                    id NVARCHAR(50) PRIMARY KEY,
                    name NVARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """,
            'warehouses': """
                CREATE TABLE warehouses (
                    id NVARCHAR(50) PRIMARY KEY,
                    name NVARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """,
            'orders': """
                CREATE TABLE orders (
                    id NVARCHAR(50) PRIMARY KEY,
                    order_number NVARCHAR(100),
                    customer_name NVARCHAR(255),
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """,
            'products': """
                CREATE TABLE products (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    sku NVARCHAR(100),
                    name NVARCHAR(500),
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """,
            'returns': """
                CREATE TABLE returns (
                    id NVARCHAR(50) PRIMARY KEY,
                    api_id NVARCHAR(100),
                    paid_by NVARCHAR(50),
                    status NVARCHAR(50),
                    created_at DATETIME,
                    updated_at DATETIME,
                    processed BIT DEFAULT 0,
                    processed_at DATETIME,
                    warehouse_note NVARCHAR(MAX),
                    customer_note NVARCHAR(MAX),
                    tracking_number NVARCHAR(100),
                    tracking_url NVARCHAR(500),
                    carrier NVARCHAR(100),
                    service NVARCHAR(100),
                    label_cost DECIMAL(10,2),
                    label_pdf_url NVARCHAR(500),
                    rma_slip_url NVARCHAR(500),
                    label_voided BIT DEFAULT 0,
                    client_id NVARCHAR(50),
                    warehouse_id NVARCHAR(50),
                    order_id NVARCHAR(50),
                    return_integration_id NVARCHAR(100),
                    last_synced_at DATETIME
                )
            """,
            'return_items': """
                CREATE TABLE return_items (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    return_id NVARCHAR(50),
                    product_id INT,
                    quantity INT DEFAULT 0,
                    return_reasons NVARCHAR(MAX),
                    condition_on_arrival NVARCHAR(MAX),
                    quantity_received INT DEFAULT 0,
                    quantity_rejected INT DEFAULT 0,
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """,
            'email_history': """
                CREATE TABLE email_history (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    client_id NVARCHAR(50),
                    client_name NVARCHAR(255),
                    recipient_email NVARCHAR(255),
                    subject NVARCHAR(500),
                    attachment_name NVARCHAR(255),
                    sent_date DATETIME DEFAULT GETDATE(),
                    sent_by NVARCHAR(100),
                    status NVARCHAR(50)
                )
            """,
            'email_share_items': """
                CREATE TABLE email_share_items (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    return_id NVARCHAR(50),
                    share_id INT,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """,
            'sync_logs': """
                CREATE TABLE sync_logs (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    status NVARCHAR(50),
                    items_synced INT DEFAULT 0,
                    started_at DATETIME DEFAULT GETDATE(),
                    completed_at DATETIME,
                    error_message NVARCHAR(MAX)
                )
            """,
            'settings': """
                CREATE TABLE settings (
                    [key] NVARCHAR(100) PRIMARY KEY,
                    value NVARCHAR(MAX),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """
        }
        
        for table_name, create_sql in table_definitions.items():
            try:
                # Check if table exists
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = %s
                """, (table_name,))
                
                result = cursor.fetchone()
                exists = (result['count'] if USE_AZURE_SQL else result[0]) > 0
                
                if not exists:
                    cursor.execute(create_sql)
                    conn.commit()
                    tables_created.append(table_name)
                else:
                    tables_skipped.append(table_name)
            except Exception as e:
                print(f"Error creating table {table_name}: {e}")
        
        conn.close()
        
        return {
            "status": "success",
            "tables_created": tables_created,
            "tables_already_existed": tables_skipped,
            "message": f"Created {len(tables_created)} tables, {len(tables_skipped)} already existed"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/sync/status")
async def get_sync_status():
    """Get current sync status"""
    global sync_status
    
    try:
        # Get last sync from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if last_synced_at column exists
        try:
            cursor.execute("""
                SELECT MAX(last_synced_at) as last_sync
                FROM returns
                WHERE last_synced_at IS NOT NULL
            """)
        except Exception as e:
            # Column doesn't exist, try to add it
            if "Invalid column name" in str(e):
                try:
                    cursor.execute("ALTER TABLE returns ADD last_synced_at DATETIME")
                    conn.commit()
                    cursor.execute("SELECT NULL as last_sync")
                except:
                    cursor.execute("SELECT NULL as last_sync")
            else:
                cursor.execute("SELECT NULL as last_sync")
        result = cursor.fetchone()
        
        # Handle both SQLite and Azure SQL
        last_sync_value = None
        if result:
            if USE_AZURE_SQL:
                last_sync_value = result[0] if result else None
            else:
                last_sync_value = result[0] if result else None
        
        if last_sync_value:
            sync_status["last_sync"] = last_sync_value
    
        conn.close()
        
        return {
            "current_sync": {
                "status": "running" if sync_status["is_running"] else "completed",
                "items_synced": sync_status["items_synced"]
            },
            "last_sync": sync_status["last_sync"],
            "last_sync_status": sync_status["last_sync_status"],
            "last_sync_message": sync_status["last_sync_message"],
            "deployment_version": DEPLOYMENT_VERSION,
            "sql_fix_applied": "YES - parameterized queries use ? not %s"
        }
    except Exception as e:
        print(f"Error in sync status: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return {
            "current_sync": {"status": "error", "items_synced": 0},
            "last_sync": None,
            "last_sync_status": "error",
            "last_sync_message": str(e),
            "deployment_version": DEPLOYMENT_VERSION,
            "sql_fix_applied": "YES - parameterized queries use ? not %s"
        }

def convert_date_for_sql(date_string):
    """Convert API date string to SQL Server compatible format"""
    if not date_string:
        return None
    
    try:
        # Parse the date string and convert to ISO format that SQL Server accepts
        from datetime import datetime
        # Handle multiple possible formats from API
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',     # ISO with microseconds
            '%Y-%m-%dT%H:%M:%SZ',        # ISO without microseconds
            '%Y-%m-%d %H:%M:%S',         # SQL format
            '%Y-%m-%dT%H:%M:%S.%f',      # ISO without Z
            '%Y-%m-%d',                  # Date only
            '%Y-%m-%dT%H:%M:%S',         # ISO without Z or microseconds
            '%d/%m/%Y %H:%M:%S',         # DD/MM/YYYY format
            '%m/%d/%Y %H:%M:%S',         # MM/DD/YYYY format
            '%Y-%m-%d %H:%M:%S.%f',      # SQL with microseconds
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_string, fmt)
                # Return in SQL Server compatible format
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        
        # If no format matches, return default date instead of None for SQL Server
        print(f"⚠️ Could not parse date '{date_string}', using default")
        return "1900-01-01 00:00:00"
    except Exception:
        # If all else fails, return default date instead of None for SQL Server
        print(f"⚠️ Date conversion error for '{date_string}', using default")
        return "1900-01-01 00:00:00"

async def run_sync():
    """Run the actual sync process"""
    global sync_status
    
    sync_status["is_running"] = True
    sync_status["items_synced"] = 0
    
    try:
        # Initialize database tables if using Azure SQL
        if USE_AZURE_SQL:
            init_result = await initialize_database()
            print(f"Database initialization result: {init_result}")
            if init_result.get("status") == "error":
                raise Exception(f"Database initialization failed: {init_result.get('message')}")
        
        # Use the configured API key
        api_key = WAREHANCE_API_KEY
        
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }
        
        print(f"Starting sync with API key: {api_key[:15]}...")
        sync_status["last_sync_message"] = f"Starting sync with API key: {api_key[:15]}..."
        
        # Test database connection early
        print("Testing database connection...")
        sync_status["last_sync_message"] = "Testing database connection..."
        
        conn = get_db_connection()
        if not conn:
            raise Exception("Failed to establish database connection")
            
        cursor = conn.cursor()
        
        # Test basic database operation
        try:
            if USE_AZURE_SQL:
                cursor.execute("SELECT 1 as test")
            else:
                cursor.execute("SELECT 1")
            test_result = cursor.fetchone()
            print(f"Database test query successful: {test_result}")
            sync_status["last_sync_message"] = "Database connection confirmed"
        except Exception as db_test_error:
            raise Exception(f"Database test query failed: {db_test_error}")
        
        # STEP 1: Fetch ALL returns from API with pagination
        sync_status["last_sync_message"] = "Fetching returns from Warehance API..."
        print("Starting to fetch returns from Warehance API...")
        all_order_ids = set()  # Collect unique order IDs
        offset = 0
        limit = 100
        total_fetched = 0
        
        while True:
            try:
                url = f"https://api.warehance.com/v1/returns?limit={limit}&offset={offset}"
                print(f"Fetching from: {url}")
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    error_text = response.text[:500] if response.text else "No response body"
                    print(f"API Error: Status {response.status_code}, Response: {error_text}")
                    sync_status["last_sync_message"] = f"API Error: {response.status_code} - {error_text[:100]}"
                    sync_status["last_sync_status"] = "error"
                    break
                
                data = response.json()
                print(f"API Response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
                
                # Check for API error response
                if data.get('status') == 'error':
                    error_msg = data.get('message', 'Unknown API error')
                    print(f"API returned error: {error_msg}")
                    sync_status["last_sync_message"] = f"API Error: {error_msg}"
                    break
                
                if 'data' not in data:
                    print(f"No 'data' key in API response. Response: {data}")
                    sync_status["last_sync_message"] = "Invalid API response format"
                    break
                
                if 'returns' not in data['data']:
                    print(f"No 'returns' key in data. Data keys: {data['data'].keys() if isinstance(data['data'], dict) else 'Not a dict'}")
                    sync_status["last_sync_message"] = "No returns data in API response"
                    break
                    
                returns_batch = data['data']['returns']
                print(f"Fetched {len(returns_batch)} returns at offset {offset}")
                sync_status["last_sync_message"] = f"Processing {len(returns_batch)} returns from offset {offset}..."
                
                if not returns_batch:
                    print("No more returns to process - breaking loop")
                    break
                
                for ret in returns_batch:
                    print(f"Processing return {ret.get('id', 'no-id')} from client {ret.get('client', {}).get('name', 'no-client')}")
                    # First ensure client and warehouse exist - with overflow protection
                    if ret.get('client'):
                        try:
                            client_id = ret['client']['id']
                            client_name = ret['client'].get('name', '')
                            
                            # Convert large IDs to string to prevent arithmetic overflow
                            if isinstance(client_id, int) and client_id > 2147483647:
                                client_id = str(client_id)
                            
                            if USE_AZURE_SQL:
                                # Use simple INSERT with ignore duplicate errors
                                try:
                                    placeholder = get_param_placeholder()
                                    cursor.execute(f"INSERT INTO clients (id, name) VALUES ({placeholder}, {placeholder})",
                                                 (client_id, client_name))
                                    try:
                                        conn.commit()
                                    except Exception as commit_err:
                                        if "no corresponding BEGIN TRANSACTION" not in str(commit_err):
                                            raise
                                except Exception as insert_err:
                                    # Ignore duplicate key errors, log others
                                    if "duplicate key" not in str(insert_err).lower() and "primary key" not in str(insert_err).lower():
                                        print(f"Non-duplicate client insert error: {insert_err}")
                            else:
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    INSERT OR IGNORE INTO clients (id, name) VALUES ({placeholder}, {placeholder})
                                """, (client_id, client_name))
                        except Exception as e:
                            print(f"Error handling client: {e}")
                
                    if ret.get('warehouse'):
                        try:
                            warehouse_id = ret['warehouse']['id']
                            warehouse_name = ret['warehouse'].get('name', '')
                            
                            # Convert large IDs to string to prevent arithmetic overflow
                            if isinstance(warehouse_id, int) and warehouse_id > 2147483647:
                                warehouse_id = str(warehouse_id)
                            
                            if USE_AZURE_SQL:
                                # Use simple INSERT with ignore duplicate errors
                                try:
                                    placeholder = get_param_placeholder()
                                    cursor.execute(f"INSERT INTO warehouses (id, name) VALUES ({placeholder}, {placeholder})",
                                                 (warehouse_id, warehouse_name))
                                    try:
                                        conn.commit()
                                    except Exception as commit_err:
                                        if "no corresponding BEGIN TRANSACTION" not in str(commit_err):
                                            raise
                                except Exception as insert_err:
                                    # Ignore duplicate key errors, log others
                                    if "duplicate key" not in str(insert_err).lower() and "primary key" not in str(insert_err).lower():
                                        print(f"Non-duplicate warehouse insert error: {insert_err}")
                            else:
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    INSERT OR IGNORE INTO warehouses (id, name) VALUES ({placeholder}, {placeholder})
                                """, (warehouse_id, warehouse_name))
                        except Exception as e:
                            print(f"Error handling warehouse: {e}")
                
                    # Collect order ID if present
                    if ret.get('order') and ret['order'].get('id'):
                        all_order_ids.add(ret['order']['id'])
                    
                    # Update or insert return - with overflow protection
                    return_id = ret['id']
                    # Convert large IDs to string to prevent arithmetic overflow
                    if isinstance(return_id, int) and return_id > 2147483647:
                        return_id = str(return_id)
                    
                    # Always use Azure SQL (SQLite logic removed)
                    # Use IF EXISTS for Azure SQL (simpler than MERGE)
                    cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id = %s", (return_id,))
                    return_result = cursor.fetchone()
                    exists = (return_result['count'] if USE_AZURE_SQL else return_result[0]) > 0

                    print(f"🔍 Return {return_id}: USE_AZURE_SQL={USE_AZURE_SQL}, exists={exists}")
                    print(f"   Taking Azure SQL path for return {return_id}")

                    if exists:
                        # Update existing return
                        print(f"   📅 Return {return_id} dates: created_at='{ret.get('created_at')}', updated_at='{ret.get('updated_at')}', processed_at='{ret.get('processed_at')}'")
                        # Safe access to nested objects with null checks
                        client_id = ret.get('client', {}).get('id') if ret.get('client') else None
                        warehouse_id = ret.get('warehouse', {}).get('id') if ret.get('warehouse') else None
                        order_id = ret.get('order', {}).get('id') if ret.get('order') else None
                        print(f"   🔢 Return {return_id} IDs: client_id='{client_id}', warehouse_id='{warehouse_id}', order_id='{order_id}'")
                        cursor.execute("""
                                UPDATE returns SET
                                    api_id = %s, paid_by = %s, status = %s, created_at = %s,
                                    updated_at = %s, processed = %s, processed_at = %s,
                                    warehouse_note = %s, customer_note = %s, tracking_number = %s,
                                    tracking_url = %s, carrier = %s, service = %s, label_cost = %s,
                                    label_pdf_url = %s, rma_slip_url = %s, label_voided = %s,
                                    client_id = %s, warehouse_id = %s, order_id = %s,
                                    return_integration_id = %s, last_synced_at = %s
                                WHERE id = %s
                            """, (
                                ret.get('api_id'), ret.get('paid_by', ''),
                                ret.get('status', ''), convert_date_for_sql(ret.get('created_at')), convert_date_for_sql(ret.get('updated_at')),
                                ret.get('processed', False), convert_date_for_sql(ret.get('processed_at')),
                                ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                                ret.get('tracking_number'), ret.get('tracking_url'),
                                ret.get('carrier', ''), ret.get('service', ''),
                                ret.get('label_cost'), ret.get('label_pdf_url'),
                                ret.get('rma_slip_url'), ret.get('label_voided', False),
                                str(ret['client']['id']) if ret.get('client') and ret['client'].get('id') else None,
                                str(ret['warehouse']['id']) if ret.get('warehouse') and ret['warehouse'].get('id') else None,
                                str(ret['order']['id']) if ret.get('order') and ret['order'].get('id') else None,
                                ret.get('return_integration_id'),
                                convert_date_for_sql(datetime.now().isoformat()),
                                return_id  # WHERE clause
                            ))
                    else:
                        # Insert new return
                        print(f"   📅 Return {return_id} dates: created_at='{ret.get('created_at')}', updated_at='{ret.get('updated_at')}', processed_at='{ret.get('processed_at')}'")
                        # Safe access to nested objects with null checks
                        client_id = ret.get('client', {}).get('id') if ret.get('client') else None
                        warehouse_id = ret.get('warehouse', {}).get('id') if ret.get('warehouse') else None
                        order_id = ret.get('order', {}).get('id') if ret.get('order') else None
                        print(f"   🔢 Return {return_id} IDs: client_id='{client_id}', warehouse_id='{warehouse_id}', order_id='{order_id}'")
                        cursor.execute("""
                                INSERT INTO returns (id, api_id, paid_by, status, created_at, updated_at,
                                        processed, processed_at, warehouse_note, customer_note,
                                        tracking_number, tracking_url, carrier, service,
                                        label_cost, label_pdf_url, rma_slip_url, label_voided,
                                        client_id, warehouse_id, order_id, return_integration_id,
                                        last_synced_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                return_id, ret.get('api_id'), ret.get('paid_by', ''),
                                ret.get('status', ''), convert_date_for_sql(ret.get('created_at')), convert_date_for_sql(ret.get('updated_at')),
                                ret.get('processed', False), convert_date_for_sql(ret.get('processed_at')),
                                ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                                ret.get('tracking_number'), ret.get('tracking_url'),
                                ret.get('carrier', ''), ret.get('service', ''),
                                ret.get('label_cost'), ret.get('label_pdf_url'),
                                ret.get('rma_slip_url'), ret.get('label_voided', False),
                                str(ret['client']['id']) if ret.get('client') and ret['client'].get('id') else None,
                                str(ret['warehouse']['id']) if ret.get('warehouse') and ret['warehouse'].get('id') else None,
                                str(ret['order']['id']) if ret.get('order') and ret['order'].get('id') else None,
                                ret.get('return_integration_id'),
                                convert_date_for_sql(datetime.now().isoformat())
                            ))
                
                # Also store basic order info from return data
                if ret.get('order'):
                    order = ret['order']
                    try:
                        if USE_AZURE_SQL:
                            # Check if order exists first
                            cursor.execute("SELECT COUNT(*) as count FROM orders WHERE id = %s", (str(order['id']),))
                            order_result = cursor.fetchone()
                            if (order_result['count'] if USE_AZURE_SQL else order_result[0]) == 0:
                                cursor.execute("""
                                    INSERT INTO orders (id, order_number, created_at, updated_at)
                                    VALUES (%s, %s, GETDATE(), GETDATE())
                                """, (str(order['id']), order.get('order_number', '')))
                        else:
                            cursor.execute("""
                                INSERT INTO orders (id, order_number, created_at, updated_at)
                                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """, (str(order['id']), order.get('order_number', '')))
                    except Exception as e:
                        print(f"Error inserting order {str(order['id'])}: {e}")
                
                # Store return items if present
                if ret.get('items'):
                    for item in ret['items']:
                        # Get or create product
                        product_id = item.get('product', {}).get('id', 0)
                        product_sku = item.get('product', {}).get('sku', '')
                        product_name = item.get('product', {}).get('name', '')
                        
                        # If product doesn't exist or has no ID, try to find by SKU or create a placeholder
                        if product_id == 0 and product_sku:
                            # Try to find existing product by SKU
                            cursor.execute("SELECT id as product_id FROM products WHERE sku = %s", (product_sku,))
                            existing = cursor.fetchone()
                            if existing:
                                product_id = existing[0]
                            else:
                                # Create a placeholder product
                                cursor.execute("""
                                    INSERT INTO products (sku, name, created_at, updated_at)
                                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (product_sku, product_name or 'Unknown Product'))
                                product_id = cursor.lastrowid
                        elif product_id > 0:
                            # Ensure product exists
                            if USE_AZURE_SQL:
                                cursor.execute("SELECT COUNT(*) as count FROM products WHERE id = %s", (product_id,))
                                product_result = cursor.fetchone()
                                if (product_result['count'] if USE_AZURE_SQL else product_result[0]) == 0:
                                    # Need separate statements for IDENTITY_INSERT
                                    cursor.execute("SET IDENTITY_INSERT products ON")
                                    cursor.execute("""
                                        INSERT INTO products (id, sku, name, created_at, updated_at)
                                        VALUES (%s, %s, %s, GETDATE(), GETDATE())
                                    """, (product_id, product_sku, product_name))
                                    cursor.execute("SET IDENTITY_INSERT products OFF")
                            else:
                                cursor.execute("""
                                    INSERT INTO products (id, sku, name, created_at, updated_at)
                                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (product_id, product_sku, product_name))
                        
                        # Store return item
                        import json
                        if USE_AZURE_SQL:
                            # Check if return item exists
                            if item.get('id'):
                                cursor.execute("SELECT COUNT(*) as count FROM return_items WHERE id = %s", (item['id'],))
                                item_result = cursor.fetchone()
                                if (item_result['count'] if USE_AZURE_SQL else item_result[0]) == 0:
                                    cursor.execute("SET IDENTITY_INSERT return_items ON")
                                    cursor.execute("""
                                        INSERT INTO return_items (
                                            id, return_id, product_id, quantity,
                                            return_reasons, condition_on_arrival,
                                            quantity_received, quantity_rejected,
                                            created_at, updated_at
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, GETDATE(), GETDATE())
                                    """, (
                                        item.get('id'),
                                        return_id,
                                        product_id if product_id > 0 else None,
                                        item.get('quantity', 0),
                                        json.dumps(item.get('return_reasons', [])),
                                        json.dumps(item.get('condition_on_arrival', [])),
                                        item.get('quantity_received', 0),
                                        item.get('quantity_rejected', 0)
                                    ))
                                    cursor.execute("SET IDENTITY_INSERT return_items OFF")
                            else:
                                # No ID provided, let SQL generate one
                                cursor.execute("""
                                    INSERT INTO return_items (
                                        return_id, product_id, quantity,
                                        return_reasons, condition_on_arrival,
                                        quantity_received, quantity_rejected,
                                        created_at, updated_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, GETDATE(), GETDATE())
                                """, (
                                    return_id,
                                    product_id if product_id > 0 else None,
                                    item.get('quantity', 0),
                                    json.dumps(item.get('return_reasons', [])),
                                    json.dumps(item.get('condition_on_arrival', [])),
                                    item.get('quantity_received', 0),
                                    item.get('quantity_rejected', 0)
                                ))
                        else:
                            cursor.execute("""
                                INSERT OR REPLACE INTO return_items (
                                id, return_id, product_id, quantity,
                                return_reasons, condition_on_arrival,
                                quantity_received, quantity_rejected,
                                created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (
                            item.get('id'),
                            return_id,
                            product_id if product_id > 0 else None,
                            item.get('quantity', 0),
                            json.dumps(item.get('return_reasons', [])),
                            json.dumps(item.get('condition_on_arrival', [])),
                            item.get('quantity_received', 0),
                            item.get('quantity_rejected', 0)
                        ))
                    
                    print(f"About to increment counter for return {return_id}")
                    sync_status["items_synced"] += 1
                    print(f"Successfully processed return {return_id}, total synced: {sync_status['items_synced']}")
                
                total_fetched += len(returns_batch)
                
                # Check if we've fetched all returns
                total_count = data['data'].get('total_count', 0)
                if total_fetched >= total_count or len(returns_batch) < limit:
                    break
                    
                offset += limit
            except Exception as e:
                print(f"Error in sync loop: {e}")
                sync_status["last_sync_message"] = f"Error: {str(e)[:100]}"
                break
            
            # Add a small delay to avoid overwhelming the API
            await asyncio.sleep(0.5)
        
        # STEP 2: Fetch full order details for all collected order IDs (with customer names)
        sync_status["last_sync_message"] = f"Fetching {len(all_order_ids)} orders with customer info..."
        
        # Check which orders need customer name updates
        if all_order_ids:
            cursor.execute("""
                SELECT id FROM orders 
                WHERE id IN ({}) 
                AND (customer_name IS NULL OR customer_name = '')
            """.format(format_in_clause(len(all_order_ids))), tuple(all_order_ids))
            orders_needing_update = [row[0] for row in cursor.fetchall()]
        else:
            orders_needing_update = []
        customers_updated = 0
        
        # Fetch order details in batches (limit to avoid timeout)
        batch_size = 20  # Fetch 20 orders at a time
        for i in range(0, min(len(orders_needing_update), 500), batch_size):  # Max 500 orders per sync
            batch = orders_needing_update[i:i+batch_size]
            
            for order_id in batch:
                try:
                    order_response = requests.get(
                        f"https://api.warehance.com/v1/orders/{order_id}",
                        headers=headers,
                        timeout=5
                    )
                    if order_response.status_code == 200:
                        order_data = order_response.json().get('data', {})
                        customer_name = ''
                        
                        # Extract customer name from ship_to_address
                        if order_data.get('ship_to_address'):
                            ship_addr = order_data['ship_to_address']
                            first = ship_addr.get('first_name', '')
                            last = ship_addr.get('last_name', '')
                            customer_name = f"{first} {last}".strip()
                        
                        # Update order with full details including customer name
                        cursor.execute("""
                            UPDATE orders 
                            SET customer_name = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (customer_name, order_id))
                        
                        if customer_name:
                            customers_updated += 1
                    
                    # Small delay between API calls
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error fetching order {order_id}: {e}")
            
            # Update progress
            sync_status["last_sync_message"] = f"Fetched {i+len(batch)} of {min(len(orders_needing_update), 500)} orders..."
        
        try:
            conn.commit()
        except Exception as commit_err:
            if "no corresponding BEGIN TRANSACTION" not in str(commit_err):
                print(f"⚠️ Final commit error: {commit_err}")
                raise
            else:
                print(f"⚠️ Ignoring final commit transaction state error")
        conn.close()
        
        # Only mark as success if we actually synced something
        if sync_status['items_synced'] > 0:
            sync_status["last_sync_status"] = "success"
            sync_status["last_sync_message"] = f"Synced {sync_status['items_synced']} returns, updated {customers_updated} customer names"
        else:
            sync_status["last_sync_status"] = "warning"
            sync_status["last_sync_message"] = "No returns found to sync. Check API connection and logs."
        
        sync_status["last_sync"] = datetime.now().isoformat()
            
    except Exception as e:
        import traceback
        error_details = f"Sync error: {type(e).__name__}: {str(e)}"
        traceback_str = traceback.format_exc()
        print(f"SYNC FAILED: {error_details}")
        print(f"Traceback: {traceback_str}")
        
        sync_status["last_sync_status"] = "error"
        sync_status["last_sync_message"] = f"{error_details[:100]}... (check logs for full details)"
        
        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass
    
    finally:
        sync_status["is_running"] = False
        print(f"Sync completed. Status: {sync_status['last_sync_status']}, Items: {sync_status['items_synced']}")

@app.post("/api/returns/send-email")
async def send_returns_email(request_data: dict):
    """Send returns report via email to client"""
    try:
        client_id = request_data.get('client_id')
        recipient_email = request_data.get('email')
        date_range = request_data.get('date_range', 'Last 30 days')
        custom_message = request_data.get('message', '')
        
        if not recipient_email:
            raise HTTPException(status_code=400, detail="Recipient email is required")
        
        # Get client info and statistics
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get client name
        client_name = "All Clients"
        if client_id:
            cursor.execute("SELECT name as client_name FROM clients WHERE id = %s", (client_id,))
            result = cursor.fetchone()
            if result:
                client_name = result[0]
        
        # Get statistics
        where_clause = "WHERE 1=1"
        params = []
        if client_id:
            where_clause += " AND r.client_id = %s"
            params.append(client_id)
        
        # Total returns
        cursor.execute(f"SELECT COUNT(*) as count FROM returns r {where_clause}", params)
        row = cursor.fetchone()
        total_returns = row[0] if row else 0
        
        # Processed returns
        cursor.execute(f"SELECT COUNT(*) as count FROM returns r {where_clause} AND r.processed = 1", params)
        row = cursor.fetchone()
        processed_returns = row[0] if row else 0
        
        # Pending returns
        pending_returns = total_returns - processed_returns
        
        # Total items
        cursor.execute(f"""
            SELECT COUNT(ri.id) 
            FROM return_items ri 
            JOIN returns r ON ri.return_id = r.id 
            {where_clause}
        """, params)
        row = cursor.fetchone()
        total_items = row[0] if row else 0
        
        # Top return reason
        cursor.execute(f"""
            SELECT ri.return_reasons, COUNT(*) as count
            FROM return_items ri
            JOIN returns r ON ri.return_id = r.id
            {where_clause} AND ri.return_reasons IS NOT NULL
            GROUP BY ri.return_reasons
            ORDER BY count DESC
            {format_limit_clause(1)}
        """, params)
        result = cursor.fetchone()
        top_reason = result[0] if result else "N/A"
        
        # Generate CSV export
        export_params = {'client_id': client_id} if client_id else {}
        csv_data = await export_returns_csv(export_params)
        csv_content = csv_data.body.decode('utf-8') if hasattr(csv_data.body, 'decode') else str(csv_data.body)
        
        # Prepare email
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_CONFIG['SENDER_EMAIL'] if EMAIL_CONFIG else "returns@company.com"
        msg['To'] = recipient_email
        msg['Subject'] = f"Returns Report - {client_name} - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Prepare template variables
        template_vars = {
            'client_name': client_name,
            'report_date': datetime.now().strftime('%B %d, %Y'),
            'date_range': date_range,
            'total_returns': total_returns,
            'processed_returns': processed_returns,
            'pending_returns': pending_returns,
            'total_items': total_items,
            'top_reason': top_reason,
            'avg_processing_time': 'N/A',  # Can be calculated if needed
            'attachment_name': f'returns_report_{client_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.csv',
            'year': datetime.now().year,
            'custom_message': custom_message
        }
        
        # Create email body
        if EMAIL_TEMPLATE:
            html_body = EMAIL_TEMPLATE.format(**template_vars)
            plain_body = EMAIL_TEMPLATE_PLAIN.format(**template_vars)
        else:
            # Simple fallback template
            html_body = f"""
            <html>
                <body>
                    <h2>Returns Report for {client_name}</h2>
                    <p>Please find attached your returns report.</p>
                    <p><strong>Summary:</strong></p>
                    <ul>
                        <li>Total Returns: {total_returns}</li>
                        <li>Processed: {processed_returns}</li>
                        <li>Pending: {pending_returns}</li>
                    </ul>
                    {f'<p>{custom_message}</p>' if custom_message else ''}
                </body>
            </html>
            """
            plain_body = f"""
            Returns Report for {client_name}
            
            Please find attached your returns report.
            
            Summary:
            - Total Returns: {total_returns}
            - Processed: {processed_returns}
            - Pending: {pending_returns}
            
            {custom_message if custom_message else ''}
            """
        
        # Attach HTML and plain text
        msg.attach(MIMEText(plain_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Attach CSV file
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(csv_content.encode('utf-8'))
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename="{template_vars["attachment_name"]}"'
        )
        msg.attach(attachment)
        
        # Send email (configure SMTP settings)
        auth_password = EMAIL_CONFIG.get('AUTH_PASSWORD') or EMAIL_CONFIG.get('SENDER_PASSWORD')
        if EMAIL_CONFIG and auth_password:
            server = smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT'])
            server.starttls()
            # Login with auth account (personal account with Send As permissions for shared mailbox)
            auth_email = EMAIL_CONFIG.get('AUTH_EMAIL', EMAIL_CONFIG['SENDER_EMAIL'])
            server.login(auth_email, auth_password)
            server.send_message(msg)
            server.quit()
            
            # Log to email history
            cursor.execute("""
                INSERT INTO email_history (client_id, client_name, recipient_email, subject, attachment_name, sent_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                client_id,
                client_name,
                recipient_email,
                msg['Subject'],
                template_vars["attachment_name"],
                'System',
                'sent'
            ))
            conn.commit()
            
            status = "sent"
            message = "Email sent successfully!"
        else:
            # Save to email history as draft since SMTP not configured
            cursor.execute("""
                INSERT INTO email_history (client_id, client_name, recipient_email, subject, attachment_name, sent_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                client_id,
                client_name,
                recipient_email,
                msg['Subject'],
                template_vars["attachment_name"],
                'System',
                'draft'
            ))
            conn.commit()
            
            status = "draft"
            message = "Email prepared but not sent (SMTP not configured). Email saved as draft."
        
        conn.close()
        
        return {
            "status": status,
            "message": message,
            "recipient": recipient_email,
            "subject": msg['Subject']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email-history")
async def get_email_history(client_id: Optional[int] = None):
    """Get email history with optional client filter"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM email_history WHERE 1=1"
    params = []
    
    if client_id:
        query += " AND client_id = %s"
        params.append(client_id)
    
    query += " ORDER BY sent_date DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    if USE_AZURE_SQL:
        emails = rows_to_dict(cursor, rows) if rows else []
    else:
        emails = [dict(row) for row in rows]
    
    conn.close()
    
    return emails

@app.get("/api/email-config")
async def get_email_config():
    """Get email configuration status"""
    auth_configured = EMAIL_CONFIG.get('AUTH_PASSWORD') or EMAIL_CONFIG.get('SENDER_PASSWORD')
    is_configured = bool(EMAIL_CONFIG and auth_configured)
    
    return {
        "is_configured": is_configured,
        "sender_email": EMAIL_CONFIG['SENDER_EMAIL'] if EMAIL_CONFIG else None,
        "smtp_server": EMAIL_CONFIG['SMTP_SERVER'] if EMAIL_CONFIG else None
    }

@app.post("/api/email-config")
async def update_email_config(config: dict):
    """Update email configuration"""
    global EMAIL_CONFIG
    
    if not EMAIL_CONFIG:
        EMAIL_CONFIG = {}
    
    EMAIL_CONFIG.update(config)
    
    return {"status": "success", "message": "Email configuration updated"}

@app.get("/settings")
async def settings_page():
    """Serve the settings page"""
    # Check multiple possible paths for templates
    import os
    possible_paths = [
        "web/templates/settings.html",  # When running from root
        "templates/settings.html",       # When running from web directory
        "/home/site/wwwroot/web/templates/settings.html",  # Azure absolute path
        os.path.join(os.path.dirname(__file__), "templates", "settings.html")  # Relative to this file
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    
    # If no template found, return error with debug info
    return {"error": "Settings template not found", "searched_paths": possible_paths, "cwd": os.getcwd()}

@app.get("/api/settings")
async def get_settings():
    """Get all system settings"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create settings table if it doesn't exist
    if USE_AZURE_SQL:
        # Check if table exists first
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'settings'
        """)
        settings_result = cursor.fetchone()
        if (settings_result['count'] if USE_AZURE_SQL else settings_result[0]) == 0:
            cursor.execute("""
                CREATE TABLE settings (
                    [key] NVARCHAR(100) PRIMARY KEY,
                    value NVARCHAR(MAX),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """)
            conn.commit()
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    
    # Get all settings
    cursor.execute("SELECT key, value FROM settings")
    settings_rows = cursor.fetchall()
    
    # Convert rows for Azure SQL
    if USE_AZURE_SQL:
        settings_rows = rows_to_dict(cursor, settings_rows) if settings_rows else []
    
    # Convert to dictionary
    settings = {}
    for row in settings_rows:
        try:
            # Try to parse as JSON for complex values
            settings[row['key']] = json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            # If not JSON, use as string
            settings[row['key']] = row['value']
    
    # Add current EMAIL_CONFIG if available
    if EMAIL_CONFIG:
        settings['smtp_server'] = EMAIL_CONFIG.get('SMTP_SERVER', '')
        settings['smtp_port'] = EMAIL_CONFIG.get('SMTP_PORT', 587)
        settings['use_tls'] = EMAIL_CONFIG.get('USE_TLS', True)
        settings['auth_email'] = EMAIL_CONFIG.get('AUTH_EMAIL', '')
        settings['sender_email'] = EMAIL_CONFIG.get('SENDER_EMAIL', '')
        settings['sender_name'] = EMAIL_CONFIG.get('SENDER_NAME', '')
    
    conn.close()
    
    return settings

@app.post("/api/settings")
async def save_settings(settings: dict):
    """Save system settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create settings table if it doesn't exist
    if USE_AZURE_SQL:
        # Check if table exists first
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'settings'
        """)
        settings_result = cursor.fetchone()
        if (settings_result['count'] if USE_AZURE_SQL else settings_result[0]) == 0:
            cursor.execute("""
                CREATE TABLE settings (
                    [key] NVARCHAR(100) PRIMARY KEY,
                    value NVARCHAR(MAX),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            """)
            conn.commit()
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # Update each setting
    for key, value in settings.items():
        # Convert complex values to JSON
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        if USE_AZURE_SQL:
            # Check if setting exists
            cursor.execute("SELECT COUNT(*) as count FROM settings WHERE [key] = %s", (key,))
            setting_result = cursor.fetchone()
            if (setting_result['count'] if USE_AZURE_SQL else setting_result[0]) > 0:
                # Update existing
                cursor.execute("""
                    UPDATE settings 
                    SET value = %s, updated_at = %s
                    WHERE [key] = %s
                """, (value_str, datetime.now().isoformat(), key))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO settings ([key], value, updated_at)
                    VALUES (%s, %s, %s)
                """, (key, value_str, datetime.now().isoformat()))
        else:
            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, %s)
            """, (key, value_str, datetime.now().isoformat()))
    
    conn.commit()
    
    # Update EMAIL_CONFIG if email settings are provided
    global EMAIL_CONFIG
    if not EMAIL_CONFIG:
        EMAIL_CONFIG = {}
    
    if 'smtp_server' in settings:
        EMAIL_CONFIG['SMTP_SERVER'] = settings['smtp_server']
    if 'smtp_port' in settings:
        EMAIL_CONFIG['SMTP_PORT'] = int(settings['smtp_port'])
    if 'use_tls' in settings:
        EMAIL_CONFIG['USE_TLS'] = bool(settings['use_tls'])
    if 'sender_email' in settings:
        EMAIL_CONFIG['SENDER_EMAIL'] = settings['sender_email']
    if 'sender_name' in settings:
        EMAIL_CONFIG['SENDER_NAME'] = settings['sender_name']
    if 'auth_email' in settings:
        EMAIL_CONFIG['AUTH_EMAIL'] = settings['auth_email']
    if 'auth_password' in settings:
        EMAIL_CONFIG['AUTH_PASSWORD'] = settings['auth_password']
    if 'smtp_password' in settings:
        # Legacy support
        EMAIL_CONFIG['SENDER_PASSWORD'] = settings['smtp_password']
    
    conn.close()
    
    return {"status": "success", "message": "Settings saved successfully"}

@app.post("/api/test-email-oauth")
async def test_email_oauth(config: dict):
    """Test OAuth email configuration by sending a test email"""
    try:
        # Validate required fields
        if not config.get('tenant_id'):
            raise HTTPException(status_code=400, detail="Tenant ID is required")
        if not config.get('client_id'):
            raise HTTPException(status_code=400, detail="Client ID is required")
        if not config.get('client_secret'):
            raise HTTPException(status_code=400, detail="Client Secret is required")
        if not config.get('test_recipient'):
            raise HTTPException(status_code=400, detail="Test recipient email is required")
        
        # Initialize Graph mailer
        mailer = MicrosoftGraphMailer(
            tenant_id=config['tenant_id'],
            client_id=config['client_id'],
            client_secret=config['client_secret']
        )
        
        # Get access token
        token = mailer.get_access_token()
        
        # Prepare test email
        sender_email = config.get('sender_email', 'returns@uptimeops.net')
        test_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Test Email Successful!</h2>
            <p>This is a test email from your Warehance Returns system using Microsoft Graph API.</p>
            <p>Your OAuth2 configuration is working correctly.</p>
            <hr>
            <p><strong>Configuration Details:</strong></p>
            <ul>
                <li>Tenant ID: {config['tenant_id'][:8]}...</li>
                <li>Client ID: {config['client_id'][:8]}...</li>
                <li>Sender: {sender_email}</li>
                <li>Authentication: OAuth2 with Microsoft Graph</li>
            </ul>
        </body>
        </html>
        """
        
        # Send test email
        result = mailer.send_mail(
            from_address=sender_email,
            to_address=config['test_recipient'],
            subject="Warehance Returns - OAuth Test Email",
            body_html=test_body
        )
        
        return {"status": "success", "message": "OAuth test email sent successfully!"}
        
    except Exception as e:
        print(f"OAuth test email error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/test-email")
async def test_email(config: dict):
    """Test email configuration by sending a test email"""
    try:
        import traceback
        print(f"Test email config received: {config}")  # Debug logging
        # Validate required fields
        if not config.get('smtp_server'):
            raise HTTPException(status_code=400, detail="SMTP server is required")
        if not config.get('auth_email'):
            raise HTTPException(status_code=400, detail="Authentication email is required")
        if not config.get('auth_password'):
            raise HTTPException(status_code=400, detail="Authentication password is required")
        if not config.get('test_recipient'):
            raise HTTPException(status_code=400, detail="Test recipient email is required")
        
        # Get port with default value
        try:
            smtp_port = int(config.get('smtp_port', 587)) if config.get('smtp_port') else 587
        except ValueError:
            smtp_port = 587
        
        # Create test SMTP connection
        if config.get('use_tls'):
            server = smtplib.SMTP(config['smtp_server'], smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config['smtp_server'], smtp_port)
        
        # Try to login with auth account (personal account with Send As permissions)
        auth_email = config.get('auth_email') or config.get('sender_email')
        auth_password = config.get('auth_password') or config.get('smtp_password', '')
        
        if not auth_email or not auth_password:
            raise HTTPException(status_code=400, detail="Authentication credentials are required")
            
        server.login(auth_email, auth_password)
        
        # Create test message
        msg = MIMEMultipart()
        sender_email = config.get('sender_email') or config.get('auth_email')
        sender_name = config.get('sender_name', 'Warehance Returns')
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = config['test_recipient']
        msg['Subject'] = "Warehance Returns - Test Email"
        
        # Create test body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Test Email Successful!</h2>
            <p>This is a test email from your Warehance Returns system.</p>
            <p>Your email configuration is working correctly.</p>
            <hr>
            <p><strong>Configuration Details:</strong></p>
            <ul>
                <li>SMTP Server: {config['smtp_server']}</li>
                <li>Port: {config['smtp_port']}</li>
                <li>Sender: {config['sender_email']}</li>
                <li>TLS: {'Yes' if config.get('use_tls') else 'No'}</li>
            </ul>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return {"status": "success", "message": "Test email sent successfully!"}
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"Authentication error: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed. Please check your email and password.")
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")
        raise HTTPException(status_code=400, detail=f"SMTP error: {str(e)}")
    except Exception as e:
        print(f"Test email error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/api/deployment/version")
async def get_deployment_version():
    """Simple endpoint to verify deployment version"""
    import datetime
    return {
        "version": "2025-09-10-COMPREHENSIVE-OVERFLOW-FIX-V10-DIRECT-SYNC-TEST", 
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "latest_deployment_active"
    }

@app.get("/api/database/diagnose")
async def diagnose_azure_sql():
    """Comprehensive Azure SQL diagnostic endpoint"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL"}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        diagnostics = {
            "connection": "working",
            "current_user": None,
            "database_name": None,
            "schema_info": {},
            "permissions": {},
            "tables": {},
            "simple_create_test": None,
            "detailed_errors": []
        }
        
        try:
            # Get current user
            cursor.execute("SELECT USER_NAME() as user_name")
            result = cursor.fetchone()
            diagnostics["current_user"] = result['user_name'] if result else "No result"
        except Exception as e:
            import traceback
            error_details = f"USER_NAME() error: {type(e).__name__}: {str(e)}"
            if hasattr(e, 'args') and e.args:
                error_details += f" Args: {e.args}"
            diagnostics["detailed_errors"].append(error_details)
            diagnostics["detailed_errors"].append(f"Traceback: {traceback.format_exc()}")
        
        try:
            # Get database name
            cursor.execute("SELECT DB_NAME() as database_name")
            result = cursor.fetchone()
            diagnostics["database_name"] = result['database_name'] if result else "No result"
        except Exception as e:
            import traceback
            error_details = f"DB_NAME() error: {type(e).__name__}: {str(e)}"
            if hasattr(e, 'args') and e.args:
                error_details += f" Args: {e.args}"
            diagnostics["detailed_errors"].append(error_details)
            diagnostics["detailed_errors"].append(f"Traceback: {traceback.format_exc()}")
        
        try:
            # Check schema permissions
            cursor.execute("SELECT SCHEMA_NAME() as schema_name")
            schema_result = cursor.fetchone()
            diagnostics["schema_info"]["current_schema"] = (schema_result['schema_name'] if USE_AZURE_SQL else schema_result[0])
        except Exception as e:
            diagnostics["detailed_errors"].append(f"SCHEMA_NAME() error: {str(e)}")
        
        try:
            # Check table creation permissions with a simple test
            cursor.execute("CREATE TABLE test_permissions_check (id INT)")
            diagnostics["simple_create_test"] = "SUCCESS - Can create tables"
            
            # Clean up test table
            cursor.execute("DROP TABLE test_permissions_check")
        except Exception as e:
            diagnostics["simple_create_test"] = f"FAILED - Cannot create tables: {str(e)}"
            diagnostics["detailed_errors"].append(f"CREATE TABLE test failed: {str(e)}")
        
        try:
            # List existing tables
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
            tables = cursor.fetchall()
            diagnostics["tables"]["existing_tables"] = [row[0] for row in tables] if tables else []
        except Exception as e:
            diagnostics["detailed_errors"].append(f"Table listing error: {str(e)}")
        
        try:
            # Check specific permissions
            cursor.execute("""
                SELECT 
                    p.permission_name,
                    p.state_desc,
                    pr.name as principal_name
                FROM sys.database_permissions p
                LEFT JOIN sys.database_principals pr ON p.grantee_principal_id = pr.principal_id
                WHERE p.major_id = 0
            """)
            perms = cursor.fetchall()
            diagnostics["permissions"]["database_permissions"] = [
                {"permission": row[0], "state": row[1], "principal": row[2]} 
                for row in perms
            ] if perms else []
        except Exception as e:
            diagnostics["detailed_errors"].append(f"Permission query error: {str(e)}")
        
        conn.close()
        
        return {
            "status": "success",
            "diagnostics": diagnostics
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "diagnostics": diagnostics if 'diagnostics' in locals() else {}
        }

@app.post("/api/database/migrate-bigint")
async def migrate_to_bigint():
    """Migrate existing INT columns to BIGINT for large API IDs"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL, migration not needed"}

        conn = get_db_connection()
        cursor = conn.cursor()

        migrations = []

        # SQL Server migration commands that properly handle constraints
        migration_steps = [
            {
                "description": "Drop primary key constraint on clients",
                "command": "ALTER TABLE clients DROP CONSTRAINT PK__clients__3213E83F6F2C7259",
                "ignore_error": True
            },
            {
                "description": "Alter clients.id to BIGINT",
                "command": "ALTER TABLE clients ALTER COLUMN id BIGINT NOT NULL"
            },
            {
                "description": "Recreate primary key on clients.id",
                "command": "ALTER TABLE clients ADD CONSTRAINT PK_clients_id PRIMARY KEY (id)"
            },
            {
                "description": "Drop primary key constraint on warehouses",
                "command": "ALTER TABLE warehouses DROP CONSTRAINT PK__warehous__3213E83FF88C1B96",
                "ignore_error": True
            },
            {
                "description": "Alter warehouses.id to BIGINT",
                "command": "ALTER TABLE warehouses ALTER COLUMN id BIGINT NOT NULL"
            },
            {
                "description": "Recreate primary key on warehouses.id",
                "command": "ALTER TABLE warehouses ADD CONSTRAINT PK_warehouses_id PRIMARY KEY (id)"
            },
            {
                "description": "Drop primary key constraint on orders",
                "command": "ALTER TABLE orders DROP CONSTRAINT PK__orders__3213E83F89CDD820",
                "ignore_error": True
            },
            {
                "description": "Alter orders.id to BIGINT",
                "command": "ALTER TABLE orders ALTER COLUMN id BIGINT NOT NULL"
            },
            {
                "description": "Recreate primary key on orders.id",
                "command": "ALTER TABLE orders ADD CONSTRAINT PK_orders_id PRIMARY KEY (id)"
            },
            {
                "description": "Drop primary key constraint on returns",
                "command": "ALTER TABLE returns DROP CONSTRAINT PK__returns__3213E83FA1C16B80",
                "ignore_error": True
            },
            {
                "description": "Alter returns.id to BIGINT",
                "command": "ALTER TABLE returns ALTER COLUMN id BIGINT NOT NULL"
            },
            {
                "description": "Recreate primary key on returns.id",
                "command": "ALTER TABLE returns ADD CONSTRAINT PK_returns_id PRIMARY KEY (id)"
            },
            {
                "description": "Alter returns foreign key columns to BIGINT",
                "command": "ALTER TABLE returns ALTER COLUMN client_id BIGINT"
            },
            {
                "description": "Alter returns.warehouse_id to BIGINT",
                "command": "ALTER TABLE returns ALTER COLUMN warehouse_id BIGINT"
            },
            {
                "description": "Alter returns.order_id to BIGINT",
                "command": "ALTER TABLE returns ALTER COLUMN order_id BIGINT"
            },
            {
                "description": "Alter return_items.return_id to BIGINT",
                "command": "ALTER TABLE return_items ALTER COLUMN return_id BIGINT"
            },
            {
                "description": "Alter email_history.client_id to BIGINT",
                "command": "ALTER TABLE email_history ALTER COLUMN client_id BIGINT"
            },
            {
                "description": "Alter email_share_items.return_id to BIGINT",
                "command": "ALTER TABLE email_share_items ALTER COLUMN return_id BIGINT"
            }
        ]

        for step in migration_steps:
            try:
                cursor.execute(step["command"])
                conn.commit()
                migrations.append({
                    "description": step["description"],
                    "command": step["command"],
                    "status": "success"
                })
            except Exception as e:
                error_msg = str(e)
                if step.get("ignore_error", False) and ("does not exist" in error_msg or "is not a constraint" in error_msg):
                    migrations.append({
                        "description": step["description"],
                        "command": step["command"],
                        "status": "skipped",
                        "error": "Constraint already dropped or doesn't exist"
                    })
                else:
                    migrations.append({
                        "description": step["description"],
                        "command": step["command"],
                        "status": "error",
                        "error": error_msg
                    })

        conn.close()

        success_count = len([m for m in migrations if m['status'] == 'success'])
        return {
            "status": "success",
            "migrations": migrations,
            "message": f"Completed {success_count} migrations successfully"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/database/migrate-bigint")
async def migrate_to_bigint_get():
    """GET version of BIGINT migration for browser testing"""
    return await migrate_to_bigint()

@app.get("/api/database/migrate-bigint-v2")
async def migrate_to_bigint_v2():
    """V2 migration with dynamic constraint detection"""
    try:
        if not USE_AZURE_SQL:
            return {"status": "skipped", "message": "Not using Azure SQL, migration not needed"}

        conn = get_db_connection()
        cursor = conn.cursor()
        migrations = []

        # Tables to migrate
        tables = ['clients', 'warehouses', 'orders', 'returns']

        for table in tables:
            try:
                # Step 1: Find and drop primary key constraint
                cursor.execute(f"""
                    SELECT CONSTRAINT_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                    WHERE TABLE_NAME = '{table}' AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                """)
                pk_constraint = cursor.fetchone()

                if pk_constraint:
                    pk_name = pk_constraint[0]
                    cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {pk_name}")
                    conn.commit()
                    migrations.append({
                        "description": f"Drop primary key on {table}",
                        "command": f"DROP CONSTRAINT {pk_name}",
                        "status": "success"
                    })

                # Step 2: Alter column to BIGINT
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN id BIGINT NOT NULL")
                conn.commit()
                migrations.append({
                    "description": f"Alter {table}.id to BIGINT",
                    "command": f"ALTER COLUMN id BIGINT NOT NULL",
                    "status": "success"
                })

                # Step 3: Recreate primary key
                cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT PK_{table}_id PRIMARY KEY (id)")
                conn.commit()
                migrations.append({
                    "description": f"Recreate primary key on {table}",
                    "command": f"ADD CONSTRAINT PK_{table}_id PRIMARY KEY (id)",
                    "status": "success"
                })

            except Exception as e:
                migrations.append({
                    "description": f"Error migrating {table}",
                    "command": f"Full migration of {table}",
                    "status": "error",
                    "error": str(e)
                })

        # Step 4: Migrate foreign key columns
        fk_migrations = [
            ("returns", "client_id"),
            ("returns", "warehouse_id"),
            ("returns", "order_id"),
            ("return_items", "return_id"),
            ("email_history", "client_id"),
            ("email_share_items", "return_id")
        ]

        for table, column in fk_migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {column} BIGINT")
                conn.commit()
                migrations.append({
                    "description": f"Alter {table}.{column} to BIGINT",
                    "command": f"ALTER COLUMN {column} BIGINT",
                    "status": "success"
                })
            except Exception as e:
                migrations.append({
                    "description": f"Error migrating {table}.{column}",
                    "command": f"ALTER COLUMN {column} BIGINT",
                    "status": "error",
                    "error": str(e)
                })

        conn.close()

        success_count = len([m for m in migrations if m['status'] == 'success'])
        return {
            "status": "success",
            "migrations": migrations,
            "message": f"V2 Migration: Completed {success_count} steps successfully"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/database/reset-get")
async def reset_database_get():
    """GET version of database reset for browser testing"""
    return await reset_database()

@app.get("/api/sync/trigger-get")
async def trigger_sync_get():
    """GET version of sync trigger for browser testing"""
    # Provide default request data for GET trigger
    request_data = {"sync_type": "full"}
    return await trigger_sync(request_data)

@app.get("/api/sync/test-direct")
async def test_direct_sync():
    """Direct synchronous sync for debugging - bypasses background task"""
    global sync_status
    
    print("=== DIRECT SYNC TEST STARTING ===")
    
    try:
        # Test 1: Database connection
        print("Testing database connection...")
        conn = get_db_connection()
        if not conn:
            return {"error": "Failed to get database connection"}
        
        cursor = conn.cursor()
        
        # Test basic query
        try:
            if USE_AZURE_SQL:
                cursor.execute("SELECT 1 as test")
            else:
                cursor.execute("SELECT 1")
            test_result = cursor.fetchone()
            print(f"Database test successful: {test_result}")
        except Exception as db_err:
            return {"error": f"Database test failed: {db_err}"}
            
        # Test 2: API connection
        print("Testing API connection...")
        api_key = WAREHANCE_API_KEY
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }
        
        url = "https://api.warehance.com/v1/returns?limit=1&offset=0"
        print(f"Testing API call to: {url}")
        
        import requests
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return {"error": f"API test failed: {response.status_code} - {response.text[:200]}"}
            
        data = response.json()
        print(f"API test successful: {len(data.get('data', {}).get('returns', []))} returns found")
        
        # Test 3: Try to process one return
        if data.get('data', {}).get('returns'):
            first_return = data['data']['returns'][0]
            return_id = first_return.get('id')
            print(f"Attempting to process return {return_id}")
            
            try:
                # Check if return exists
                cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id = %s", (str(return_id),))
                result = cursor.fetchone()
                exists = (result['count'] if USE_AZURE_SQL else result[0]) > 0
                print(f"Return {return_id} exists in DB: {exists}")
                
                conn.close()
                
                return {
                    "success": True,
                    "database_connection": "OK",
                    "api_connection": "OK", 
                    "first_return_id": return_id,
                    "return_exists_in_db": exists,
                    "total_returns_available": data.get('data', {}).get('total_count', 0),
                    "message": "Direct sync test completed successfully"
                }
                
            except Exception as process_err:
                return {"error": f"Failed to process return: {process_err}"}
        else:
            return {"error": "No returns found in API response"}
            
    except Exception as e:
        import traceback
        return {
            "error": f"Direct sync test failed: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    import uvicorn
    # Use Azure's PORT environment variable if available
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8015)))
    uvicorn.run(app, host="0.0.0.0", port=port)