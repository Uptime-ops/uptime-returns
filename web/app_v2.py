"""
Enhanced FastAPI app with product details and CSV export
"""
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# VERSION IDENTIFIER - Update this when deploying
import datetime
DEPLOYMENT_VERSION = "V87.104-EMERGENCY-FIX-INDENTATION-ERROR-EMPTY-IF-BLOCKS"
DEPLOYMENT_TIME = datetime.datetime.now().isoformat()
# Trigger V87.10 deployment retry
print(f"STARTING APP_V2.PY VERSION: {DEPLOYMENT_VERSION}")
print(f"DEPLOYMENT TIME: {DEPLOYMENT_TIME}")
print("THIS IS THE NEW APP_V2.PY FILE")

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
    print("WARNING:  WARNING: WAREHANCE_API_KEY environment variable not set. Sync functionality will be disabled.")
    print("   Please configure WAREHANCE_API_KEY in Azure App Service Application Settings.")
    WAREHANCE_API_KEY = None

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_AZURE_SQL = bool(DATABASE_URL and ('database.windows.net' in DATABASE_URL or 'database.azure.com' in DATABASE_URL))

# 🚀 CURSOR PERFORMANCE FIX: HTTP connection pooling for API calls
# (Function definition moved after imports to avoid NameError)

# Debug database configuration
print("DATABASE CONFIGURATION")
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

def ensure_tuple_params(params):
    """Ensure parameters are tuples for Azure SQL pymssql compatibility"""
    if USE_AZURE_SQL and isinstance(params, list):
        return tuple(params)
    return params

def build_placeholders(count):
    """Build a string of parameter placeholders for SQL queries"""
    placeholder = get_param_placeholder()
    return ", ".join([placeholder] * count)

def execute_sql(cursor, sql, params=None):
    """Execute SQL with automatic parameter placeholder conversion"""
    if params is None:
        params = ()

    # If using SQLite and SQL contains %s, convert to ?
    if not USE_AZURE_SQL and '%s' in sql:
        sql = sql.replace('%s', '?')

    cursor.execute(sql, params)
    return cursor

if USE_AZURE_SQL:
    print(f"Using Azure SQL Database")

    # First, list all available ODBC drivers for diagnostics
    print("ODBC Driver Diagnostics")
    try:
        available_drivers = pyodbc.drivers()
        print(f"Available ODBC drivers: {available_drivers}")
        if not available_drivers:
            print("WARNING: No ODBC drivers detected! This may be a configuration issue.")
    except Exception as e:
        print(f"ERROR listing drivers: {e}")
    print("ODBC Driver Diagnostics Complete")

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
from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any, Dict
from pydantic import BaseModel
import json
import csv
import io
from datetime import datetime
import asyncio
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import smtplib

# 🚀 CURSOR PERFORMANCE FIX: HTTP connection pooling for API calls
def create_http_session():
    """Create a reusable HTTP session with connection pooling and retries"""
    session = requests.Session()
    retry_strategy = Retry(
        total=2,  # 🚀 SPEED: Reduced from 3 to 2 retries
        backoff_factor=0.1,  # 🚀 SPEED: Reduced from 0.3 to 0.1 for faster retries
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        pool_connections=20,  # 🚀 SPEED: Increased from 10 to 20
        pool_maxsize=50,  # 🚀 SPEED: Increased from 20 to 50
        max_retries=retry_strategy
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Global HTTP session for reuse
http_session = create_http_session()

def fetch_return_items_data(return_id, headers):
    """Fetch items data for a single return - optimized for concurrent execution"""
    try:
        individual_response = http_session.get(
            f"https://api.warehance.com/v1/returns/{return_id}",
            headers=headers,
            timeout=1.5  # 🚀 SPEED: Fast timeout for concurrent calls
        )
        if individual_response.status_code == 200:
            individual_data = individual_response.json()
            if individual_data.get("status") == "success":
                individual_return_data = individual_data.get("data", {})
                items_data = individual_return_data.get('items', [])
                return return_id, items_data, None
            else:
                return return_id, [], f"API returned non-success status"
        else:
            return return_id, [], f"API call failed with status {individual_response.status_code}"
    except Exception as e:
        return return_id, [], f"Error: {str(e)}"
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

class SearchFilters(BaseModel):
    client_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    status: Optional[str] = None
    search: Optional[str] = ""
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    page: Optional[int] = 1
    limit: Optional[int] = 20
    include_items: Optional[bool] = False

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

# Log buffer to capture sync activity for debugging
sync_log_buffer = []
MAX_LOG_ENTRIES = 200

def log_sync_activity(message):
    """DISABLED - Log sync activity function causing formatting corruption"""
    # EMERGENCY FIX: This function was causing log corruption with line breaks
    # and browser crashes due to concurrent logging issues
    pass

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

    # Try a completely different approach - manual dictionary building
    try:
        columns = [column[0] for column in cursor.description]

        result = []
        for row in rows:
            row_dict = {}
            for i, col_name in enumerate(columns):
                if i < len(row):
                    row_dict[col_name] = row[i]
                else:
                    row_dict[col_name] = None
            result.append(row_dict)

        return result

    except Exception as e:
        # Fallback - return rows as-is if they're already dictionaries
        if rows and isinstance(rows[0], dict):
            return rows
        return []

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
        # print("DASHBOARD STATS: Starting")
        conn = get_db_connection()
        if not conn:
            # Only log connection errors for dashboard stats
            return {"stats": {}, "error": "No database connection"}

        if not USE_AZURE_SQL:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get various statistics
        stats = {}

        # Test basic query with detailed error handling
        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns")
            row = cursor.fetchone()
            stats['total_returns'] = row['count'] if row else 0
        except Exception as count_error:
            print(f"ERROR: Dashboard COUNT query failed: {count_error}")
            stats['total_returns'] = 0
            stats['count_error'] = str(count_error)

        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 0")
            row = cursor.fetchone()
            stats['pending_returns'] = row['count'] if row else 0
        except Exception as pending_error:
            print(f"ERROR: Dashboard processed = 0 query failed: {pending_error}")
            stats['pending_returns'] = 0
            stats['pending_error'] = str(pending_error)

        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE processed = 1")
            row = cursor.fetchone()
            stats['processed_returns'] = row['count'] if row else 0
        except Exception as processed_error:
            print(f"ERROR: Dashboard processed = 1 query failed: {processed_error}")
            stats['processed_returns'] = 0
            stats['processed_error'] = str(processed_error)

        try:
            cursor.execute("SELECT COUNT(DISTINCT client_id) as count FROM returns WHERE client_id IS NOT NULL")
            row = cursor.fetchone()
            stats['total_clients'] = row['count'] if row else 0
        except Exception as client_error:
            print(f"ERROR: Dashboard client_id query failed: {client_error}")
            stats['total_clients'] = 0
            stats['client_error'] = str(client_error)

        try:
            cursor.execute("SELECT COUNT(DISTINCT warehouse_id) as count FROM returns WHERE warehouse_id IS NOT NULL")
            row = cursor.fetchone()
            stats['total_warehouses'] = row['count'] if row else 0
        except Exception as warehouse_error:
            print(f"ERROR: Dashboard warehouse_id query failed: {warehouse_error}")
            stats['total_warehouses'] = 0
            stats['warehouse_error'] = str(warehouse_error)

        # Get return counts by time period
        if USE_AZURE_SQL:
            # Azure SQL syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)")
            row = cursor.fetchone()
            stats['returns_today'] = row['count'] if row else 0

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -7, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_week'] = row['count'] if row else 0

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE created_at >= DATEADD(day, -30, GETDATE())")
            row = cursor.fetchone()
            stats['returns_this_month'] = row['count'] if row else 0
        else:
            # SQLite syntax
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) = DATE('now')")
            row = cursor.fetchone()
            stats['returns_today'] = row['count'] if row else 0

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-7 days')")
            row = cursor.fetchone()
            stats['returns_this_week'] = row['count'] if row else 0

            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE DATE(created_at) >= DATE('now', '-30 days')")
            row = cursor.fetchone()
            stats['returns_this_month'] = row['count'] if row else 0

        # Count of unshared returns
        try:
            cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id NOT IN (SELECT return_id FROM email_share_items)")
            row = cursor.fetchone()
            stats['unshared_returns'] = row['count'] if row else 0
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
        # print(f"ERROR: Dashboard Returning stats: {stats}")
        return {"stats": stats}

    except Exception as e:
        print(f"DASHBOARD STATS ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return {
            "stats": {"total_returns": 0, "processed_returns": 0, "pending_returns": 0},
            "error": f"Dashboard error: {str(e)}"
        }

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

