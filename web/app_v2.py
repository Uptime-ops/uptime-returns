"""
Enhanced FastAPI app with product details and CSV export
"""
import sys
import os

# VERSION IDENTIFIER - Update this when deploying
import datetime
DEPLOYMENT_VERSION = "V87.235-CSV-CORRUPTION-FIX"
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

# Try to import the new sync class with progress tracking - SAFE IMPORT
try:
    from scripts.sync_returns import WarehanceAPISync
    ENHANCED_SYNC_AVAILABLE = True
    print("✅ Enhanced sync system loaded successfully")
except ImportError as e:
    print(f"⚠️ Enhanced sync import failed: {e}")
    ENHANCED_SYNC_AVAILABLE = False
    WarehanceAPISync = None
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
    "items_synced": 0,
    "total_returns": 0,
    "new_returns": 0,
    "updated_returns": 0,
    "return_items_synced": 0,
    "products_synced": 0,
    "orders_synced": 0,
    "error_count": 0,
    "sync_start_time": None
}

# Helper functions for database row conversion
def row_to_dict(cursor, row):
    """Convert database row to dictionary for both SQLite and Azure SQL"""
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]

    # Debug logging to identify the issue
    print(f"DEBUG row_to_dict - columns: {columns}")
    print(f"DEBUG row_to_dict - row: {row}")
    print(f"DEBUG row_to_dict - row type: {type(row)}")

    result = dict(zip(columns, row))
    print(f"DEBUG row_to_dict - result: {result}")

    return result

def get_single_value(row, column_name, index=0):
    """Get single value from database row, handling both dict and tuple formats"""
    if row is None:
        return None

    # Try dictionary access first (Azure SQL fetchall case)
    if hasattr(row, 'get'):
        return row.get(column_name)

    # Try dictionary-like access (some row factories)
    try:
        return row[column_name]
    except (KeyError, TypeError):
        pass

    # Fall back to index access (tuple case)
    try:
        return row[index] if index < len(row) else None
    except (IndexError, TypeError):
        return None