@app.get("/api/returns")
async def get_returns(page: int = 1, limit: int = 20, client_id: Optional[int] = None, status: Optional[str] = None, search: Optional[str] = None):
    """Get returns with pagination and filtering for GET requests"""
    # Create a mock request object with query parameters
    filter_params = {
        'page': page,
        'limit': limit,
        'client_id': client_id,
        'status': status,
        'search': search
    }

    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query with filters
    query = """
    SELECT r.id, r.api_id, r.paid_by, r.status, r.created_at, r.updated_at,
           r.processed, r.processed_at, r.warehouse_note, r.customer_note,
           r.tracking_number, r.tracking_url, r.carrier, r.service,
           r.label_cost, r.label_pdf_url, r.rma_slip_url, r.label_voided,
           r.client_id, r.warehouse_id, r.order_id, r.return_integration_id,
           r.last_synced_at, c.name as client_name, w.name as warehouse_name,
           o.order_number, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    params = []
    if client_id:
        placeholder = get_param_placeholder()
        query += f" AND r.client_id = {placeholder}"
        params.append(client_id)

    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"

    if search:
        placeholder = get_param_placeholder()
        query += f" AND (r.tracking_number LIKE {placeholder} OR CAST(r.id AS NVARCHAR(50)) LIKE {placeholder} OR c.name LIKE {placeholder})"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    # Count total rows for pagination
    count_query = """
    SELECT COUNT(*) as total_count
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    # Add same filters to count query
    if client_id:
        placeholder = get_param_placeholder()
        count_query += f" AND r.client_id = {placeholder}"

    if status:
        if status == 'pending':
            count_query += " AND r.processed = 0"
        elif status == 'processed':
            count_query += " AND r.processed = 1"

    if search:
        placeholder = get_param_placeholder()
        count_query += f" AND (r.tracking_number LIKE {placeholder} OR CAST(r.id AS NVARCHAR(50)) LIKE {placeholder} OR c.name LIKE {placeholder})"

    cursor.execute(count_query, ensure_tuple_params(params))
    count_result = cursor.fetchone()
    if USE_AZURE_SQL:
        total_count = count_result['total_count'] if count_result else 0
    else:
        total_count = count_result[0] if count_result else 0

    # Get paginated results
    query += " ORDER BY r.created_at DESC"
    limit_clause = format_limit_clause(limit, (page - 1) * limit)
    query += f" {limit_clause}"

    cursor.execute(query, ensure_tuple_params(params))
    rows = cursor.fetchall()

    # Convert rows to dict for Azure SQL
    if USE_AZURE_SQL:
        rows = rows_to_dict(cursor, rows) if rows else []

    conn.close()

    total_pages = (total_count + limit - 1) // limit

    return {
        "returns": rows,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.post("/api/returns/search")
async def search_returns(request: Request):
    # Parse request body for filters, with fallback to defaults
    try:
        body = await request.json()
        filter_params = {
            'page': body.get('page', 1),
            'limit': body.get('limit', 20),
            'client_id': body.get('client_id'),
            'warehouse_id': body.get('warehouse_id'),
            'status': body.get('status'),
            'search': body.get('search', ''),
            'date_from': body.get('date_from'),
            'date_to': body.get('date_to'),
            'include_items': body.get('include_items', False)
        }
        print(f"DEBUG: Parsed filters: {filter_params}")
    except Exception as e:
        print(f"Error parsing request body: {e}")
        # Fallback to defaults if request parsing fails
        filter_params = {
            'page': 1,
            'limit': 20,
            'client_id': None,
            'warehouse_id': None,
            'status': None,
            'search': '',
            'date_from': None,
            'date_to': None,
            'include_items': False
        }

    try:
        conn = get_db_connection()
        if not USE_AZURE_SQL:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"Database connection error in search_returns: {e}")
        return {"error": "Database connection failed", "returns": [], "total_count": 0, "page": 1, "limit": 20, "total_pages": 1}

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
    SELECT r.id, r.api_id, r.paid_by, r.status, r.created_at, r.updated_at,
           r.processed, r.processed_at, r.warehouse_note, r.customer_note,
           r.tracking_number, r.tracking_url, r.carrier, r.service,
           r.label_cost, r.label_pdf_url, r.rma_slip_url, r.label_voided,
           r.client_id, r.warehouse_id, r.order_id, r.return_integration_id,
           r.last_synced_at,
           c.name as client_name, w.name as warehouse_name,
           o.order_number, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    params = []

    if client_id:
        placeholder = get_param_placeholder()
        query += f" AND r.client_id = {placeholder}"
        params.append(client_id)

    if status:
        placeholder = get_param_placeholder()
        query += f" AND r.status = {placeholder}"
        params.append(status)

    if search:
        placeholder = get_param_placeholder()
        query += f" AND (r.tracking_number LIKE {placeholder} OR c.name LIKE {placeholder} OR w.name LIKE {placeholder})"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    # Add date filtering
    date_from = filter_params.get('date_from')
    date_to = filter_params.get('date_to')

    if date_from:
        placeholder = get_param_placeholder()
        query += f" AND r.created_at >= {placeholder}"
        params.append(date_from)

    if date_to:
        placeholder = get_param_placeholder()
        query += f" AND r.created_at <= {placeholder}"
        params.append(date_to + ' 23:59:59')  # Include full day

    # Add pagination
    if USE_AZURE_SQL:
        placeholder = get_param_placeholder()
        query += f" ORDER BY r.created_at DESC OFFSET {placeholder} ROWS FETCH NEXT {placeholder} ROWS ONLY"
        params.extend([(page - 1) * limit, limit])
    else:
        placeholder = get_param_placeholder()
        query += f" ORDER BY r.created_at DESC LIMIT {placeholder} OFFSET {placeholder}"
        params.extend([limit, (page - 1) * limit])

    try:
        cursor.execute(query, ensure_tuple_params(params))
        rows = cursor.fetchall()

        returns = []
        if USE_AZURE_SQL:
            print(f"DEBUG: Raw rows type: {type(rows)}")
            print(f"DEBUG: Raw first row: {rows[0] if rows else 'No rows'}")
            print(f"DEBUG: Raw first row type: {type(rows[0]) if rows else 'No rows'}")

            # Try to see if rows are already dictionaries
            if rows and hasattr(rows[0], 'keys'):
                print(f"DEBUG: First row has keys: {list(rows[0].keys())}")
                rows = rows  # Already dictionaries, don't convert
            else:
                print(f"DEBUG: Converting rows with rows_to_dict")
                rows = rows_to_dict(cursor, rows) if rows else []

            # Debug: print first row to see what we're getting
            if rows:
                print(f"DEBUG: Final first row: {rows[0]}")
                print(f"DEBUG: Final first row type: {type(rows[0])}")
    except Exception as e:
        print(f"Query execution error in search_returns: {e}")
        conn.close()
        return {"error": "Query execution failed", "returns": [], "total_count": 0, "page": page, "limit": limit, "total_pages": 1}

    for row in rows:
        if USE_AZURE_SQL:
            return_dict = {
                "id": row['id'],
                "api_id": row['api_id'],
                "paid_by": row['paid_by'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "updated_at": row['updated_at'],
                "processed": bool(row['processed']),
                "processed_at": row['processed_at'],
                "warehouse_note": row['warehouse_note'],
                "customer_note": row['customer_note'],
                "tracking_number": row['tracking_number'],
                "tracking_url": row['tracking_url'],
                "carrier": row['carrier'],
                "service": row['service'],
                "label_cost": float(row['label_cost']) if row['label_cost'] and str(row['label_cost']) != 'label_cost' else None,
                "label_pdf_url": row['label_pdf_url'],
                "rma_slip_url": row['rma_slip_url'],
                "label_voided": bool(row['label_voided']),
                "client_id": row['client_id'],
                "warehouse_id": row['warehouse_id'],
                "order_id": row['order_id'],
                "return_integration_id": row['return_integration_id'],
                "last_synced_at": row['last_synced_at'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "order_number": row['order_number'],
                "customer_name": row['customer_name'],
                "is_shared": False
            }
        else:
            return_dict = {
                "id": row['id'],
                "api_id": row['api_id'],
                "paid_by": row['paid_by'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "updated_at": row['updated_at'],
                "processed": bool(row['processed']),
                "processed_at": row['processed_at'],
                "warehouse_note": row['warehouse_note'],
                "customer_note": row['customer_note'],
                "tracking_number": row['tracking_number'],
                "tracking_url": row['tracking_url'],
                "carrier": row['carrier'],
                "service": row['service'],
                "label_cost": float(row['label_cost']) if row['label_cost'] and str(row['label_cost']) != 'label_cost' else None,
                "label_pdf_url": row['label_pdf_url'],
                "rma_slip_url": row['rma_slip_url'],
                "label_voided": bool(row['label_voided']),
                "client_id": row['client_id'],
                "warehouse_id": row['warehouse_id'],
                "order_id": row['order_id'],
                "return_integration_id": row['return_integration_id'],
                "last_synced_at": row['last_synced_at'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "order_number": row['order_number'],
                "customer_name": row['customer_name'],
                "is_shared": False
            }

        returns.append(return_dict)

    # Get total count for pagination
    count_query = """
    SELECT COUNT(*) as total_count
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    count_params = []
    if client_id:
        placeholder = get_param_placeholder()
        count_query += f" AND r.client_id = {placeholder}"
        count_params.append(client_id)
    if status:
        placeholder = get_param_placeholder()
        count_query += f" AND r.status = {placeholder}"
        count_params.append(status)
    if search:
        placeholder = get_param_placeholder()
        count_query += f" AND (r.tracking_number LIKE {placeholder} OR c.name LIKE {placeholder} OR w.name LIKE {placeholder})"
        search_param = f"%{search}%"
        count_params.extend([search_param, search_param, search_param])

    if date_from:
        placeholder = get_param_placeholder()
        count_query += f" AND r.created_at >= {placeholder}"
        count_params.append(date_from)

    if date_to:
        placeholder = get_param_placeholder()
        count_query += f" AND r.created_at <= {placeholder}"
        count_params.append(date_to + ' 23:59:59')

    cursor.execute(count_query, ensure_tuple_params(count_params))
    count_result = cursor.fetchone()

    if USE_AZURE_SQL:
        if hasattr(count_result, 'keys'):
            total_count = count_result['total_count']
        else:
            count_dict = row_to_dict(cursor, count_result)
            total_count = count_dict['total_count'] if count_dict else 0
    else:
        total_count = count_result['total_count'] if count_result else 0

    total_pages = (total_count + limit - 1) // limit

    conn.close()

    return {
        "returns": returns,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.get("/api/returns/search-test")
async def search_returns_test():
    # For now, just return basic data without filters to test if the endpoint works
    filter_params = {
        'page': 1,
        'limit': 20,
        'client_id': None,
        'warehouse_id': None,
        'status': None,
        'search': '',
        'date_from': None,
        'date_to': None,
        'include_items': False
    }

    try:
        conn = get_db_connection()
        if not USE_AZURE_SQL:
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"Database connection error in search_returns: {e}")
        return {"error": "Database connection failed", "returns": [], "total_count": 0, "page": 1, "limit": 20, "total_pages": 1}

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
    SELECT r.id, r.api_id, r.paid_by, r.status, r.created_at, r.updated_at,
           r.processed, r.processed_at, r.warehouse_note, r.customer_note,
           r.tracking_number, r.tracking_url, r.carrier, r.service,
           r.label_cost, r.label_pdf_url, r.rma_slip_url, r.label_voided,
           r.client_id, r.warehouse_id, r.order_id, r.return_integration_id,
           r.last_synced_at,
           c.name as client_name, w.name as warehouse_name,
           o.order_number, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    params = []

    if client_id:
        placeholder = get_param_placeholder()
        query += f" AND r.client_id = {placeholder}"
        params.append(client_id)

    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"

    if search:
        placeholder = get_param_placeholder()
        query += f" AND (r.tracking_number LIKE {placeholder} OR CAST(r.id AS NVARCHAR(50)) LIKE {placeholder} OR c.name LIKE {placeholder})"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    # Get total count for pagination (use separate params for count query)
    count_params = []
    count_query = """
    SELECT COUNT(*) as total_count FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    if client_id:
        placeholder = get_param_placeholder()
        count_query += f" AND r.client_id = {placeholder}"
        count_params.append(client_id)

    if status:
        if status == 'pending':
            count_query += " AND r.processed = 0"
        elif status == 'processed':
            count_query += " AND r.processed = 1"

    if search:
        placeholder = get_param_placeholder()
        count_query += f" AND (r.tracking_number LIKE {placeholder} OR CAST(r.id AS NVARCHAR(50)) LIKE {placeholder} OR c.name LIKE {placeholder})"
        search_param = f"%{search}%"
        count_params.extend([search_param, search_param, search_param])

    cursor.execute(count_query, ensure_tuple_params(count_params))
    row = cursor.fetchone()
    if USE_AZURE_SQL:
        total = row['total_count'] if row else 0
    else:
        total = row[0] if row else 0

    # Add pagination (different syntax for Azure SQL vs SQLite)
    if USE_AZURE_SQL:
        placeholder = get_param_placeholder()
        query += f" ORDER BY r.created_at DESC OFFSET {placeholder} ROWS FETCH NEXT {placeholder} ROWS ONLY"
        params.extend([(page - 1) * limit, limit])
    else:
        placeholder = get_param_placeholder()
        query += f" ORDER BY r.created_at DESC LIMIT {placeholder} OFFSET {placeholder}"
        params.extend([limit, (page - 1) * limit])

    try:
        cursor.execute(query, ensure_tuple_params(params))
        rows = cursor.fetchall()

        returns = []
        if USE_AZURE_SQL:
            print(f"DEBUG: Raw rows type: {type(rows)}")
            print(f"DEBUG: Raw first row: {rows[0] if rows else 'No rows'}")
            print(f"DEBUG: Raw first row type: {type(rows[0]) if rows else 'No rows'}")

            # Try to see if rows are already dictionaries
            if rows and hasattr(rows[0], 'keys'):
                print(f"DEBUG: First row has keys: {list(rows[0].keys())}")
                rows = rows  # Already dictionaries, don't convert
            else:
                print(f"DEBUG: Converting rows with rows_to_dict")
                rows = rows_to_dict(cursor, rows) if rows else []

            # Debug: print first row to see what we're getting
            if rows:
                print(f"DEBUG: Final first row: {rows[0]}")
                print(f"DEBUG: Final first row type: {type(rows[0])}")
    except Exception as e:
        print(f"Query execution error in search_returns: {e}")
        conn.close()
        return {"error": "Query execution failed", "returns": [], "total_count": 0, "page": page, "limit": limit, "total_pages": 1}

    for row in rows:
        if USE_AZURE_SQL:
            return_dict = {
                "id": row['id'],
                "api_id": row['api_id'],
                "paid_by": row['paid_by'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "updated_at": row['updated_at'],
                "processed": bool(row['processed']),
                "processed_at": row['processed_at'],
                "warehouse_note": row['warehouse_note'],
                "customer_note": row['customer_note'],
                "tracking_number": row['tracking_number'],
                "tracking_url": row['tracking_url'],
                "carrier": row['carrier'],
                "service": row['service'],
                "label_cost": float(row['label_cost']) if row['label_cost'] and str(row['label_cost']) != 'label_cost' else None,
                "label_pdf_url": row['label_pdf_url'],
                "rma_slip_url": row['rma_slip_url'],
                "label_voided": bool(row['label_voided']),
                "client_id": row['client_id'],
                "warehouse_id": row['warehouse_id'],
                "order_id": row['order_id'],
                "return_integration_id": row['return_integration_id'],
                "last_synced_at": row['last_synced_at'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "order_number": row['order_number'],
                "customer_name": row['customer_name'],
                "is_shared": False
            }
        else:
            return_dict = {
                "id": row['id'],
                "api_id": row['api_id'],
                "paid_by": row['paid_by'],
                "status": row['status'] or '',
                "created_at": row['created_at'],
                "updated_at": row['updated_at'],
                "processed": bool(row['processed']),
                "processed_at": row['processed_at'],
                "warehouse_note": row['warehouse_note'],
                "customer_note": row['customer_note'],
                "tracking_number": row['tracking_number'],
                "tracking_url": row['tracking_url'],
                "carrier": row['carrier'],
                "service": row['service'],
                "label_cost": float(row['label_cost']) if row['label_cost'] and str(row['label_cost']) != 'label_cost' else None,
                "label_pdf_url": row['label_pdf_url'],
                "rma_slip_url": row['rma_slip_url'],
                "label_voided": bool(row['label_voided']),
                "client_id": row['client_id'],
                "warehouse_id": row['warehouse_id'],
                "order_id": row['order_id'],
                "return_integration_id": row['return_integration_id'],
                "last_synced_at": row['last_synced_at'],
                "client_name": row['client_name'],
                "warehouse_name": row['warehouse_name'],
                "order_number": row['order_number'],
                "customer_name": row['customer_name'],
                "is_shared": False
            }

        # Include items if requested
        if include_items:
            try:
                return_id = row['id'] if USE_AZURE_SQL else row['id']
                placeholder = get_param_placeholder()
                cursor.execute(f"""
                    SELECT ri.id, ri.return_id, ri.product_id, ri.quantity,
                           ri.return_reasons, ri.condition_on_arrival,
                           ri.quantity_received, ri.quantity_rejected,
                           ri.created_at, ri.updated_at,
                           p.sku, p.name as product_name
                    FROM return_items ri
                    LEFT JOIN products p ON ri.product_id = p.id
                    WHERE CAST(ri.return_id AS NVARCHAR(50)) = {placeholder}
                """, (return_id,))
            except Exception as e:
                print(f"Error fetching return items for return_id {return_id}: {e}")
                return_dict['items'] = []
                continue

            item_rows = cursor.fetchall()
            if USE_AZURE_SQL:
                item_rows = rows_to_dict(cursor, item_rows) if item_rows else []

            items = []
            for item_row in item_rows:
                items.append({
                    "id": item_row['id'],
                    "return_id": item_row['return_id'],
                    "product_id": item_row['product_id'],
                    "quantity": item_row['quantity'],
                    "return_reasons": json.loads(item_row['return_reasons']) if item_row['return_reasons'] else [],
                    "condition_on_arrival": json.loads(item_row['condition_on_arrival']) if item_row['condition_on_arrival'] else [],
                    "quantity_received": item_row['quantity_received'],
                    "quantity_rejected": item_row['quantity_rejected'],
                    "created_at": item_row['created_at'],
                    "updated_at": item_row['updated_at'],
                    "product": {
                        "id": item_row['product_id'],
                        "sku": item_row['sku'],
                        "name": item_row['product_name']
                    } if item_row['product_id'] else None
                })
            return_dict['items'] = items

        returns.append(return_dict)

    if 'conn' in locals():
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
async def get_return_detail(return_id: str):
    """Get detailed information for a specific return including order items if available"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get return details with all fields
    placeholder = get_param_placeholder()
    cursor.execute(f"""
        SELECT CAST(r.id AS NVARCHAR(50)) as id, r.api_id, r.paid_by, r.created_at, r.updated_at,
               r.status, r.tracking_number, r.processed, r.label_pdf_url, r.rma_slip_url,
               r.label_voided, CAST(r.client_id AS NVARCHAR(50)) as client_id,
               CAST(r.warehouse_id AS NVARCHAR(50)) as warehouse_id,
               CAST(r.order_id AS NVARCHAR(50)) as order_id, r.return_integration_id,
               r.last_synced_at, c.name as client_name, w.name as warehouse_name, o.order_number
        FROM returns r
        LEFT JOIN clients c ON CAST(r.client_id AS NVARCHAR(50)) = CAST(c.id AS NVARCHAR(50))
        LEFT JOIN warehouses w ON CAST(r.warehouse_id AS NVARCHAR(50)) = CAST(w.id AS NVARCHAR(50))
        LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
        WHERE CAST(r.id AS NVARCHAR(50)) = {placeholder}
    """, (return_id,))

    return_row = cursor.fetchone()
    if not return_row:
        return {"error": "Return not found"}

    return_data = dict(return_row)
    order_id = return_data.get('order_id')

    items = []

    # First check if there are actual return items (there shouldn't be any from API)
    placeholder = get_param_placeholder()
    cursor.execute(f"""
        SELECT ri.id, ri.return_id, ri.product_id, ri.quantity,
               ri.return_reasons, ri.condition_on_arrival,
               ri.quantity_received, ri.quantity_rejected,
               ri.created_at, ri.updated_at,
               p.sku, p.name as product_name
        FROM return_items ri
        LEFT JOIN products p ON ri.product_id = p.id
        WHERE CAST(ri.return_id AS NVARCHAR(50)) = {placeholder}
    """, (return_id,))

    return_items = cursor.fetchall()

    if return_items:
        # If we have return items, use them
        for item_row in return_items:
            items.append({
                "id": item_row['id'],
                "return_id": item_row['return_id'],
                "product_id": item_row['product_id'],
                "quantity": item_row['quantity'],
                "return_reasons": json.loads(item_row['return_reasons']) if item_row['return_reasons'] else [],
                "condition_on_arrival": json.loads(item_row['condition_on_arrival']) if item_row['condition_on_arrival'] else [],
                "quantity_received": item_row['quantity_received'],
                "quantity_rejected": item_row['quantity_rejected'],
                "created_at": item_row['created_at'],
                "updated_at": item_row['updated_at'],
                "product": {
                    "id": item_row['product_id'],
                    "sku": item_row['sku'],
                    "name": item_row['product_name']
                } if item_row['product_id'] else None
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
                timeout=3  # 🚀 PERFORMANCE: Reduced from 10s to 3s for speed
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
async def export_returns_csv(request: Request):
    """Export returns with product details to CSV"""
    # print("CSV EXPORT: Starting export process")
    # Parse the request body as JSON
    try:
        filter_params = await request.json()
        # print(f"CSV EXPORT: Filter params: {filter_params}")
    except Exception as e:
        print(f"JSON parsing error in export_returns_csv: {e}")
        filter_params = {}

    # print("CSV EXPORT: Getting database connection")
    conn = get_db_connection()
    # print("CSV EXPORT: Database connection successful")
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # First get all returns matching the filter
    query = """
    SELECT CAST(r.id AS NVARCHAR(50)) as return_id, r.status, r.created_at as return_date, r.tracking_number,
           r.processed, c.name as client_name, w.name as warehouse_name,
           CAST(r.order_id AS NVARCHAR(50)) as order_id, o.order_number, o.created_at as order_date, o.customer_name
    FROM returns r
    LEFT JOIN clients c ON r.client_id = c.id
    LEFT JOIN warehouses w ON r.warehouse_id = w.id
    LEFT JOIN orders o ON CAST(r.order_id AS NVARCHAR(50)) = CAST(o.id AS NVARCHAR(50))
    WHERE 1=1
    """

    params = []
    client_id = filter_params.get('client_id')
    status = filter_params.get('status')
    search = filter_params.get('search') or ''
    search = search.strip() if search else ''

    if client_id:
        placeholder = get_param_placeholder()
        query += f" AND r.client_id = {placeholder}"
        params.append(client_id)

    if status:
        if status == 'pending':
            query += " AND r.processed = 0"
        elif status == 'processed':
            query += " AND r.processed = 1"

    if search:
        placeholder = get_param_placeholder()
        query += f" AND (r.tracking_number LIKE {placeholder} OR CAST(r.id AS NVARCHAR(50)) LIKE {placeholder} OR c.name LIKE {placeholder})"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    query += " ORDER BY r.created_at DESC"

    cursor.execute(query, ensure_tuple_params(params))
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
        placeholder = get_param_placeholder()
        try:
            # Use string-based comparison to avoid INT overflow completely
            # Just query directly with string return_id (no conversion needed)
            cursor.execute(f"""
                SELECT ri.id, COALESCE(p.sku, 'N/A') as sku,
                       COALESCE(p.name, 'Unknown Product') as name,
                       ri.quantity as order_quantity,
                       ri.quantity_received as return_quantity,
                       ri.return_reasons, ri.condition_on_arrival
                FROM return_items ri
                LEFT JOIN products p ON CAST(ri.product_id AS NVARCHAR(50)) = CAST(p.id AS NVARCHAR(50))
                WHERE CAST(ri.return_id AS NVARCHAR(50)) = {placeholder}
            """, (str(return_id),))
            items = cursor.fetchall()
            # print(f"CSV EXPORT: Successfully queried return_items for return {return_id}, found {len(items)} items")
        except Exception as query_error:
            print(f"CSV EXPORT ERROR: Query failed for return {return_id}: {query_error}")
            items = []  # Continue with empty items instead of crashing

        # Convert items to dict for Azure SQL
        if USE_AZURE_SQL:
            items = rows_to_dict(cursor, items) if items else []

        if items:
            # Write return items from database
            for item in items:
                reasons = ''
                if item.get('return_reasons'):
                    try:
                        reasons_data = json.loads(item['return_reasons'])
                        reasons = ', '.join(reasons_data) if isinstance(reasons_data, list) else str(reasons_data)
                    except:
                        reasons = str(item.get('return_reasons', ''))

                writer.writerow([
                    return_row['client_name'] or '',
                    customer_name,
                    return_row['order_date'] or '',
                    return_row['return_date'],
                    return_row['order_number'] or '',
                    item.get('name', '') or '',
                    item.get('order_quantity', 0) or 0,  # Original order quantity
                    item.get('return_quantity', 0) or 0,  # Actual return quantity received
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






@app.post("/api/sync/trigger")
async def trigger_sync():
    """Trigger a sync with Warehance API"""
    global sync_status

    print(f"SYNC TRIGGER: is_running={sync_status['is_running']}")

    # Check if API key is configured
    if not WAREHANCE_API_KEY:
        return {"message": "WAREHANCE_API_KEY not configured. Please set it in Azure App Service Application Settings.", "status": "error"}

    if sync_status["is_running"]:
        return {"message": "Sync already in progress", "status": "running"}

    # Initialize sync status immediately to prevent race conditions
    sync_status["is_running"] = True
    sync_status["items_synced"] = 0
    sync_status["products_synced"] = 0
    sync_status["return_items_synced"] = 0
    sync_status["orders_synced"] = 0
    sync_status["last_sync_status"] = "running"
    sync_status["last_sync_message"] = "Starting sync..."
    print(f"SYNC TRIGGER: Set is_running=True immediately")

    # Start sync in background
    print("SYNC TRIGGER: Starting background sync task")
    try:
        task = asyncio.create_task(run_sync())
        print(f"SYNC TRIGGER: Task created successfully")
    except Exception as e:
        print(f"SYNC TRIGGER ERROR: Failed to create task: {e}")
        sync_status["is_running"] = False
        sync_status["last_sync_status"] = "error"
        sync_status["last_sync_message"] = f"Failed to start sync: {str(e)}"
        return {"message": f"Failed to start sync: {str(e)}", "status": "error"}

    return {"message": "Sync started", "status": "started"}


@app.post("/api/sync/stop")
async def stop_sync():
    """Force stop any running sync process"""
    global sync_status

    was_running = sync_status["is_running"]
    sync_status["is_running"] = False
    sync_status["last_sync_status"] = "stopped"
    sync_status["last_sync_message"] = "Sync stopped by user request"

    return {
        "message": f"Sync {'stopped' if was_running else 'was not running'}",
        "status": "stopped",
        "was_running": was_running
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
                exists = (result['count'] > 0 if USE_AZURE_SQL else result[0] > 0)

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

        # First, check if orders table exists and add missing columns if needed
        try:
            cursor.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'orders' AND COLUMN_NAME = 'customer_name'
            """)
            customer_name_exists = cursor.fetchone()

            if not customer_name_exists:
                print("Adding missing customer_name column to orders table...")
                cursor.execute("ALTER TABLE orders ADD customer_name NVARCHAR(255)")
                conn.commit()
                print("SUCCESS: Added customer_name column to orders table")
            else:
                print("SUCCESS: customer_name column already exists in orders table")
        except Exception as alter_err:
            print(f"Error checking/adding customer_name column: {alter_err}")

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
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
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
                    product_id BIGINT,
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
            'email_shares': """
                CREATE TABLE email_shares (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    client_id BIGINT NOT NULL,
                    share_date DATETIME DEFAULT GETDATE(),
                    date_range_start DATE NOT NULL,
                    date_range_end DATE NOT NULL,
                    recipient_email NVARCHAR(255),
                    subject NVARCHAR(500),
                    total_returns_shared INT DEFAULT 0,
                    share_status NVARCHAR(50) DEFAULT 'pending',
                    sent_at DATETIME,
                    notes NVARCHAR(MAX),
                    created_at DATETIME DEFAULT GETDATE(),
                    created_by NVARCHAR(100),
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                )
            """,
            'email_share_items': """
                CREATE TABLE email_share_items (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    email_share_id INT NOT NULL,
                    return_id BIGINT NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    FOREIGN KEY (email_share_id) REFERENCES email_shares(id) ON DELETE CASCADE,
                    FOREIGN KEY (return_id) REFERENCES returns(id),
                    UNIQUE(email_share_id, return_id)
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
                exists = (result['count'] > 0 if USE_AZURE_SQL else result[0] > 0)

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
        # Simplified sync status - no database query to avoid timeouts
        # Just return the in-memory sync status

        current_sync_status = "running" if sync_status["is_running"] else "completed"
        # print(f"=== SYNC STATUS API: Returning status='{current_sync_status}', is_running={sync_status['is_running']} ===")

        return {
            "current_sync": {
                "status": current_sync_status,
                "items_synced": sync_status["items_synced"],
                "products_synced": sync_status.get("products_synced", 0),
                "return_items_synced": sync_status.get("return_items_synced", 0),
                "orders_synced": sync_status.get("orders_synced", 0)
            },
            "last_sync": sync_status["last_sync"],
            "last_sync_status": sync_status["last_sync_status"],
            "last_sync_message": sync_status["last_sync_message"],
            "deployment_version": DEPLOYMENT_VERSION,
            "sql_fix_applied": "YES - MERGE statements + parameterized queries",
            "identity_insert_fixed": "YES - Removed IDENTITY_INSERT, using MERGE"
        }
    except Exception as e:
        print(f"Error in sync status: {str(e)}")
        return {
            "current_sync": {
                "status": "error",
                "items_synced": 0,
                "products_synced": 0,
                "return_items_synced": 0,
                "orders_synced": 0
            },
            "last_sync": None,
            "last_sync_status": "error",
            "last_sync_message": str(e),
            "deployment_version": DEPLOYMENT_VERSION,
            "sql_fix_applied": "YES - MERGE statements + parameterized queries",
            "identity_insert_fixed": "YES - Removed IDENTITY_INSERT, using MERGE"
        }

@app.post("/api/sync/target-returns-with-data")
async def sync_returns_with_product_data():
    """Target and process returns that have real product data in items array"""
    global sync_status

    if sync_status["is_running"]:
        return {"message": "Sync already in progress", "status": "running"}

    try:
        sync_status["is_running"] = True
        sync_status["last_sync_status"] = "running"
        sync_status["last_sync_message"] = "Targeting returns with product data..."

        # Get API key
        api_key = WAREHANCE_API_KEY
        headers = {"X-API-KEY": api_key, "accept": "application/json"}

        conn = get_db_connection()
        cursor = conn.cursor()

        # CRITICAL: Ensure return_items table exists with correct schema
        try:
            if USE_AZURE_SQL:
                create_return_items_sql = """
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='return_items' AND xtype='U')
                CREATE TABLE return_items (
                    id BIGINT PRIMARY KEY,
                    return_id BIGINT NOT NULL,
                    product_id BIGINT,
                    quantity INT DEFAULT 1,
                    reason NVARCHAR(500),
                    created_at DATETIME DEFAULT GETDATE()
                )
                """
                cursor.execute(create_return_items_sql)
                print("Ensured return_items table exists in Azure SQL")
            else:
                create_return_items_sql = """
                CREATE TABLE IF NOT EXISTS return_items (
                    id INTEGER PRIMARY KEY,
                    return_id INTEGER NOT NULL,
                    product_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
                cursor.execute(create_return_items_sql)
                print("Ensured return_items table exists in SQLite")
        except Exception as e:
            print(f"Table creation check failed: {e}")

        # Also ensure products table exists
        try:
            if USE_AZURE_SQL:
                create_products_sql = """
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='products' AND xtype='U')
                CREATE TABLE products (
                    id BIGINT PRIMARY KEY,
                    sku NVARCHAR(200),
                    name NVARCHAR(500),
                    created_at DATETIME DEFAULT GETDATE()
                )
                """
                cursor.execute(create_products_sql)
                print("Ensured products table exists in Azure SQL")
            else:
                create_products_sql = """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    sku TEXT,
                    name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
                cursor.execute(create_products_sql)
                print("Ensured products table exists in SQLite")
        except Exception as e:
            print(f"Products table creation check failed: {e}")

        processed_count = 0
        returns_with_data = 0
        return_items_created = 0

        # First, get a batch of returns to check for product data
        print("Fetching returns to check for product data...")

        # Get first 20 returns to analyze
        response = requests.get(
            "https://api.warehance.com/v1/returns?limit=20&offset=0",
            headers=headers,
            timeout=10  # 🚀 PERFORMANCE: Reduced from 30s to 10s for debug endpoint
        )

        if response.status_code != 200:
            sync_status["last_sync_status"] = "error"
            sync_status["last_sync_message"] = f"API call failed: {response.status_code}"
            return {"error": f"API call failed: {response.status_code}"}

        data = response.json()
        returns_data = data.get('data', {}).get('returns', [])

        print(f"Analyzing {len(returns_data)} returns for product data...")

        # Check each return for real product data
        for return_item in returns_data:
            processed_count += 1
            return_id = return_item.get('id')
            items = return_item.get('items', [])

            # Skip if no items array or empty
            if not items or items is None:
                pass  # DISABLED - print(f"Return {return_id}: No items array")
                continue

            # Check if any item has real product data
            has_real_data = False
            for item in items:
                if item.get('product', {}).get('sku') and item.get('product', {}).get('name'):
                    has_real_data = True
                    break

            if not has_real_data:
                pass  # DISABLED - print(f"Return {return_id}: Items array exists but no product data")
                continue

            pass  # DISABLED - print(f"Return {return_id}: HAS REAL PRODUCT DATA! Processing {len(items)} items...")
            returns_with_data += 1

            # Process return items with real data
            for item in items:
                product_info = item.get('product', {})
                if product_info.get('sku') and product_info.get('name'):
                    item_id = item.get('id')
                    product_id = product_info.get('id')
                    sku = product_info.get('sku')
                    name = product_info.get('name')
                    quantity = item.get('quantity', 1)

                    print(f"  Item {item_id}: {sku} - {name} (qty: {quantity})")

                    # First ensure product exists in products table
                    placeholder = get_param_placeholder()

                    # Use simple INSERT with IDENTITY_INSERT for Azure SQL
                    try:
                        if USE_AZURE_SQL:
                            # 🚨 FIXED: Use MERGE instead of IDENTITY_INSERT for Azure SQL
                            merge_sql = f"""
                                MERGE products AS target
                                USING (VALUES ({placeholder}, {placeholder})) AS source (sku, name)
                                ON target.sku = source.sku
                                WHEN NOT MATCHED THEN
                                    INSERT (sku, name, created_at, updated_at)
                                    VALUES (source.sku, source.name, GETDATE(), GETDATE());
                            """
                            cursor.execute(merge_sql, (sku, name))
                        else:
                            # SQLite - can use explicit IDs
                            product_insert_sql = f"INSERT OR IGNORE INTO products (id, sku, name) VALUES ({placeholder}, {placeholder}, {placeholder})"
                        cursor.execute(product_insert_sql, (product_id, sku, name))

                        print(f"    Product {product_id} inserted successfully")
                    except Exception as e:
                        print(f"    Product {product_id} insert failed: {e}")
                        # Continue anyway - product might already exist

                    # Now insert return_item with full structure to match CSV export expectations
                    try:
                        if USE_AZURE_SQL:
                            cursor.execute(f"""
                                INSERT INTO return_items (return_id, product_id, quantity, return_reasons,
                                       condition_on_arrival, quantity_received, quantity_rejected, created_at, updated_at)
                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                                       {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, ensure_tuple_params((
                                str(return_id),  # Convert to string for NVARCHAR field
                                product_id,
                                quantity,
                                '["Original order item"]',  # Default return reason
                                '["Unknown"]',  # Default condition
                                quantity,  # Assume all received
                                0,  # None rejected initially
                                convert_date_for_sql(datetime.now().isoformat()),  # created_at
                                convert_date_for_sql(datetime.now().isoformat())   # updated_at
                            )))
                        else:
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO return_items (
                                    return_id, product_id, quantity,
                                    return_reasons, condition_on_arrival,
                                    quantity_received, quantity_rejected,
                                    created_at, updated_at
                                ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, ensure_tuple_params((
                                return_id,
                                product_id,
                                quantity,
                                '["Original order item"]',  # Default return reason
                                '["Unknown"]',  # Default condition
                                quantity,  # Assume all received
                                0,  # None rejected initially
                                datetime.now().isoformat(),  # created_at
                                datetime.now().isoformat()   # updated_at
                            )))
                        return_items_created += 1
                        print(f"    Return item created successfully for return {return_id}!")
                    except Exception as e:
                        print(f"    CRITICAL: Return item insert failed for return {return_id}: {e}")
                        # This is the critical failure - return_items not being created

        # Commit all changes
        conn.commit()
        conn.close()

        sync_status["is_running"] = False
        sync_status["last_sync_status"] = "success"
        sync_status["last_sync_message"] = f"Targeted sync: {returns_with_data} returns with data, {return_items_created} items created"
        sync_status["return_items_synced"] = return_items_created

        return {
            "status": "success",
            "message": f"Targeted sync completed successfully",
            "processed_returns": processed_count,
            "returns_with_product_data": returns_with_data,
            "return_items_created": return_items_created
        }

    except Exception as e:
        sync_status["is_running"] = False
        sync_status["last_sync_status"] = "error"
        sync_status["last_sync_message"] = f"Targeted sync error: {str(e)}"

        if 'conn' in locals():
            conn.close()

        return {
            "status": "error",
            "message": str(e),
            "processed_returns": processed_count,
            "returns_with_product_data": returns_with_data,
            "return_items_created": return_items_created
        }




def convert_date_for_sql(date_string):
    """Convert API date string to SQL Server compatible format"""
    if not date_string:
        return None

    try:
        # print(f"DATE CONVERSION: Converting '{date_string}'")
        # Parse the date string and convert to ISO format that SQL Server accepts
        from datetime import datetime
        # Handle multiple possible formats from API
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',     # ISO with microseconds
            '%Y-%m-%dT%H:%M:%SZ',        # ISO without microseconds
            '%Y-%m-%dT%H:%M:%S%z',       # ISO with timezone offset (Warehance API format)
            '%Y-%m-%dT%H:%M:%S.%f%z',    # ISO with microseconds and timezone
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
                result = dt.strftime('%Y-%m-%d %H:%M:%S')
                # print(f"DATE CONVERSION: Successfully converted '{date_string}' to '{result}' using format '{fmt}'")
                return result
            except ValueError:
                continue

        # If no format matches, return None to avoid SQL errors
        print(f"DATE CONVERSION ERROR: No format matched for '{date_string}'")
        return None
    except Exception as e:
        # If all else fails, return None to avoid SQL errors
        print(f"DATE CONVERSION ERROR: Exception converting '{date_string}': {e}")
        return None

async def run_sync():
    """Run the actual sync process"""
    global sync_status

    print("RUN_SYNC: Starting sync process")
    # Sync status already initialized in trigger_sync to prevent race conditions
    print(f"RUN_SYNC: Status already set, is_running={sync_status['is_running']}")

    try:
        # print("=== RUN_SYNC: Checking API key and database connection ===")
        api_key = os.getenv('WAREHANCE_API_KEY')
        if not api_key:
            print("RUN_SYNC ERROR: WAREHANCE_API_KEY not found")
            sync_status["last_sync_status"] = "error"
            sync_status["last_sync_message"] = "WAREHANCE_API_KEY not configured"
            return

        # print(f"=== RUN_SYNC: API key found, length={len(api_key)} ===")

        # Initialize database tables if using Azure SQL
        if USE_AZURE_SQL:
            print("RUN_SYNC: Initializing Azure SQL database")
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

        # print(f"=== SYNC DEBUG: Starting sync with API key: {api_key[:15]}...")
        sync_status["last_sync_message"] = f"STEP 1: Starting sync with API key: {api_key[:15]}..."

        # Test database connection early with detailed logging
        print("SYNC DEBUG: Testing database connection")
        sync_status["last_sync_message"] = "STEP 2: Testing database connection..."

        # CRITICAL: Ensure database schema is migrated before sync
        print("SYNC DEBUG: Ensuring database schema is migrated (INT -> BIGINT)")
        sync_status["last_sync_message"] = "STEP 2.1: Running database migration..."
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if products.id is still INT and needs migration
            if USE_AZURE_SQL:
                cursor.execute("""
                    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'id'
                """)
                result = cursor.fetchone()
                current_type = result['data_type'] if result else "unknown"

                if current_type == "int":
                    print(f"🔧 SYNC DEBUG: products.id is {current_type}, running migration to BIGINT...")
                    # Run critical migrations
                    migrations = [
                        "ALTER TABLE products ALTER COLUMN id BIGINT",
                        "ALTER TABLE return_items ALTER COLUMN product_id BIGINT"
                    ]
                    # CURSOR PERFORMANCE FIX: Execute all migrations then batch commit
                    migration_success = True
                    for migration in migrations:
                        try:
                            cursor.execute(migration)
                            print(f"SUCCESS: SYNC DEBUG: Migration executed: {migration}")
                        except Exception as mig_err:
                            print(f"WARNING: SYNC DEBUG: Migration warning: {migration} - {mig_err}")
                            migration_success = False

                    # Batch commit all migrations at once
                    if migration_success:
                        conn.commit()
                        print("🚀 PERFORMANCE: All migrations committed in batch")

                    # Verify migration
                    cursor.execute("""
                        SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'id'
                    """)
                    new_result = cursor.fetchone()
                    new_type = new_result['data_type'] if new_result else "unknown"
                    print(f"SUCCESS: SYNC DEBUG: products.id type after migration: {new_type}")
                else:
                    print(f"SUCCESS: SYNC DEBUG: products.id already {current_type}, migration not needed")

            conn.close()
        except Exception as schema_err:
            print(f"WARNING: SYNC DEBUG: Schema migration error (continuing): {schema_err}")

        sync_status["last_sync_message"] = "STEP 2.2: Database migration completed, continuing sync..."

        # print(f"SYNC DEBUG: USE_AZURE_SQL = {USE_AZURE_SQL}")
        # print(f"SYNC DEBUG: DATABASE_URL exists = {bool(os.getenv('DATABASE_URL'))}")

        # 🚀 CURSOR PERFORMANCE FIX: Removed inefficient individual API calls (1,000+ calls)
        # Now using efficient batch API processing below (10 batch calls instead)
        print("🚀 PERFORMANCE: Skipping individual API calls, using batch processing...")
        sync_status["last_sync_message"] = "STEP 2.3: Using efficient batch API processing..."

        conn = get_db_connection()
        if not conn:
            raise Exception("STEP 2 FAILED: Failed to establish database connection")

        print("SYNC DEBUG: Database connection established, creating cursor")
        cursor = conn.cursor()
        sync_status["last_sync_message"] = "STEP 3: Database cursor created..."

        # Test basic database operation
        try:
            print("SYNC DEBUG: Testing basic database query")
            if USE_AZURE_SQL:
                cursor.execute("SELECT 1 as test")
            else:
                cursor.execute("SELECT 1")
            test_result = cursor.fetchone()
            # print(f"SYNC DEBUG: Database test query successful: {test_result}")
            sync_status["last_sync_message"] = "STEP 4: Database connection confirmed"
        except Exception as db_test_error:
            # print(f"SYNC DEBUG: Database test query failed: {db_test_error}")
            raise Exception(f"STEP 4 FAILED: Database test query failed: {db_test_error}")

        # STEP 5: Fetch ALL returns from API with pagination
        # print("=== SYNC DEBUG: Starting API fetch phase...")
        sync_status["last_sync_message"] = "STEP 5: Fetching returns from Warehance API..."
        # print("=== SYNC DEBUG: Starting to fetch returns from Warehance API...")
        all_order_ids = set()  # Collect unique order IDs
        # Start from recent returns (last 200) to get returns with new order/items data
        # API was updated last week, so focus on recent returns
        offset = 0  # Start from most recent
        limit = 100  # 🚀 SPEED: Maximum allowed batch size by Warehance API (was 200)
        max_returns_to_process = 500  # 🚀 SPEED: Increased limit to process more returns (was 200)
        total_fetched = 0

        while True:
            try:
                url = f"https://api.warehance.com/v1/returns?limit={limit}&offset={offset}"
                log_sync_activity(f"Fetching page: offset={offset}, limit={limit}")
                response = http_session.get(url, headers=headers)

                if response.status_code != 200:
                    error_text = response.text[:500] if response.text else "No response body"
                    print(f"API Error: Status {response.status_code}, Response: {error_text}")
                    sync_status["last_sync_message"] = f"API Error: {response.status_code} - {error_text[:100]}"
                    sync_status["last_sync_status"] = "error"
                    break

                data = response.json()
                # FINAL DISABLE - print(f"API Response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
                # FINAL DISABLE - print(f"API Response data length: {len(data.get('data', [])) if data.get('data') else 0}")

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

                returns_batch = data['data']['returns'] or []  # Handle None case
                print(f"Fetched {len(returns_batch)} returns at offset {offset}")
                sync_status["last_sync_message"] = f"Processing {len(returns_batch)} returns from offset {offset}..."

                if not returns_batch:
                    print("No more returns to process - breaking loop")
                    break

                for ret in returns_batch:
                    return_id = ret['id']
                    client_name = ret.get('client', {}).get('name', 'no-client')

                    # Enhanced logging to see API response structure
                    has_order = bool(ret.get('order'))
                    has_items = bool(ret.get('items'))
                    items_count = len(ret.get('items', [])) if ret.get('items') else 0

                    pass  # DISABLED - print(f"Return {return_id}: order={has_order}, items={has_items} (count: {items_count})")
                    log_sync_activity(f"Processing return {return_id} from {client_name}: order={has_order}, items={items_count}")

                    # Increment progress counter at start of each return processing
                    sync_status["items_synced"] += 1
                    sync_status["last_sync_message"] = f"Processing return #{sync_status['items_synced']} of {max_returns_to_process}"

                    # Update progress every 5 returns for better frontend responsiveness
                    if sync_status["items_synced"] % 5 == 0:
                        sync_status["last_sync_message"] = f"Processing return #{sync_status['items_synced']} of {max_returns_to_process}"
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
                                                 ensure_tuple_params((client_id, client_name)))
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
                                                 ensure_tuple_params((warehouse_id, warehouse_name)))
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

                    # Collect order ID if present - handle multiple API response formats
                    order_id_to_collect = None
                    if ret.get('order'):
                        if isinstance(ret['order'], dict):
                            # Nested object format: {"order": {"id": "123"}}
                            order_id_to_collect = ret['order'].get('id')
                        else:
                            # Direct ID format: {"order": "123"}
                            order_id_to_collect = ret['order']
                    elif ret.get('order_id'):
                        # Alternative field name: {"order_id": "123"}
                        order_id_to_collect = ret['order_id']

                    if order_id_to_collect:
                        all_order_ids.add(str(order_id_to_collect))
                        print(f"📋 Collected order ID {order_id_to_collect} for return {return_id}")

                    # Update or insert return - with overflow protection
                    # Convert large IDs to string to prevent arithmetic overflow
                    if isinstance(return_id, int) and return_id > 2147483647:
                        return_id = str(return_id)

                    if USE_AZURE_SQL:
                        # Use IF EXISTS for Azure SQL (simpler than MERGE)
                        placeholder = get_param_placeholder()
                        cursor.execute(f"SELECT COUNT(*) as count FROM returns WHERE CAST(id AS NVARCHAR(50)) = {placeholder}", ensure_tuple_params((return_id,)))
                        return_result = cursor.fetchone()
                        exists = (return_result['count'] > 0 if USE_AZURE_SQL else return_result[0] > 0)

                        if exists:
                            # Update existing return
                            placeholder = get_param_placeholder()
                            cursor.execute(f"""
                                UPDATE returns SET
                                    api_id = {placeholder}, paid_by = {placeholder}, status = {placeholder}, created_at = {placeholder},
                                    updated_at = {placeholder}, processed = {placeholder}, processed_at = {placeholder},
                                    warehouse_note = {placeholder}, customer_note = {placeholder}, tracking_number = {placeholder},
                                    tracking_url = {placeholder}, carrier = {placeholder}, service = {placeholder}, label_cost = {placeholder},
                                    label_pdf_url = {placeholder}, rma_slip_url = {placeholder}, label_voided = {placeholder},
                                    client_id = {placeholder}, warehouse_id = {placeholder}, order_id = {placeholder},
                                    return_integration_id = {placeholder}, last_synced_at = {placeholder}
                                WHERE CAST(id AS NVARCHAR(50)) = {placeholder}
                            """, (
                                ret.get('api_id'), ret.get('paid_by', ''),
                                ret.get('status', ''), convert_date_for_sql(ret.get('created_at')), convert_date_for_sql(ret.get('updated_at')),
                                ret.get('processed', False), convert_date_for_sql(ret.get('processed_at')),
                                ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                                ret.get('tracking_number'), ret.get('tracking_url'),
                                ret.get('carrier', ''), ret.get('service', ''),
                                ret.get('label_cost'), ret.get('label_pdf_url'),
                                ret.get('rma_slip_url'), ret.get('label_voided', False),
                                str(ret['client']['id']) if ret.get('client') else None,
                                str(ret['warehouse']['id']) if ret.get('warehouse') else None,
                                str(ret['order']['id']) if ret.get('order') else None,
                                ret.get('return_integration_id'),
                                convert_date_for_sql(datetime.now().isoformat()),
                                return_id  # WHERE clause
                            ))
                        else:
                            # Insert new return with duplicate handling
                            try:
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    INSERT INTO returns (id, api_id, paid_by, status, created_at, updated_at,
                                            processed, processed_at, warehouse_note, customer_note,
                                            tracking_number, tracking_url, carrier, service,
                                            label_cost, label_pdf_url, rma_slip_url, label_voided,
                                            client_id, warehouse_id, order_id, return_integration_id,
                                            last_synced_at)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, ensure_tuple_params((
                                return_id, ret.get('api_id'), ret.get('paid_by', ''),
                                ret.get('status', ''), convert_date_for_sql(ret.get('created_at')), convert_date_for_sql(ret.get('updated_at')),
                                ret.get('processed', False), convert_date_for_sql(ret.get('processed_at')),
                                ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                                ret.get('tracking_number'), ret.get('tracking_url'),
                                ret.get('carrier', ''), ret.get('service', ''),
                                ret.get('label_cost'), ret.get('label_pdf_url'),
                                ret.get('rma_slip_url'), ret.get('label_voided', False),
                                str(ret['client']['id']) if ret.get('client') else None,
                                str(ret['warehouse']['id']) if ret.get('warehouse') else None,
                                str(ret['order']['id']) if ret.get('order') else None,
                                ret.get('return_integration_id'),
                                convert_date_for_sql(datetime.now().isoformat())
                            )))
                            except Exception as insert_error:
                                if "duplicate key" in str(insert_error).lower() or "primary key constraint" in str(insert_error).lower():
                                    print(f"Duplicate return {return_id} already exists, skipping insert")
                                else:
                                    print(f"Unexpected INSERT error for return {return_id}: {insert_error}")
                                    raise
                else:
                    # Use INSERT OR REPLACE for SQLite
                    placeholder = get_param_placeholder()
                    cursor.execute(f"""
                        INSERT INTO returns (
                        id, api_id, paid_by, status, created_at, updated_at,
                        processed, processed_at, warehouse_note, customer_note,
                        tracking_number, tracking_url, carrier, service,
                        label_cost, label_pdf_url, rma_slip_url, label_voided,
                        client_id, warehouse_id, order_id, return_integration_id,
                        last_synced_at
                        ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    """, ensure_tuple_params((
                    return_id, ret.get('api_id'), ret.get('paid_by', ''),
                    ret.get('status', ''), convert_date_for_sql(ret.get('created_at')), convert_date_for_sql(ret.get('updated_at')),
                    ret.get('processed', False), convert_date_for_sql(ret.get('processed_at')),
                    ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                    ret.get('tracking_number'), ret.get('tracking_url'),
                    ret.get('carrier', ''), ret.get('service', ''),
                    ret.get('label_cost'), ret.get('label_pdf_url'),
                    ret.get('rma_slip_url'), ret.get('label_voided', False),
                    str(ret['client']['id']) if ret.get('client') else None,
                    str(ret['warehouse']['id']) if ret.get('warehouse') else None,
                    str(ret['order']['id']) if ret.get('order') else None,
                    ret.get('return_integration_id'),
                    convert_date_for_sql(datetime.now().isoformat())
                )))

                # Store order info - always make separate API call for complete data
                order_data = None
                # Extract order ID from returns API response - use same robust logic as collection
                order_id = None
                if ret.get('order'):
                    if isinstance(ret['order'], dict):
                        # Nested object format: {"order": {"id": "123"}}
                        order_id = str(ret['order'].get('id')) if ret['order'].get('id') else None
                    else:
                        # Direct ID format: {"order": "123"}
                        order_id = str(ret['order'])
                elif ret.get('order_id'):  # Alternative field name: {"order_id": "123"}
                    order_id = str(ret['order_id'])

                # Always make separate API call to get complete order details with customer name
                if order_id:
                    # Make separate API call to fetch order details
                    try:
                        print(f"🔄 Return {return_id}: Making API call for order {order_id}")
                        sync_status["last_sync_message"] = f"Fetching order {order_id} for return {return_id}"
                        order_response = requests.get(
                            f"https://api.warehance.com/v1/orders/{order_id}",
                            headers=headers,
                            timeout=3  # 🚀 PERFORMANCE: Reduced from 10s to 3s for speed
                        )

                        if order_response.status_code == 200:
                            order_api_data = order_response.json()
                            if order_api_data.get("status") == "success":
                                order_data = order_api_data.get("data", {})
                                pass  # DISABLED - print(f"SUCCESS: Return {return_id}: Successfully fetched order {order_id} - Customer: {order_data.get('ship_to_address', {}).get('first_name', '')} {order_data.get('ship_to_address', {}).get('last_name', '')}")
                                # print(f"ORDER DATA DEBUG: Order {order_id} created_at: {order_data.get('created_at')}")
                            else:
                                pass  # DISABLED - print(f"Return {return_id}: Order API returned non-success status: {order_api_data.get('status')}")
                        else:
                            pass  # DISABLED - print(f"Return {return_id}: Order API call failed with status {order_response.status_code}")
                    except Exception as order_err:
                        pass  # DISABLED - print(f"Return {return_id}: Error fetching order {order_id}: {order_err}")

                # Insert order data if we have it
                if order_data:
                    try:
                        # Extract customer name from ship_to_address
                        ship_addr = order_data.get('ship_to_address', {})
                        first_name = ship_addr.get('first_name', '') if isinstance(ship_addr, dict) else ''
                        last_name = ship_addr.get('last_name', '') if isinstance(ship_addr, dict) else ''
                        customer_name = f"{first_name} {last_name}".strip() or "Unknown Customer"
                        # print(f"ORDER PROCESSING DEBUG: Processing order {order_data['id']} with customer '{customer_name}'")

                        if USE_AZURE_SQL:
                            # Check if order exists first
                            placeholder = get_param_placeholder()
                            cursor.execute(f"SELECT COUNT(*) as count FROM orders WHERE CAST(id AS NVARCHAR(50)) = {placeholder}", (str(order_data['id']),))
                            order_result = cursor.fetchone()
                            if (order_result['count'] == 0 if USE_AZURE_SQL else order_result[0] == 0):
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    INSERT INTO orders (id, order_number, customer_name, created_at, updated_at)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                                """, ensure_tuple_params((
                                    str(order_data['id']),
                                    order_data.get('order_number', ''),
                                    customer_name,
                                    convert_date_for_sql(order_data.get('created_at')),  # Use actual order date from API
                                    convert_date_for_sql(datetime.now().isoformat())    # Updated at current time
                                )))
                                sync_status["orders_synced"] += 1
                                print(f"Inserted order {order_data['id']} with customer '{customer_name}'")
                        else:
                            placeholder = get_param_placeholder()
                            cursor.execute(f"""
                                INSERT OR IGNORE INTO orders (id, order_number, customer_name, created_at, updated_at)
                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, ensure_tuple_params((
                                str(order_data['id']),
                                order_data.get('order_number', ''),
                                customer_name,
                                convert_date_for_sql(order_data.get('created_at')),  # Use actual order date from API
                                datetime.now().isoformat()  # Updated at current time
                            )))
                            sync_status["orders_synced"] += 1
                    except Exception as e:
                        import traceback
                        print(f"ERROR inserting order {str(order_data['id'])}: {e}")
                        print(f"Full traceback: {traceback.format_exc()}")
                        print(f"Order data: {order_data}")
                        print(f"Customer name: {customer_name}")

                # Store return items - use optimized concurrent approach
                items_data = []

                # 🚀 SPEED OPTIMIZATION: Use the optimized function for faster API calls
                # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Fetching individual return with items data")
                return_id_result, items_data, error = fetch_return_items_data(return_id, headers)

                if items_data:
                    # # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Successfully fetched {len(items_data)} items via individual API")
                    if items_data:
                        pass  # DISABLED TRACE - print(f"SYNC TRACE: First item structure: {items_data[0]}")
                elif error:
                    pass  # DISABLED - # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: {error}")
                    # Fallback: Try separate items API call if individual return didn't work
                    # # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Fallback to separate items API call")
                    try:
                        items_response = http_session.get(
                            f"https://api.warehance.com/v1/returns/{return_id}/items",
                            headers=headers,
                            timeout=1.5  # 🚀 SPEED: Reduced from 3s to 1.5s for maximum speed
                        )
                        if items_response.status_code == 200:
                            items_api_data = items_response.json()
                            # # DISABLED TRACE - print(f"SYNC TRACE: Items API response: {items_api_data}")
                            if items_api_data.get("status") == "success":
                                items_data = items_api_data.get("data", [])
                                # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Successfully fetched {len(items_data)} return items")
                            else:
                                pass  # DISABLED - # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Items API returned non-success status: {items_api_data.get('status')}")
                        else:
                            pass  # DISABLED - # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Items API call failed with status {items_response.status_code}")
                    except Exception as items_err:
                        # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id}: Error fetching return items: {items_err}")
                        items_data = []

                # Process return items if we have them
                if items_data:
                    items_count = len(items_data)
                    # DISABLED TRACE - print(f"SYNC TRACE: Processing {items_count} return items for return {return_id}")
                    log_sync_activity(f"Processing {items_count} return items for return {return_id}")
                    for item_idx, item in enumerate(items_data, 1):
                        # DISABLED TRACE - print(f"SYNC TRACE: Item {item_idx}/{items_count} full structure: {item}")
                        # Get or create product
                        product_id = item.get('product', {}).get('id', 0)
                        product_sku = item.get('product', {}).get('sku', '')
                        product_name = item.get('product', {}).get('name', '')
                        # DISABLED TRACE - print(f"SYNC TRACE: Item {item_idx}/{items_count}: Product ID={product_id}, SKU='{product_sku}', Name='{product_name}'")
                        log_sync_activity(f"Item {item_idx}/{items_count}: Product ID={product_id}, SKU={product_sku}, Name={product_name[:30]}...")

                        # CRITICAL FIX: Process ALL products with SKU, not just those with product_id == 0
                        # Previous logic skipped products with large API IDs (like 231185187982)
                        # DISABLED TRACE - print(f"SYNC TRACE: Product logic check - product_id={product_id}, product_sku='{product_sku}', has_sku={bool(product_sku)}")
                        if product_sku:
                            # DISABLED TRACE - print(f"SYNC TRACE: Taking path 1: product_id=0 AND has SKU")
                            # Original logic for products with SKU but no ID
                            # Try to find existing product by SKU
                            placeholder = get_param_placeholder()
                            cursor.execute(f"SELECT id as product_id FROM products WHERE sku = {placeholder}", (product_sku,))
                            existing = cursor.fetchone()
                            if existing:
                                actual_product_id = existing['product_id'] if USE_AZURE_SQL else existing[0]
                                # DISABLED TRACE - print(f"SYNC TRACE: Found existing product: SKU={product_sku}, DB ID={actual_product_id}")
                            else:
                                # Create a placeholder product
                                placeholder = get_param_placeholder()
                                if USE_AZURE_SQL:
                                    # 🚨 FIXED: Remove explicit ID INSERT for IDENTITY column
                                    cursor.execute(f"""
                                        INSERT INTO products (sku, name, created_at, updated_at)
                                        VALUES ({placeholder}, {placeholder}, GETDATE(), GETDATE())
                                    """, ensure_tuple_params((product_sku, product_name or 'Unknown Product')))
                                else:
                                    cursor.execute(f"""
                                        INSERT INTO products (id, sku, name, created_at, updated_at)
                                        VALUES ({placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                    """, ensure_tuple_params((product_id, product_sku, product_name or 'Unknown Product')))
                                # Get the newly created product ID
                                if USE_AZURE_SQL:
                                    cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (product_sku,))
                                    new_product = cursor.fetchone()
                                    actual_product_id = new_product['id'] if new_product else None
                                else:
                                    actual_product_id = cursor.lastrowid
                                sync_status["products_synced"] += 1
                                # DISABLED TRACE - print(f"SYNC TRACE: Created product: SKU={product_sku}, DB ID={actual_product_id}")
                        elif product_id > 0:
                            # Ensure product exists - simplified approach
                            try:
                                if USE_AZURE_SQL:
                                    # Check if product exists by SKU, insert if not
                                    placeholder = get_param_placeholder()
                                    cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (product_sku,))
                                    existing_product = cursor.fetchone()
                                    if not existing_product:
                                        cursor.execute(f"""
                                            INSERT INTO products (sku, name, created_at, updated_at)
                                            VALUES ({placeholder}, {placeholder}, GETDATE(), GETDATE())
                                        """, ensure_tuple_params((product_sku, product_name)))
                                        # Get the newly inserted product ID
                                        cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (product_sku,))
                                        new_product = cursor.fetchone()
                                        actual_product_id = new_product['id'] if new_product else None
                                        sync_status["products_synced"] += 1
                                        print(f"Product inserted: SKU: {product_sku}, DB ID: {actual_product_id}")
                                    else:
                                        actual_product_id = existing_product['id']
                                        print(f"Product exists: SKU: {product_sku}, DB ID: {actual_product_id}")
                                else:
                                    # SQLite version - can use explicit IDs
                                    cursor.execute("""
                                        INSERT OR IGNORE INTO products (id, sku, name, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (product_id, product_sku, product_name, datetime.now().isoformat(), datetime.now().isoformat()))
                                    sync_status["products_synced"] += 1
                            except Exception as prod_err:
                                print(f"Product INSERT error for ID {product_id}: {prod_err}")
                                # 🚨 CRITICAL FIX: Set actual_product_id to None on error to prevent undefined variable
                                actual_product_id = None
                                # Continue processing even if product insert fails
                        elif product_id == 0 and not product_sku:
                            # DISABLED TRACE - print(f"SYNC TRACE: Taking path 2: product_id=0 AND no SKU - creating placeholder")
                            # Handle case where both product_id and product_sku are missing/empty
                            # Create a placeholder product for the return item
                            try:
                                item_id = item.get('id', 'unknown')
                                placeholder_sku = f"UNKNOWN_ITEM_{item_id}"
                                placeholder_name = f"Return Item {item_id} (No Product Data)"
                                # DISABLED TRACE - print(f"SYNC TRACE: Creating placeholder - item_id={item_id}, sku={placeholder_sku}, name={placeholder_name}")

                                if USE_AZURE_SQL:
                                    placeholder = get_param_placeholder()
                                    cursor.execute(f"""
                                        INSERT INTO products (sku, name, created_at, updated_at)
                                        VALUES ({placeholder}, {placeholder}, GETDATE(), GETDATE())
                                    """, ensure_tuple_params((placeholder_sku, placeholder_name)))
                                    # Get the newly inserted product ID
                                    cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (placeholder_sku,))
                                    new_product = cursor.fetchone()
                                    actual_product_id = new_product['id'] if new_product else None
                                    sync_status["products_synced"] += 1
                                    print(f"Placeholder product created: SKU: {placeholder_sku}, DB ID: {actual_product_id}")
                                else:
                                    # SQLite version
                                    cursor.execute("""
                                        INSERT INTO products (sku, name, created_at, updated_at)
                                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                    """, (placeholder_sku, placeholder_name))
                                    actual_product_id = cursor.lastrowid
                                    sync_status["products_synced"] += 1
                            except Exception as placeholder_err:
                                print(f"Error creating placeholder product for item {item_id}: {placeholder_err}")
                                actual_product_id = None
                        else:
                            # DISABLED TRACE - print(f"SYNC TRACE: Taking path 3: product_id > 0 ({product_id})")
                            # 🚨 CRITICAL FIX: For Azure SQL, we need to look up the actual DB ID since we can't use API IDs
                            if USE_AZURE_SQL:
                                # Look up the product by SKU to get the actual database ID
                                try:
                                    placeholder = get_param_placeholder()
                                    cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (product_sku,))
                                    existing_product = cursor.fetchone()
                                    if existing_product:
                                        actual_product_id = existing_product['id']
                                        # DISABLED TRACE - print(f"SYNC TRACE: Azure SQL path - found product by SKU: {product_sku}, DB ID: {actual_product_id}")
                                    else:
                                        # DISABLED TRACE - print(f"SYNC TRACE: Azure SQL path - product not found for SKU: {product_sku}")
                                        actual_product_id = None
                                except Exception as lookup_err:
                                    # DISABLED TRACE - print(f"SYNC TRACE: Error looking up product by SKU {product_sku}: {lookup_err}")
                                    actual_product_id = None
                            else:
                            # For SQLite, we can use the API product_id directly
                                actual_product_id = product_id
                                # DISABLED TRACE - print(f"SYNC TRACE: SQLite path - using API product_id: {actual_product_id}")

                        # Store return item with proper error handling
                        # DISABLED TRACE - print(f"SYNC TRACE: Preparing to create return_item - return_id={return_id}, actual_product_id={actual_product_id}")
                        import json
                        try:
                            if USE_AZURE_SQL:
                                # DISABLED TRACE - print(f"SYNC TRACE: Azure SQL path - checking if return_item exists")
                                # Simplified insert for Azure SQL - check and insert
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    SELECT COUNT(*) as count FROM return_items
                                    WHERE CAST(return_id AS NVARCHAR(50)) = {placeholder} AND CAST(product_id AS NVARCHAR(50)) = {placeholder}
                                """, (str(return_id), actual_product_id))
                                result = cursor.fetchone()
                                exists = result['count'] > 0 if USE_AZURE_SQL else result[0] > 0
                                # DISABLED TRACE - print(f"SYNC TRACE: Return item exists check - count={result}, exists={exists}, actual_product_id={actual_product_id}")
                                if not exists and actual_product_id:
                                    cursor.execute(f"""
                                        INSERT INTO return_items (return_id, product_id, quantity, return_reasons,
                                               condition_on_arrival, quantity_received, quantity_rejected, created_at, updated_at)
                                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                                               {placeholder}, {placeholder}, {placeholder}, {placeholder})
                                    """, ensure_tuple_params((
                                        str(return_id),  # Convert to string for NVARCHAR field
                                        actual_product_id,
                                        item.get('quantity', 0),
                                        json.dumps(item.get('return_reasons', [])),
                                        json.dumps(item.get('condition_on_arrival', [])),
                                        item.get('quantity_received', 0),
                                        item.get('quantity_rejected', 0),
                                        convert_date_for_sql(datetime.now().isoformat()),  # created_at
                                        convert_date_for_sql(datetime.now().isoformat())   # updated_at
                                    )))
                                    sync_status["return_items_synced"] += 1
                                    # DISABLED TRACE - print(f"SYNC TRACE: Return item inserted successfully: return {return_id}, product {actual_product_id}, qty {item.get('quantity', 0)}")
                                elif not actual_product_id:
                                    pass  # DISABLED TRACE - print(f"SYNC TRACE: Skipping return item - no valid product ID")
                                else:
                                    pass  # DISABLED TRACE - print(f"SYNC TRACE: Skipping return item - already exists")
                            else:
                                # SQLite - use INSERT OR REPLACE
                                placeholder = get_param_placeholder()
                                cursor.execute(f"""
                                    INSERT OR REPLACE INTO return_items (
                                        return_id, product_id, quantity,
                                        return_reasons, condition_on_arrival,
                                        quantity_received, quantity_rejected,
                                        created_at, updated_at
                                    ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                                """, ensure_tuple_params((
                                    return_id,
                                    product_id if product_id > 0 else None,
                                    item.get('quantity', 0),
                                    json.dumps(item.get('return_reasons', [])),
                                    json.dumps(item.get('condition_on_arrival', [])),
                                    item.get('quantity_received', 0),
                                    item.get('quantity_rejected', 0),
                                    datetime.now().isoformat(),  # created_at
                                    datetime.now().isoformat()   # updated_at
                                )))
                                sync_status["return_items_synced"] += 1
                        except Exception as item_err:
                            print(f"Return item INSERT error for return {return_id}, product {product_id}: {item_err}")
                            # Continue processing other items

                    # DISABLED TRACE - print(f"SYNC TRACE: Successfully processed return {return_id} with {items_count} items")
                    log_sync_activity(f"Successfully processed return {return_id} with {items_count} items")
                else:
                    # DISABLED TRACE - print(f"SYNC TRACE: No items found for return {return_id} - items_data is empty")
                    # DISABLED TRACE - print(f"SYNC TRACE: Return {return_id} items field from API: {ret.get('items')}")
                    log_sync_activity(f"Return {return_id} has no items (items field: {ret.get('items')})")
                    # DISABLED TRACE - print(f"SYNC TRACE: Successfully processed return {return_id} (no items)")

                total_fetched += len(returns_batch)

                # Check if we've fetched enough recent returns or reached limit
                total_count = data['data'].get('total_count', 0)
                if total_fetched >= max_returns_to_process or len(returns_batch) < limit:
                    print(f"Stopping sync: processed {total_fetched} recent returns (limit: {max_returns_to_process})")
                    print(f"🔢 COLLECTED {len(all_order_ids)} unique order IDs from {total_fetched} returns")
                    if len(all_order_ids) > 0:
                        sample_ids = list(all_order_ids)[:5]
                        print(f"📝 Sample order IDs: {sample_ids}")
                    break

            except Exception as e:
                error_str = str(e)
                log_sync_activity(f"ERROR in sync loop: {error_str}")

                # Check if this is a duplicate key error that we can gracefully handle
                if "duplicate key" in error_str.lower() or "primary key constraint" in error_str.lower():
                    log_sync_activity(f"Duplicate key detected - continuing sync, advancing to offset {offset + limit}")
                    sync_status["last_sync_message"] = f"Handling duplicate records... ({sync_status['items_synced']} processed)"
                    # Still increment offset even on duplicate key errors to avoid infinite loop
                    offset += limit
                    continue  # Continue processing instead of breaking
                else:
                    # For other errors, break the sync
                    log_sync_activity(f"CRITICAL ERROR - breaking sync: {error_str[:200]}")
                    sync_status["last_sync_message"] = f"Error: {error_str[:100]}"
                    break

            # Normal pagination increment (moved outside try block)
            offset += limit
            log_sync_activity(f"Page completed successfully - advancing to offset {offset}")

            # Removed artificial delay per Cursor's performance optimization

        # 🚀 CRITICAL FIX: Commit all products and return items created during batch processing
        print("🚀 PERFORMANCE: Committing all products and return items from batch processing...")
        conn.commit()
        print(f"SUCCESS: BATCH COMMIT: Successfully committed {sync_status.get('products_synced', 0)} products and {sync_status.get('return_items_synced', 0)} return items")

        # STEP 1.5: Fetch orders from API to populate orders table
        print("🔄 STEP 1.5: Fetching orders from API to populate orders table...")
        sync_status["last_sync_message"] = "STEP 1.5: Fetching orders from API..."

        # Fetch orders in batches
        offset = 0
        batch_size = 100  # Warehance API limit
        orders_fetched = 0

        while True:
            url = f"https://api.warehance.com/v1/orders?limit={batch_size}&offset={offset}"
            print(f"Fetching orders: offset={offset}, limit={batch_size}")
            response = http_session.get(url, headers=headers)

            if response.status_code != 200:
                print(f"Orders API error: {response.status_code}")
                break

            data = response.json()
            orders_data = data.get('data', {}).get('orders', [])

            if not orders_data:
                print("No more orders to fetch")
                break

            print(f"Processing {len(orders_data)} orders...")

            for order_data in orders_data:
                order_id = str(order_data['id'])
                # Extract customer name from ship_to_address
                ship_to = order_data.get('ship_to_address', {})
                customer_name = f"{ship_to.get('first_name', '')} {ship_to.get('last_name', '')}".strip()

                # Check if order already exists
                cursor.execute(f"SELECT COUNT(*) as count FROM orders WHERE CAST(id AS NVARCHAR(50)) = {get_param_placeholder()}", (order_id,))
                result = cursor.fetchone()
                if (result['count'] == 0 if USE_AZURE_SQL else result[0] == 0):
                    # Insert new order with correct date
                    try:
                        cursor.execute(f"""
                            INSERT INTO orders (id, order_number, customer_name, created_at, updated_at)
                            VALUES ({get_param_placeholder()}, {get_param_placeholder()}, {get_param_placeholder()}, {get_param_placeholder()}, {get_param_placeholder()})
                        """, ensure_tuple_params((
                            order_id,
                            order_data.get('order_number', ''),
                            customer_name,
                            convert_date_for_sql(order_data.get('order_date')),  # Use actual order date from API
                            convert_date_for_sql(datetime.now().isoformat())
                        )))
                        orders_fetched += 1
                    except Exception as e:
                        print(f"❌ Error inserting order {order_id}: {e}")
                        continue
                else:
                    # Update existing order with correct date
                    try:
                        cursor.execute(f"""
                            UPDATE orders
                            SET customer_name = {get_param_placeholder()}, order_number = {get_param_placeholder()},
                                created_at = {get_param_placeholder()}, updated_at = {get_param_placeholder()}
                            WHERE CAST(id AS NVARCHAR(50)) = {get_param_placeholder()}
                        """, ensure_tuple_params((
                            customer_name,
                            order_data.get('order_number', ''),
                            convert_date_for_sql(order_data.get('order_date')),  # Use actual order date from API
                            convert_date_for_sql(datetime.now().isoformat()),
                            order_id
                        )))
                    except Exception as e:
                        print(f"❌ Error updating order {order_id}: {e}")
                        continue

            offset += batch_size

            # Break if we got fewer orders than requested (end of data)
            if len(orders_data) < batch_size:
                break

        print(f"SUCCESS: ORDERS SYNC: Fetched {orders_fetched} new orders from API")
        sync_status["orders_synced"] = orders_fetched

        # Commit orders to database
        conn.commit()
        print(f"SUCCESS: ORDERS COMMIT: Successfully committed {orders_fetched} orders")

        # STEP 2: Fetch orders from DATABASE (ignore API collection) and populate missing customer names
        print("🔄 STEP 2: Using database-driven approach like individual return endpoint...")
        sync_status["last_sync_message"] = "STEP 2: Querying database for returns with order IDs..."

        # 🚨 CRITICAL FIX: Get ALL returns with order_ids that need return_items created
        # Don't limit to missing customer names - we need return_items for ALL older returns
        cursor.execute("""
            SELECT DISTINCT r.order_id, r.id as return_id
            FROM returns r
            LEFT JOIN return_items ri ON CAST(r.id AS NVARCHAR(50)) = CAST(ri.return_id AS NVARCHAR(50))
            WHERE r.order_id IS NOT NULL
            AND ri.return_id IS NULL
        """)
        order_id_rows = cursor.fetchall()
        if USE_AZURE_SQL:
            order_id_rows = rows_to_dict(cursor, order_id_rows) if order_id_rows else []

        # Extract both order_id and return_id from the query results
        orders_needing_processing = []
        for row in order_id_rows:
            if USE_AZURE_SQL:
                orders_needing_processing.append({
                    'order_id': row['order_id'],
                    'return_id': row['return_id']
                })
            else:
                orders_needing_processing.append({
                    'order_id': row[0],
                    'return_id': row[1]
                })

        print(f"📋 Found {len(orders_needing_processing)} returns with order IDs needing return_items created")

        # Fetch order details in batches (NO LIMIT - process all orders)
        batch_size = 100  # 🚀 SPEED: Maximum allowed batch size by Warehance API (was 50)
        print(f"🚀 PERFORMANCE: Processing ALL {len(orders_needing_processing)} orders (no 500 limit) in batches of {batch_size}")
        customers_updated = 0
        for i in range(0, len(orders_needing_processing), batch_size):  # Process ALL orders (removed 500 limit)
            batch = orders_needing_processing[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(orders_needing_processing) + batch_size - 1) // batch_size
            print(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} orders)")
            sync_status["last_sync_message"] = f"Processing batch {batch_num}/{total_batches} - {sync_status['orders_synced']} orders completed"

            for order_data in batch:
                order_id = order_data['order_id']
                return_id = order_data['return_id']
                try:
                    order_response = requests.get(
                        f"https://api.warehance.com/v1/orders/{order_id}",
                        headers=headers,
                        timeout=3  # Reduced from 5s to 3s for speed
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

                        # Insert or update order with full details including customer name
                        placeholder = get_param_placeholder()
                        if USE_AZURE_SQL:
                            # Check if order exists first
                            cursor.execute(f"SELECT COUNT(*) as count FROM orders WHERE CAST(id AS NVARCHAR(50)) = {placeholder}", (order_id,))
                            result = cursor.fetchone()
                            if (result['count'] == 0 if USE_AZURE_SQL else result[0] == 0):
                                # Insert new order
                                cursor.execute(f"""
                                    INSERT INTO orders (id, order_number, customer_name, created_at, updated_at)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                                """, ensure_tuple_params((
                                    order_id,
                                    order_data.get('order_number', ''),
                                    customer_name,
                                    convert_date_for_sql(order_data.get('created_at')),  # Use actual order date from API
                                    convert_date_for_sql(datetime.now().isoformat())    # Updated at current time
                                )))
                                sync_status["orders_synced"] += 1
                                print(f"SUCCESS: Inserted order {order_id} with customer '{customer_name}'")
                            else:
                                # Update existing order with correct order date
                                cursor.execute(f"""
                                    UPDATE orders
                                    SET customer_name = {placeholder}, order_number = {placeholder},
                                        created_at = {placeholder}, updated_at = {placeholder}
                                    WHERE CAST(id AS NVARCHAR(50)) = {placeholder}
                                """, ensure_tuple_params((
                                    customer_name,
                                    order_data.get('order_number', ''),
                                    convert_date_for_sql(order_data.get('created_at')),  # Use actual order date from API
                                    convert_date_for_sql(datetime.now().isoformat()),  # Updated at current time
                                    order_id
                                )))
                                print(f"SUCCESS: Updated order {order_id} with customer '{customer_name}'")
                        else:
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO orders (id, order_number, customer_name, created_at, updated_at)
                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, ensure_tuple_params((
                                order_id,
                                order_data.get('order_number', ''),
                                customer_name,
                                convert_date_for_sql(order_data.get('created_at')),  # Use actual order date from API
                                datetime.now().isoformat()  # Updated at current time
                            )))
                            sync_status["orders_synced"] += 1
                            print(f"SUCCESS: Inserted/updated order {order_id} with customer '{customer_name}'")

                        if customer_name:
                            customers_updated += 1

                        # Process order items and store them as return items
                        order_items = order_data.get('order_items', [])
                        for item in order_items:
                            try:
                                # Get product details
                                product_id = item.get('id')
                                sku = item.get('sku', '')
                                product_name = item.get('name', '')
                                quantity_ordered = item.get('quantity', 0)
                                quantity_shipped = item.get('quantity_shipped', 0)
                                unit_price = item.get('unit_price', 0)

                                # Use shipped quantity if available, otherwise use ordered quantity
                                display_qty = quantity_shipped if quantity_shipped > 0 else quantity_ordered

                                # Only process items that have a name and quantity
                                if product_name and display_qty > 0:
                                    # Ensure product exists
                                    if USE_AZURE_SQL:
                                        placeholder = get_param_placeholder()
                                        # Check if product exists first
                                        cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (sku,))
                                        existing = cursor.fetchone()
                                        if not existing:
                                            cursor.execute(f"""
                                                INSERT INTO products (sku, name, created_at, updated_at)
                                                VALUES ({placeholder}, {placeholder}, GETDATE(), GETDATE())
                                            """, ensure_tuple_params((sku, product_name)))
                                    else:
                                        # SQLite version - can use explicit IDs
                                        cursor.execute("""
                                            INSERT OR IGNORE INTO products (id, sku, name)
                                            VALUES (?, ?, ?)
                                        """, (product_id, sku, product_name))

                                    # Get actual product ID from database (since we can't use explicit ID)
                                    cursor.execute(f"SELECT id FROM products WHERE sku = {placeholder}", (sku,))
                                    db_product = cursor.fetchone()
                                    if db_product:
                                        actual_product_id = db_product['id']
                                    else:
                                        print(f"Warning: Product not found in DB for SKU {sku}")
                                        continue

                                    # 🚨 CRITICAL FIX: Use the return_id we already have from the query
                                    # No need to query again - we know which return needs this return_item

                                        # Check if return item already exists
                                        placeholder = get_param_placeholder()
                                        cursor.execute(f"""
                                            SELECT COUNT(*) as count FROM return_items
                                            WHERE CAST(return_id AS NVARCHAR(50)) = {placeholder} AND CAST(product_id AS NVARCHAR(50)) = {placeholder}
                                        """, (return_id, actual_product_id))
                                        item_result = cursor.fetchone()
                                        if USE_AZURE_SQL:
                                            exists = item_result['count'] > 0 if item_result else False
                                        else:
                                            exists = item_result[0] > 0 if item_result else False

                                        if not exists:
                                            # Create return item from order item
                                            print(f"🎯 Creating return_item: return_id={return_id}, product_id={actual_product_id}, sku={sku}, qty={display_qty}")
                                            if USE_AZURE_SQL:
                                                placeholder = get_param_placeholder()
                                                cursor.execute(f"""
                                                    INSERT INTO return_items
                                                    (return_id, product_id, quantity, return_reasons,
                                                 condition_on_arrival, quantity_received, quantity_rejected, created_at, updated_at)
                                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, GETDATE(), GETDATE())
                                                """, ensure_tuple_params((
                                                    return_id, actual_product_id, display_qty,
                                                    '["Original order item"]',  # Default return reason
                                                    '["Unknown"]',  # Default condition
                                                    display_qty,  # Assume all received
                                                    0  # None rejected initially
                                                )))
                                            else:
                                                cursor.execute("""
                                                    INSERT INTO return_items
                                                    (return_id, product_id, quantity, return_reasons,
                                                 condition_on_arrival, quantity_received, quantity_rejected, created_at, updated_at)
                                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                                """, (
                                                    return_id, actual_product_id, display_qty,
                                                    '["Original order item"]',  # Default return reason
                                                    '["Unknown"]',  # Default condition
                                                    display_qty,  # Assume all received
                                                0,  # None rejected initially
                                                datetime.now().isoformat(),  # created_at
                                                datetime.now().isoformat()   # updated_at
                                                ))

                                        sync_status["return_items_synced"] += 1
                                        print(f"SUCCESS: Created return_item for return {return_id}, product {actual_product_id}")

                            except Exception as item_error:
                                print(f"Error processing order item {item.get('id', 'unknown')}: {item_error}")
                                continue

                    # Removed artificial delay per Cursor's performance optimization

                except Exception as e:
                    print(f"Error fetching order {order_id}: {e}")

            # Update progress
            sync_status["last_sync_message"] = f"Fetched {i+len(batch)} of {len(orders_needing_processing)} orders..."

        conn.commit()
        conn.close()

        # Only mark as success if we actually synced something
        if sync_status['items_synced'] > 0:
            sync_status["last_sync_status"] = "success"
            sync_status["last_sync_message"] = f"Synced {sync_status['items_synced']} returns, {sync_status['products_synced']} products, {sync_status['return_items_synced']} return items, {sync_status['orders_synced']} orders, updated {customers_updated} customer names"
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

        # Enhanced error logging for debugging
        print(f"ERROR DEBUG INFO:")
        print(f"  Exception type: {type(e)}")
        print(f"  Exception args: {e.args}")
        print(f"  Exception str: '{str(e)}'")
        print(f"  Exception repr: {repr(e)}")
        print(f"  Items synced before error: {sync_status.get('items_synced', 'unknown')}")

        sync_status["last_sync_status"] = "error"
        # Ensure we don't just get the truncated version
        full_error_msg = f"{error_details} | Args: {e.args} | Type: {type(e).__name__}"
        sync_status["last_sync_message"] = full_error_msg[:200]  # Increase limit to capture more detail

        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass

    finally:
        sync_status["is_running"] = False
        print(f"SYNC COMPLETED: Status: {sync_status['last_sync_status']}, Items: {sync_status['items_synced']}")
        print(f"SYNC COMPLETED: Products: {sync_status.get('products_synced', 0)}, Return Items: {sync_status.get('return_items_synced', 0)}, Orders: {sync_status.get('orders_synced', 0)}")

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
            placeholder = get_param_placeholder()
            cursor.execute(f"SELECT name as client_name FROM clients WHERE CAST(id AS NVARCHAR(50)) = {placeholder}", (client_id,))
            result = cursor.fetchone()
            if result:
                client_name = result[0]

        # Get statistics
        where_clause = "WHERE 1=1"
        params = []
        if client_id:
            placeholder = get_param_placeholder()
            where_clause += f" AND r.client_id = {placeholder}"
            params.append(client_id)

        # Total returns
        cursor.execute(f"SELECT COUNT(*) as count FROM returns r {where_clause}", params)
        row = cursor.fetchone()
        total_returns = row['count'] if row else 0

        # Processed returns
        cursor.execute(f"SELECT COUNT(*) as count FROM returns r {where_clause} AND r.processed = 1", params)
        row = cursor.fetchone()
        processed_returns = row['count'] if row else 0

        # Pending returns
        pending_returns = total_returns - processed_returns

        # Total items
        cursor.execute(f"""
            SELECT COUNT(ri.id)
            FROM return_items ri
            JOIN returns r ON CAST(ri.return_id AS NVARCHAR(50)) = CAST(r.id AS NVARCHAR(50))
            {where_clause}
        """, params)
        row = cursor.fetchone()
        total_items = row[0] if row else 0

        # Top return reason
        cursor.execute(f"""
            SELECT ri.return_reasons, COUNT(*) as count
            FROM return_items ri
            JOIN returns r ON CAST(ri.return_id AS NVARCHAR(50)) = CAST(r.id AS NVARCHAR(50))
            {where_clause} AND ri.return_reasons IS NOT NULL
            GROUP BY ri.return_reasons
            ORDER BY count DESC
            {format_limit_clause(1)}
        """, params)
        result = cursor.fetchone()
        top_reason = result['return_reasons'] if result else "N/A"

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
            placeholder = get_param_placeholder()
            cursor.execute(f"""
                INSERT INTO email_history (client_id, client_name, recipient_email, subject, attachment_name, sent_by, status)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, ensure_tuple_params((
                client_id,
                client_name,
                recipient_email,
                msg['Subject'],
                template_vars["attachment_name"],
                'System',
                'sent'
            )))
            conn.commit()

            status = "sent"
            message = "Email sent successfully!"
        else:
            # Save to email history as draft since SMTP not configured
            placeholder = get_param_placeholder()
            cursor.execute(f"""
                INSERT INTO email_history (client_id, client_name, recipient_email, subject, attachment_name, sent_by, status)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, ensure_tuple_params((
                client_id,
                client_name,
                recipient_email,
                msg['Subject'],
                template_vars["attachment_name"],
                'System',
                'draft'
            )))
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
        placeholder = get_param_placeholder()
        query += f" AND client_id = {placeholder}"
        params.append(client_id)

    query += " ORDER BY sent_date DESC"

    cursor.execute(query, ensure_tuple_params(params))
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

    # Convert to array of objects for frontend compatibility
    settings = []
    for row in settings_rows:
        try:
            # Try to parse as JSON for complex values
            value = json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            # If not JSON, use as string
            value = row['value']

        settings.append({
            'key': row['key'],
            'value': value
        })

    # Add current EMAIL_CONFIG if available
    if EMAIL_CONFIG:
        email_settings = [
            {'key': 'smtp_server', 'value': EMAIL_CONFIG.get('SMTP_SERVER', '')},
            {'key': 'smtp_port', 'value': EMAIL_CONFIG.get('SMTP_PORT', 587)},
            {'key': 'use_tls', 'value': EMAIL_CONFIG.get('USE_TLS', True)},
            {'key': 'auth_email', 'value': EMAIL_CONFIG.get('AUTH_EMAIL', '')},
            {'key': 'sender_email', 'value': EMAIL_CONFIG.get('SENDER_EMAIL', '')},
            {'key': 'sender_name', 'value': EMAIL_CONFIG.get('SENDER_NAME', '')}
        ]
        settings.extend(email_settings)

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
            placeholder = get_param_placeholder()
            cursor.execute(f"SELECT COUNT(*) as count FROM settings WHERE [key] = {placeholder}", (key,))
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
                placeholder = get_param_placeholder()
                cursor.execute(f"""
                    INSERT INTO settings ([key], value, updated_at)
                    VALUES ({placeholder}, {placeholder}, {placeholder})
                """, ensure_tuple_params((key, value_str, datetime.now().isoformat())))
        else:
            placeholder = get_param_placeholder()
            cursor.execute(f"""
                INSERT INTO settings (key, value, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder})
            """, ensure_tuple_params((key, value_str, datetime.now().isoformat())))

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