def rows_to_dict(cursor, rows, columns=None):
    """Convert multiple database rows to list of dictionaries - Azure SQL compatible"""
    if not rows:
        return []

    # Check if rows are already dictionaries (Azure SQL case)
    if rows and isinstance(rows[0], dict):
        print(f"DEBUG rows_to_dict - rows already dictionaries, returning as-is")
        return rows

    # For tuple rows (SQLite case), convert to dictionaries
    if columns is None:
        if cursor.description:
            columns = [column[0] for column in cursor.description]
        else:
            print(f"WARNING: cursor.description is None, cannot convert rows to dict")
            return []

    print(f"DEBUG rows_to_dict - converting tuples to dictionaries")
    print(f"DEBUG rows_to_dict - columns: {columns}")
    print(f"DEBUG rows_to_dict - rows count: {len(rows)}")

    result = [dict(zip(columns, row)) for row in rows]
    return result

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
        stats['total_returns'] = get_single_value(row, 'count', 0)

        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 0")
        row = cursor.fetchone()
        stats['pending_returns'] = get_single_value(row, 'count', 0)

        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 1")
        row = cursor.fetchone()
        stats['processed_returns'] = get_single_value(row, 'count', 0)

        cursor.execute("SELECT COUNT(DISTINCT client_id) as count FROM returns WHERE client_id IS NOT NULL")
        row = cursor.fetchone()
        stats['total_clients'] = get_single_value(row, 'count', 0)

        cursor.execute("SELECT COUNT(DISTINCT warehouse_id) as count FROM returns WHERE warehouse_id IS NOT NULL")
        row = cursor.fetchone()
        stats['total_warehouses'] = get_single_value(row, 'count', 0)
    
        # Get return counts by time period
        if USE_AZURE_SQL:
            # Azure SQL syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)")
            row = cursor.fetchone()
            stats['returns_today'] = get_single_value(row, 'count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -7, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_week'] = get_single_value(row, 'count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -30, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_month'] = get_single_value(row, 'count', 0)
        else:
            # SQLite syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) = DATE('now')")
            row = cursor.fetchone()
            stats['returns_today'] = get_single_value(row, 'count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-7 days')")
            row = cursor.fetchone()
            stats['returns_this_week'] = get_single_value(row, 'count', 0)

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-30 days')")
            row = cursor.fetchone()
            stats['returns_this_month'] = get_single_value(row, 'count', 0)
    
        # Count of unshared returns
        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id NOT IN (SELECT return_id FROM email_share_items)")
            row = cursor.fetchone()
            stats['unshared_returns'] = get_single_value(row, 'count', 0)
        except:
            # Table might not exist yet
            stats['unshared_returns'] = stats['total_returns']
        
        # Get last sync time
        try:
            cursor.execute("SELECT MAX(completed_at) as last_sync FROM sync_logs WHERE status = 'completed'")
            row = cursor.fetchone()
            stats['last_sync'] = get_single_value(row, 'last_sync', 0)
        except:
            stats['last_sync'] = None
        
        # Get product statistics
        try:
            cursor.execute("SELECT COUNT(*) as count FROM products")
            row = cursor.fetchone()
            stats['total_products'] = get_single_value(row, 'count', 0)
        except:
            stats['total_products'] = 0
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM return_items")
            row = cursor.fetchone()
            stats['total_return_items'] = get_single_value(row, 'count', 0)
        except:
            stats['total_return_items'] = 0
        
        try:
            cursor.execute("SELECT SUM(quantity) as total FROM return_items")
            row = cursor.fetchone()
            stats['total_returned_quantity'] = get_single_value(row, 'total', 0)
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
            # Azure SQL returns dictionaries already, no conversion needed
            clients = rows if rows else []
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
            # Azure SQL returns dictionaries already, no conversion needed
            warehouses = rows if rows else []
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
           w.name as warehouse_name, r.client_id, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON CAST(r.client_id as BIGINT) = CAST(c.id as BIGINT)
    LEFT JOIN warehouses w ON CAST(r.warehouse_id as BIGINT) = CAST(w.id as BIGINT)
    LEFT JOIN orders o ON CAST(r.order_id as BIGINT) = CAST(o.id as BIGINT)
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
    cursor.execute(count_query, tuple(params))
    row = cursor.fetchone()
    total = get_single_value(row, 'total_count', 0)
    
    # Add pagination (different syntax for Azure SQL vs SQLite)
    if USE_AZURE_SQL:
        query += " ORDER BY r.created_at DESC OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
        params.extend([(page - 1) * limit, limit])
    else:
        query += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, (page - 1) * limit])

    cursor.execute(query, tuple(params))

    # Capture column description BEFORE fetchall() for Azure SQL
    columns = None
    if USE_AZURE_SQL:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        # print(f"DEBUG search_returns - USE_AZURE_SQL: {USE_AZURE_SQL}")
        # print(f"DEBUG search_returns - columns captured: {columns}")

    rows = cursor.fetchall()
    # print(f"DEBUG search_returns - rows count: {len(rows) if rows else 0}")
    # if rows:
        # print(f"DEBUG search_returns - first raw row: {rows[0]}")

    returns = []
    if USE_AZURE_SQL:
        # Check if rows are already dictionaries (Azure SQL with pymssql may return dict-like objects)
        if rows:
            first_row = rows[0]
            if isinstance(first_row, dict):
                # print(f"DEBUG search_returns - rows already dictionaries, no conversion needed")
                # Rows are already dictionaries, no conversion needed
                pass
            else:
                # print(f"DEBUG search_returns - converting tuples to dictionaries")
                # Convert tuple rows to dictionaries
                if columns:
                    rows = [dict(zip(columns, row)) for row in rows]
                else:
                    rows = []
            # print(f"DEBUG search_returns - first final row: {rows[0] if rows else 'none'}")
        else:
            rows = []
            # print(f"DEBUG search_returns - no rows to process")
    
    for row in rows:
        if USE_AZURE_SQL:
            # print(f"DEBUG search_returns - processing row: {row}")
            return_dict = {
                "id": row['id'],
                "status": row['status'] or '',
                "created_at": row['created_at'] if row['created_at'] else None,
                "tracking_number": row['tracking_number'],
                "processed": bool(row['processed']),
                "api_id": row['api_id'],
                "client_name": row['client_name'],
                "customer_name": row['customer_name'] or '',
                "warehouse_name": row['warehouse_name'],
                "is_shared": False
            }
            # print(f"DEBUG search_returns - created return_dict: {return_dict}")
        else:
            return_dict = {
                "id": row['id'],
                "status": row['status'] or '',
                "created_at": row['created_at'] if row['created_at'] else None,
                "tracking_number": row['tracking_number'],
                "processed": bool(row['processed']),
                "api_id": row['api_id'],
                "client_name": row['client_name'],
                "customer_name": row['customer_name'] or '',
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

            if USE_AZURE_SQL:
                # Capture columns before fetchall()
                columns = [column[0] for column in cursor.description] if cursor.description else []

            item_rows = cursor.fetchall()
            if USE_AZURE_SQL:
                # Azure SQL returns dictionaries already, no conversion needed
                pass
            
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
                return_data['order_number'] = get_single_value(order_row, 'order_number', 0)
                return_data['items_note'] = "Return items not available from API. Order reference shown."
    
    return_data['items'] = items
    
    conn.close()
    return return_data

@app.post("/api/returns/export/csv")
@app.get("/api/returns/export/csv")
async def export_returns_csv(filter_params: dict = None):
    """Export returns with product details to CSV"""
    try:
        print(f"DEBUG CSV: Starting export with filter_params: {filter_params}")

        # Handle None filter_params for GET requests
        if filter_params is None:
            filter_params = {}

        conn = get_db_connection()
        if not USE_AZURE_SQL:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print(f"DEBUG CSV: Database connection established, USE_AZURE_SQL: {USE_AZURE_SQL}")

        # First get all returns matching the filter
        query = """
        SELECT r.id as return_id, r.status, r.created_at as return_date, r.tracking_number,
               r.processed, c.name as client_name, w.name as warehouse_name,
               r.order_id, o.order_number, o.created_at as order_date, o.customer_name
        FROM returns r
        LEFT JOIN clients c ON CAST(r.client_id as BIGINT) = CAST(c.id as BIGINT)
        LEFT JOIN warehouses w ON CAST(r.warehouse_id as BIGINT) = CAST(w.id as BIGINT)
        LEFT JOIN orders o ON CAST(r.order_id as BIGINT) = CAST(o.id as BIGINT)
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

        cursor.execute(query, tuple(params))

        # Capture columns before fetchall() for Azure SQL
        if USE_AZURE_SQL:
            columns = [column[0] for column in cursor.description] if cursor.description else []

        returns = cursor.fetchall()

        # Handle Azure SQL row format - SMART CONVERSION
        if USE_AZURE_SQL:
            if returns:
                print(f"DEBUG CSV: Processing {len(returns)} returns from Azure SQL")
                # Check if first row is already a dictionary or tuple
                first_row = returns[0] if returns else None
                if isinstance(first_row, dict):
                    print("DEBUG CSV: Azure SQL returned dictionaries - using directly")
                    # Already dictionaries, use as-is
                    pass
                elif columns:
                    print("DEBUG CSV: Azure SQL returned tuples - converting to dictionaries")
                    # Convert tuples to dictionaries with explicit column mapping
                    converted_returns = []
                    for row in returns:
                        if isinstance(row, dict):
                            # Already a dictionary, use as-is
                            converted_returns.append(row)
                        else:
                            # Convert tuple to dictionary
                            row_dict = {}
                            for i, col_name in enumerate(columns):
                                if i < len(row):
                                    row_dict[col_name] = row[i]
                                else:
                                    row_dict[col_name] = None
                            converted_returns.append(row_dict)
                    returns = converted_returns
                    print(f"DEBUG CSV: Converted {len(returns)} returns from tuples to dictionaries")
                else:
                    print("DEBUG CSV: No columns available for conversion")
                    returns = []
            else:
                print("DEBUG CSV: No returns data to process")
                returns = []
    
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
        total_csv_rows = 0
        total_duplicates_skipped = 0
        total_suspicious_orders = 0
        total_returns_with_items = 0

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
                LEFT JOIN products p ON CAST(ri.product_id as BIGINT) = CAST(p.id as BIGINT)
                WHERE ri.return_id = %s
            """, (return_id,))
            items = cursor.fetchall()
            print(f"DEBUG CSV: Found {len(items) if items else 0} items for return {return_id}")

            # Convert items to dict for Azure SQL - SMART CONVERSION
            if USE_AZURE_SQL:
                raw_items_count = len(items) if items else 0
                if items:
                    # Check if first item is already a dictionary or tuple
                    first_item = items[0] if items else None
                    if isinstance(first_item, dict):
                        print(f"DEBUG CSV: Items already dictionaries for return {return_id}")
                        # Already dictionaries, use as-is
                        pass
                    else:
                        print(f"DEBUG CSV: Converting items tuples to dictionaries for return {return_id}")
                        # Use explicit column names from the query instead of relying on cursor.description
                        columns = ['id', 'sku', 'name', 'order_quantity', 'return_quantity', 'return_reasons', 'condition_on_arrival']
                        converted_items = []
                        for row in items:
                            if isinstance(row, dict):
                                # Already a dictionary, use as-is
                                converted_items.append(row)
                            else:
                                # Convert tuple to dictionary
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
                print(f"DEBUG CSV: Writing {len(items)} items for return {return_id}")

                # DUPLICATION CHECK - Track items we've seen for this return
                seen_items = set()
                duplicate_count = 0

                # Write return items from database
                for item_index, item in enumerate(items):
                    print(f"DEBUG CSV: Processing item {item_index + 1}/{len(items)} for return {return_id}: {item.get('name', 'Unknown')}")

                    # DUPLICATION DETECTION - Create unique identifier for this item
                    item_key = f"{item.get('id', '')}-{item.get('name', '')}-{item.get('sku', '')}"
                    if item_key in seen_items:
                        duplicate_count += 1
                        print(f"🚨 DUPLICATE ITEM DETECTED for return {return_id}: {item.get('name', 'Unknown')} (key: {item_key})")
                        print(f"   - This is duplicate #{duplicate_count} for this return")
                        continue  # Skip duplicates
                    seen_items.add(item_key)

                    reasons = ''
                    if item['return_reasons']:
                        try:
                            reasons_data = json.loads(item['return_reasons'])
                            reasons = ', '.join(reasons_data) if isinstance(reasons_data, list) else str(reasons_data)
                        except:
                            reasons = str(item['return_reasons'])

                    # DATA INTEGRITY CHECK - Validate order number
                    order_number = return_row.get('order_number', '')
                    if order_number and str(order_number).isdigit() and len(str(order_number)) > 10:
                        # This looks like an ID, not an order number - flag it
                        print(f"⚠️ SUSPICIOUS ORDER NUMBER for return {return_id}: {order_number} (looks like ID)")
                        order_number = f"ID-{order_number}"  # Mark as ID for visibility

                    # Additional validation - check if order_number looks like return_id or order_id
                    if str(order_number) == str(return_id):
                        print(f"⚠️ ORDER NUMBER IS RETURN ID for return {return_id}: {order_number}")
                        order_number = f"RETURN-{order_number}"
                    elif str(order_number) == str(order_id):
                        print(f"⚠️ ORDER NUMBER IS ORDER ID for return {return_id}: {order_number}")
                        order_number = f"ORDER-{order_number}"

                    csv_row = [
                        return_row['client_name'] or '',
                        customer_name,
                        return_row['order_date'] or '',
                        return_row['return_date'],
                        order_number or '',
                        item['name'] or '',
                        item['order_quantity'] or 0,  # Order Qty
                        item['return_quantity'] or 0,  # Return Qty
                        reasons
                    ]
                    print(f"DEBUG CSV: Writing row for return {return_id}, item: {item['name']}, order: {order_number}")
                    writer.writerow(csv_row)
                    total_csv_rows += 1

                # Report duplicates found
                if duplicate_count > 0:
                    print(f"⚠️ DUPLICATION SUMMARY for return {return_id}: {duplicate_count} duplicate items skipped")
                    total_duplicates_skipped += duplicate_count

                # Track returns with items for analysis
                total_returns_with_items += 1

                # Track suspicious order numbers
                if (order_number and
                    (str(order_number).isdigit() and len(str(order_number)) > 10) or
                    str(order_number) == str(return_id) or
                    str(order_number) == str(order_id)):
                    total_suspicious_orders += 1
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
                total_csv_rows += 1
    
        conn.close()

        # COMPREHENSIVE DATA INTEGRITY REPORT
        print(f"\n{'='*80}")
        print(f"📊 CSV EXPORT DATA INTEGRITY REPORT")
        print(f"{'='*80}")
        print(f"✅ Total CSV rows written: {total_csv_rows} (excluding header)")
        print(f"📦 Returns with items processed: {total_returns_with_items}")
        print(f"🔄 Total duplicate items skipped: {total_duplicates_skipped}")
        print(f"⚠️ Returns with suspicious order numbers: {total_suspicious_orders}")

        if total_duplicates_skipped > 0:
            print(f"🚨 WARNING: {total_duplicates_skipped} duplicate items were detected and skipped from CSV export")

        if total_suspicious_orders > 0:
            print(f"🚨 WARNING: {total_suspicious_orders} returns had suspicious order numbers (IDs instead of order numbers)")

        if total_duplicates_skipped == 0 and total_suspicious_orders == 0:
            print(f"✅ NO DATA INTEGRITY ISSUES DETECTED - CSV export appears clean")
        else:
            print(f"⚠️ DATA INTEGRITY ISSUES FOUND - Review logs above for details")

        print(f"{'='*80}\n")

        # Return CSV as downloadable file
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"returns_export_{timestamp}.csv"

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        print(f"DEBUG CSV ERROR: {str(e)}")
        print(f"DEBUG CSV ERROR TYPE: {type(e)}")
        import traceback
        print(f"DEBUG CSV TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")

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
    """Trigger a sync with Warehance API using enhanced sync system"""
    try:
        # Import database models
        from database.models import SessionLocal, SyncLog

        db = SessionLocal()
        running_sync = db.query(SyncLog).filter(SyncLog.status == "running").first()

        if running_sync:
            db.close()
            return {
                "message": f"Sync already in progress (ID: {running_sync.id})",
                "status": "running",
                "sync_id": running_sync.id
            }

        # Start enhanced sync
        sync_type = request_data.get("sync_type", "full")
        
        print(f"🚀 Starting enhanced sync with type: {sync_type}")

        def run_enhanced_sync():
            try:
                syncer = WarehanceAPISync()
                result = syncer.run_sync(sync_type)
                print(f"✅ Enhanced sync completed: {result}")
            except Exception as sync_error:
                print(f"❌ Enhanced sync failed: {sync_error}")
                import traceback
                traceback.print_exc()

        # Run sync in background
        asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, run_enhanced_sync))
        
        db.close()

        return {
            "message": f"Enhanced sync started with real-time progress tracking",
            "status": "started",
            "sync_type": sync_type
        }

    except Exception as e:
        print(f"❌ Enhanced sync setup failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "message": f"Error starting enhanced sync: {str(e)}",
            "status": "error"
        }

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
                exists = get_single_value(result, 'count', 0) > 0
                
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
                exists = get_single_value(result, 'count', 0) > 0
                
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
    """Get current sync status using enhanced database system"""
    try:
        from database.models import SessionLocal, SyncLog

        db = SessionLocal()
        latest_sync = db.query(SyncLog).order_by(SyncLog.started_at.desc()).first()
        history = db.query(SyncLog).filter(SyncLog.status.in_(["completed", "failed"])).order_by(SyncLog.started_at.desc()).limit(10).all()
        db.close()

        return {
            "current_sync": latest_sync.to_dict() if latest_sync else None,
            "history": [sync.to_dict() for sync in history],
            "deployment_version": DEPLOYMENT_VERSION,
            "enhanced_sync": True
        }

    except Exception as e:
        print(f"❌ Enhanced sync status failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "current_sync": {"status": "error", "items_synced": 0},
            "last_sync_status": "error",
            "last_sync_message": str(e),
            "deployment_version": DEPLOYMENT_VERSION,
            "enhanced_sync": False
        }

@app.get("/api/sync/progress")
async def get_sync_progress():
    """Get real-time sync progress using enhanced database system"""
    try:
        from database.models import SessionLocal, SyncLog
        from datetime import datetime

        db = SessionLocal()
        current_sync = db.query(SyncLog).filter(SyncLog.status == "running").order_by(SyncLog.started_at.desc()).first()

        if not current_sync:
            db.close()
            return {
                "is_running": False,
                "message": "No sync currently running"
            }

        # Calculate progress metrics
        progress_data = current_sync.to_dict()

        # Calculate ETA if we have enough data
        if current_sync.processed_count > 0 and current_sync.total_to_process > 0:
            elapsed_seconds = (datetime.utcnow() - current_sync.started_at).total_seconds()
            items_per_second = current_sync.processed_count / elapsed_seconds if elapsed_seconds > 0 else 0

            remaining_items = current_sync.total_to_process - current_sync.processed_count
            eta_seconds = remaining_items / items_per_second if items_per_second > 0 else 0

            # Format ETA
            if eta_seconds < 60:
                eta_text = f"{int(eta_seconds)}s"
            elif eta_seconds < 3600:
                eta_text = f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
            else:
                hours = int(eta_seconds/3600)
                minutes = int((eta_seconds%3600)/60)
                eta_text = f"{hours}h {minutes}m"

            progress_data.update({
                "is_running": True,
                "items_per_second": round(items_per_second, 2),
                "items_per_minute": round(items_per_second * 60, 1),
                "eta_seconds": int(eta_seconds),
                "eta_text": eta_text,
                "elapsed_seconds": int(elapsed_seconds)
            })
        else:
            progress_data.update({
                "is_running": True,
                "items_per_second": 0,
                "items_per_minute": 0,
                "eta_seconds": 0,
                "eta_text": "Calculating...",
                "elapsed_seconds": int((datetime.utcnow() - current_sync.started_at).total_seconds())
            })

        db.close()
        return progress_data

    except Exception as e:
        print(f"❌ Enhanced sync progress failed: {e}")
        import traceback
        traceback.print_exc()
        return {"is_running": False, "error": str(e)}