@app.get("/api/logs/sync")
async def get_sync_logs():
    """Get recent sync activity logs"""
    return {
        "status": "success",
        "log_count": len(sync_log_buffer),
        "logs": sync_log_buffer[-100:],  # Get last 100 entries
        "sync_status": sync_status
    }

@app.get("/api/logs/recent")
async def get_recent_logs(lines: int = 100):
    """Get recent application logs from Azure App Service"""
    try:
        import subprocess
        import os

        log_lines = []

        # Try to read from Azure's log directory
        log_paths = [
            "/home/LogFiles/Application/",
            "/var/log/",
            "/tmp/",
            "/home/site/wwwroot/logs/",
        ]

        for log_path in log_paths:
            if os.path.exists(log_path):
                try:
                    # Get all log files in the directory
                    for root, dirs, files in os.walk(log_path):
                        for file in files:
                            if file.endswith('.log') or file.endswith('.txt'):
                                full_path = os.path.join(root, file)
                                try:
                                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        log_lines.extend([
                                            f"=== {full_path} ===",
                                            content[-5000:] if len(content) > 5000 else content  # Last 5KB
                                        ])
                                except Exception as e:
                                    log_lines.append(f"Error reading {full_path}: {e}")
                except Exception as e:
                    log_lines.append(f"Error accessing {log_path}: {e}")

        # Also try to capture recent stdout/stderr if possible
        try:
            # Try to read from Docker logs or systemd logs
            result = subprocess.run(['tail', '-n', str(lines), '/var/log/syslog'],
                                  capture_output=True, text=True, timeout=5)
            if result.stdout:
                log_lines.extend(["=== System Logs ===", result.stdout])
        except Exception as e:
            log_lines.append(f"System log access failed: {e}")

        return {
            "status": "success",
            "logs": log_lines,
            "log_paths_checked": log_paths,
            "environment": {
                "platform": os.name,
                "cwd": os.getcwd(),
                "env_vars": {k: v for k, v in os.environ.items() if 'WEBSITE' in k or 'AZURE' in k}
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Could not access logs"
        }

@app.get("/api/deployment/version")
async def get_deployment_version():
    """Simple endpoint to verify deployment version"""
    import datetime
    return {
        "version": "2025-01-15-ORDER-ITEMS-ENHANCEMENT-V42",
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
            cursor.execute("SELECT SUSER_NAME() as user_name")
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

        # Migration commands to change INT to BIGINT
        migration_commands = [
            "ALTER TABLE clients ALTER COLUMN id BIGINT",
            "ALTER TABLE warehouses ALTER COLUMN id BIGINT",
            "ALTER TABLE orders ALTER COLUMN id BIGINT",
            "ALTER TABLE returns ALTER COLUMN id BIGINT",
            "ALTER TABLE returns ALTER COLUMN client_id BIGINT",
            "ALTER TABLE returns ALTER COLUMN warehouse_id BIGINT",
            "ALTER TABLE returns ALTER COLUMN order_id BIGINT",
            "ALTER TABLE return_items ALTER COLUMN return_id BIGINT",
            "ALTER TABLE email_history ALTER COLUMN client_id BIGINT",
            "ALTER TABLE email_share_items ALTER COLUMN return_id BIGINT",
            # CRITICAL: Fix product ID overflow issues
            "ALTER TABLE products ALTER COLUMN id BIGINT",
            "ALTER TABLE return_items ALTER COLUMN product_id BIGINT"
        ]

        # CURSOR PERFORMANCE FIX: Execute all migrations then batch commit
        migration_success = True
        for cmd in migration_commands:
            try:
                cursor.execute(cmd)
                migrations.append({"command": cmd, "status": "success"})
            except Exception as e:
                migrations.append({"command": cmd, "status": "error", "error": str(e)})
                migration_success = False

        # Batch commit all successful migrations at once
        if migration_success:
            conn.commit()
            print("🚀 PERFORMANCE: All BIGINT migrations committed in batch")

        conn.close()

        return {
            "status": "success",
            "migrations": migrations,
            "message": f"Completed {len([m for m in migrations if m['status'] == 'success'])} migrations"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/database/migrate-bigint")
async def migrate_to_bigint_get():
    """GET version of BIGINT migration for browser testing"""
    return await migrate_to_bigint()

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





# Email Share Endpoints
@app.post("/api/email-shares/create")
async def create_email_share(request: Request):
    """Create a new email share record"""
    try:
        # Parse request body
        data = await request.json()
        client_id = data.get('client_id')
        date_range_start = data.get('date_range_start')
        date_range_end = data.get('date_range_end')
        recipient_email = data.get('recipient_email')
        subject = data.get('subject')
        notes = data.get('notes')
        return_ids = data.get('return_ids')

        if not all([client_id, date_range_start, date_range_end, recipient_email]):
            return {"error": "Missing required fields: client_id, date_range_start, date_range_end, recipient_email"}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query to get returns to share
        placeholder = get_param_placeholder()
        query = f"""
            SELECT r.id, r.created_at
            FROM returns r
            WHERE r.client_id = {placeholder}
            AND CAST(r.created_at AS DATE) >= {placeholder}
            AND CAST(r.created_at AS DATE) <= {placeholder}
        """
        params = [client_id, date_range_start, date_range_end]

        # If specific return IDs provided, filter by those
        if return_ids and len(return_ids) > 0:
            placeholders = ','.join([placeholder] * len(return_ids))
            query += f" AND r.id IN ({placeholders})"
            params.extend(return_ids)

        # Exclude already shared returns
        query += f"""
            AND r.id NOT IN (
                SELECT DISTINCT esi.return_id
                FROM email_share_items esi
                JOIN email_shares es ON esi.email_share_id = es.id
                WHERE es.client_id = {placeholder}
                AND es.share_status = 'sent'
            )
        """
        params.append(client_id)

        cursor.execute(query, params)
        returns_to_share = cursor.fetchall()

        if USE_AZURE_SQL:
            returns_to_share = rows_to_dict(cursor, returns_to_share)

        if not returns_to_share:
            conn.close()
            return {"error": "No unshared returns found for the specified criteria"}

        # Create email share record
        placeholder = get_param_placeholder()
        cursor.execute(f"""
            INSERT INTO email_shares (client_id, date_range_start, date_range_end, recipient_email, subject, total_returns_shared, share_status, notes, created_by, created_at)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """, ensure_tuple_params((
            client_id,
            date_range_start,
            date_range_end,
            recipient_email,
            subject or f"Returns Report - {date_range_start} to {date_range_end}",
            len(returns_to_share),
            "pending",
            notes,
            "system",
            datetime.now().isoformat()
        )))

        # Get the email share ID
        if USE_AZURE_SQL:
            cursor.execute("SELECT @@IDENTITY as id")
            email_share_id = cursor.fetchone()['id']
        else:
            email_share_id = cursor.lastrowid

        # Add share items
        for return_obj in returns_to_share:
            return_id = return_obj['id'] if USE_AZURE_SQL else return_obj[0]
            placeholder = get_param_placeholder()
            cursor.execute(f"""
                INSERT INTO email_share_items (email_share_id, return_id, created_at)
                VALUES ({placeholder}, {placeholder}, {placeholder})
            """, ensure_tuple_params((
                email_share_id,
                return_id,
                datetime.now().isoformat()
            )))

        conn.commit()
        conn.close()

        return {
            "id": email_share_id,
            "client_id": client_id,
            "total_returns_shared": len(returns_to_share),
            "recipient_email": recipient_email,
            "status": "pending"
        }

    except Exception as e:
        print(f"Error creating email share: {e}")
        return {"error": str(e)}


@app.get("/api/email-shares/history")
async def get_email_share_history(client_id: Optional[int] = None, limit: int = 50):
    """Get email share history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query
        placeholder = get_param_placeholder()
        query = f"""
            SELECT es.id, es.client_id, c.name as client_name, es.date_range_start, es.date_range_end,
                   es.recipient_email, es.subject, es.total_returns_shared, es.share_status,
                   es.sent_at, es.created_at, es.notes
            FROM email_shares es
            LEFT JOIN clients c ON es.client_id = c.id
            WHERE 1=1
        """
        params = []

        if client_id:
            query += f" AND es.client_id = {placeholder}"
            params.append(client_id)

        query += f" ORDER BY es.created_at DESC LIMIT {placeholder}"
        params.append(limit)

        cursor.execute(query, params)
        shares = cursor.fetchall()

        if USE_AZURE_SQL:
            shares = rows_to_dict(cursor, shares)

        result = []
        for share in shares:
            if USE_AZURE_SQL:
                result.append({
                    "id": share['id'],
                    "client_id": share['client_id'],
                    "client_name": share['client_name'],
                    "date_range_start": share['date_range_start'].isoformat() if share['date_range_start'] else None,
                    "date_range_end": share['date_range_end'].isoformat() if share['date_range_end'] else None,
                    "recipient_email": share['recipient_email'],
                    "subject": share['subject'],
                    "total_returns_shared": share['total_returns_shared'],
                    "share_status": share['share_status'],
                    "sent_at": share['sent_at'].isoformat() if share['sent_at'] else None,
                    "created_at": share['created_at'].isoformat() if share['created_at'] else None,
                    "notes": share['notes']
                })
        else:
                result.append({
                    "id": share[0],
                    "client_id": share[1],
                    "client_name": share[2],
                    "date_range_start": share[3],
                    "date_range_end": share[4],
                    "recipient_email": share[5],
                    "subject": share[6],
                    "total_returns_shared": share[7],
                    "share_status": share[8],
                    "sent_at": share[9],
                    "created_at": share[10],
                    "notes": share[11]
                })

        conn.close()
        return result

    except Exception as e:
        print(f"Error getting email share history: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    # Use Azure's PORT environment variable if available
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8015)))
    uvicorn.run(app, host="0.0.0.0", port=port)