@app.get("/api/sync/history")
async def get_sync_history():
    """Get sync history from database logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get recent sync history from returns table last_synced_at timestamps
        cursor.execute("""
            SELECT
                MAX(last_synced_at) as sync_time,
                COUNT(*) as returns_count,
                COUNT(CASE WHEN last_synced_at > DATEADD(day, -1, GETDATE()) THEN 1 END) as recent_count
            FROM returns
            WHERE last_synced_at IS NOT NULL
            GROUP BY CAST(last_synced_at as DATE)
            ORDER BY sync_time DESC
        """ if USE_AZURE_SQL else """
            SELECT
                last_synced_at as sync_time,
                COUNT(*) as returns_count
            FROM returns
            WHERE last_synced_at IS NOT NULL
            GROUP BY DATE(last_synced_at)
            ORDER BY sync_time DESC
            LIMIT 10
        """)

        rows = cursor.fetchall()
        history = []

        if USE_AZURE_SQL and rows:
            columns = [column[0] for column in cursor.description]
            for row in rows:
                history.append(dict(zip(columns, row)))
        else:
            for row in rows:
                history.append({
                    'sync_time': row[0],
                    'returns_count': row[1]
                })

        conn.close()

        return {
            "history": history,
            "current_sync_id": sync_status.get("sync_id"),
            "is_running": sync_status["is_running"]
        }

    except Exception as e:
        print(f"Error getting sync history: {e}")
        return {"history": [], "error": str(e)}

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

# DISABLED: Old sync function replaced by enhanced sync system
async def run_sync():
    """DISABLED: This old sync function has been replaced by the enhanced sync system"""
    raise NotImplementedError("This old sync function has been disabled. Please use the enhanced sync system via /api/sync/trigger")

@app.post("/api/returns/send-email")
async def send_returns_email(request_data: dict):
    """Send returns report via email to client"""
    try:
        client_id = request_data.get('client_id')
        recipient_email = request_data.get('email')
        
        # TODO: Implement email sending functionality
        return {"status": "success", "message": "Email functionality not yet implemented"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    # Use Azure's PORT environment variable if available
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8015)))
    uvicorn.run(app, host="0.0.0.0", port=port)
