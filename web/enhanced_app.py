"""
Enhanced FastAPI app with product details and CSV export
"""
import sys
import os
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
WAREHANCE_API_KEY = os.getenv('WAREHANCE_API_KEY', 'WH_0e088e8c-dc84-421e-85c7-6db74a3b8afa')
if not WAREHANCE_API_KEY:
    WAREHANCE_API_KEY = 'WH_0e088e8c-dc84-421e-85c7-6db74a3b8afa'  # Fallback for local testing

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_AZURE_SQL = bool(DATABASE_URL and ('database.windows.net' in DATABASE_URL or 'database.azure.com' in DATABASE_URL))

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
        """Get Azure SQL connection with fallback"""
        if pyodbc:
            # Parse the DATABASE_URL to ensure it has the right format
            import re
            
            # Extract components from the connection string
            conn_str = DATABASE_URL
            
            # Try different connection string formats
            if 'Driver=' not in conn_str and 'DRIVER=' not in conn_str:
                # Check what drivers are available
                available_drivers = pyodbc.drivers()
                print(f"Detected ODBC drivers via pyodbc: {available_drivers}")
                
                # Try multiple drivers in order of likelihood
                # Include some variations that might work on Azure Linux
                drivers = [
                    'ODBC Driver 17 for SQL Server',
                    'ODBC Driver 18 for SQL Server',
                    '/opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17.10.so.6.1',  # Direct .so path
                    '/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.3.so.2.1',   # Direct .so path
                    'SQL Server Native Client 11.0',
                    'SQL Server',
                    'FreeTDS',
                    'ODBC Driver 13 for SQL Server',
                    'libmsodbcsql-17.so',  # Short .so name
                    'libmsodbcsql-18.so'   # Short .so name
                ]
                
                # If we detected drivers, prioritize those
                if available_drivers:
                    drivers = available_drivers + drivers
                
                for driver in drivers:
                    try:
                        test_conn_str = f"DRIVER={{{driver}}};{conn_str}"
                        if 'TrustServerCertificate=' not in test_conn_str:
                            test_conn_str += ';TrustServerCertificate=yes'
                        
                        print(f"Attempting connection with driver: {driver}")
                        conn = pyodbc.connect(test_conn_str)
                        print(f"SUCCESS: Connected with {driver}")
                        
                        # Configure encoding
                        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
                        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
                        conn.setencoding(encoding='utf-8')
                        return conn
                    except Exception as e:
                        error_msg = str(e)[:200]
                        print(f"Failed with {driver}: {error_msg}")
                        continue
                
                # If no driver worked, show diagnostic info
                import subprocess
                try:
                    odbcinst_output = subprocess.run(['odbcinst', '-q', '-d'], capture_output=True, text=True, timeout=5)
                    print(f"odbcinst drivers: {odbcinst_output.stdout}")
                except:
                    print("Could not run odbcinst command")
                
                print(f"ERROR: No driver worked. pyodbc.drivers() returned: {available_drivers}")
                raise Exception(f"Could not connect to Azure SQL. Available drivers: {available_drivers}")
            else:
                # Connection string already has a driver
                conn = pyodbc.connect(conn_str)
                conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
                conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
                conn.setencoding(encoding='utf-8')
                return conn
        elif pymssql:
            # Fallback to pymssql if pyodbc is not available
            print("Using pymssql as fallback for Azure SQL")
            
            # Parse DATABASE_URL for pymssql
            import re
            # Extract components from connection string
            # Expected format: Server=xxx.database.windows.net;Database=xxx;User ID=xxx;Password=xxx
            pattern = r'Server=([^;]+);.*Database=([^;]+);.*User ID=([^;]+);.*Password=([^;]+)'
            match = re.search(pattern, DATABASE_URL)
            
            if match:
                server = match.group(1)
                database = match.group(2)
                username = match.group(3)
                password = match.group(4)
                
                # Connect using pymssql
                conn = pymssql.connect(
                    server=server,
                    user=username,
                    password=password,
                    database=database,
                    as_dict=True,
                    tds_version='7.4'
                )
                return conn
            else:
                raise Exception("Could not parse DATABASE_URL for pymssql")
        else:
            raise Exception("Neither pyodbc nor pymssql installed - needed for Azure SQL")
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
    return FileResponse("templates/index.html")

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
        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id NOT IN (SELECT return_id FROM email_share_items)")
        row = cursor.fetchone()
        stats['unshared_returns'] = row[0] if row else 0
        
        # Get last sync time
        cursor.execute("SELECT MAX(completed_at) as last_sync FROM sync_logs WHERE status = 'completed'")
        row = cursor.fetchone()
        stats['last_sync'] = row[0] if row else None
        
        # Get product statistics
        cursor.execute("SELECT COUNT(*) as count FROM products")
        row = cursor.fetchone()
        stats['total_products'] = row[0] if row else 0
        
        cursor.execute("SELECT COUNT(*) as count FROM return_items")
        row = cursor.fetchone()
        stats['total_return_items'] = row[0] if row else 0
        
        cursor.execute("SELECT SUM(quantity) as total FROM return_items")
        row = cursor.fetchone()
        stats['total_returned_quantity'] = row[0] if row else 0
    
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
    row = cursor.fetchone()
    total = row[0] if row else 0
    
    # Add pagination
    query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
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
                WHERE ri.return_id = ?
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
        WHERE r.id = ?
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
        WHERE ri.return_id = ?
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
                WHERE o.id = ?
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
                   COALESCE(p.name, 'Unknown Product') as name, ri.quantity,
                   ri.return_reasons, ri.condition_on_arrival
            FROM return_items ri
            LEFT JOIN products p ON ri.product_id = p.id
            WHERE ri.return_id = ?
        """, (return_id,))
        items = cursor.fetchall()
        
        # Convert items to dict for Azure SQL
        if USE_AZURE_SQL:
            items = rows_to_dict(cursor, items) if items else []
        
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
                    item['quantity'] or 0,  # Order Qty (using return qty as placeholder)
                    item['quantity'] or 0,  # Return Qty
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
    
    cursor.execute("""
        SELECT return_reasons, COUNT(*) as count
        FROM return_items
        WHERE return_reasons IS NOT NULL AND return_reasons != '[]'
        GROUP BY return_reasons
        ORDER BY count DESC
        LIMIT 20
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
    
    cursor.execute("""
        SELECT p.sku, p.name, SUM(ri.quantity) as total_quantity, COUNT(ri.id) as return_count
        FROM return_items ri
        JOIN products p ON ri.product_id = p.id
        GROUP BY p.id
        ORDER BY total_quantity DESC
        LIMIT 10
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
async def trigger_sync(request_data: dict):
    """Trigger a sync with Warehance API"""
    global sync_status
    
    if sync_status["is_running"]:
        return {"message": "Sync already in progress", "status": "running"}
    
    # Start sync in background
    asyncio.create_task(run_sync())
    
    return {"message": "Sync started", "status": "started"}

@app.get("/api/sync/status")
async def get_sync_status():
    """Get current sync status"""
    global sync_status
    
    try:
        # Get last sync from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(last_synced_at) as last_sync
            FROM returns
            WHERE last_synced_at IS NOT NULL
        """)
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
            "last_sync_message": sync_status["last_sync_message"]
        }
    except Exception as e:
        print(f"Error in sync status: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return {
            "current_sync": {"status": "error", "items_synced": 0},
            "last_sync": None,
            "last_sync_status": "error",
            "last_sync_message": str(e)
        }

async def run_sync():
    """Run the actual sync process"""
    global sync_status
    
    sync_status["is_running"] = True
    sync_status["items_synced"] = 0
    
    try:
        headers = {
            "X-API-KEY": "WH_237eb441_547781417ad5a2dc895ba0915deaf48cb963c1660e2324b3fb25df5bd4df65f1",
            "accept": "application/json"
        }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # STEP 1: Fetch ALL returns from API with pagination
        sync_status["last_sync_message"] = "Fetching returns..."
        all_order_ids = set()  # Collect unique order IDs
        offset = 0
        limit = 100
        total_fetched = 0
        
        while True:
            response = requests.get(f"https://api.warehance.com/v1/returns?limit={limit}&offset={offset}", headers=headers)
            data = response.json()
            
            if 'data' not in data or 'returns' not in data['data']:
                break
                
            returns_batch = data['data']['returns']
            if not returns_batch:
                break
                
            for ret in returns_batch:
                # Collect order ID if present
                if ret.get('order') and ret['order'].get('id'):
                    all_order_ids.add(ret['order']['id'])
                
                # Update or insert return
                cursor.execute("""
                    INSERT OR REPLACE INTO returns (
                        id, api_id, paid_by, status, created_at, updated_at,
                        processed, processed_at, warehouse_note, customer_note,
                        tracking_number, tracking_url, carrier, service,
                        label_cost, label_pdf_url, rma_slip_url, label_voided,
                        client_id, warehouse_id, order_id, return_integration_id,
                        last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ret['id'], ret.get('api_id'), ret.get('paid_by', ''),
                    ret.get('status', ''), ret.get('created_at'), ret.get('updated_at'),
                    ret.get('processed', False), ret.get('processed_at'),
                    ret.get('warehouse_note', ''), ret.get('customer_note', ''),
                    ret.get('tracking_number'), ret.get('tracking_url'),
                    ret.get('carrier', ''), ret.get('service', ''),
                    ret.get('label_cost'), ret.get('label_pdf_url'),
                    ret.get('rma_slip_url'), ret.get('label_voided', False),
                    ret['client']['id'] if ret.get('client') else None,
                    ret['warehouse']['id'] if ret.get('warehouse') else None,
                    ret['order']['id'] if ret.get('order') else None,
                    ret.get('return_integration_id'),
                    datetime.now().isoformat()
                ))
                
                # Also store basic order info from return data
                if ret.get('order'):
                    order = ret['order']
                    cursor.execute("""
                        INSERT OR IGNORE INTO orders (id, order_number, created_at, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (order['id'], order.get('order_number', '')))
                
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
                            cursor.execute("SELECT id FROM products WHERE sku = ?", (product_sku,))
                            existing = cursor.fetchone()
                            if existing:
                                product_id = existing[0]
                            else:
                                # Create a placeholder product
                                cursor.execute("""
                                    INSERT INTO products (sku, name, created_at, updated_at)
                                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (product_sku, product_name or 'Unknown Product'))
                                product_id = cursor.lastrowid
                        elif product_id > 0:
                            # Ensure product exists
                            cursor.execute("""
                                INSERT OR IGNORE INTO products (id, sku, name, created_at, updated_at)
                                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """, (product_id, product_sku, product_name))
                        
                        # Store return item
                        import json
                        cursor.execute("""
                            INSERT OR REPLACE INTO return_items (
                                id, return_id, product_id, quantity,
                                return_reasons, condition_on_arrival,
                                quantity_received, quantity_rejected,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (
                            item.get('id'),
                            ret['id'],
                            product_id if product_id > 0 else None,
                            item.get('quantity', 0),
                            json.dumps(item.get('return_reasons', [])),
                            json.dumps(item.get('condition_on_arrival', [])),
                            item.get('quantity_received', 0),
                            item.get('quantity_rejected', 0)
                        ))
                
                sync_status["items_synced"] += 1
            
            total_fetched += len(returns_batch)
            
            # Check if we've fetched all returns
            total_count = data['data'].get('total_count', 0)
            if total_fetched >= total_count or len(returns_batch) < limit:
                break
                
            offset += limit
            
            # Add a small delay to avoid overwhelming the API
            await asyncio.sleep(0.5)
        
        conn.commit()
        
        # STEP 2: Fetch full order details for all collected order IDs (with customer names)
        sync_status["last_sync_message"] = f"Fetching {len(all_order_ids)} orders with customer info..."
        
        # Check which orders need customer name updates
        cursor.execute("""
            SELECT id FROM orders 
            WHERE id IN ({}) 
            AND (customer_name IS NULL OR customer_name = '')
        """.format(','.join('?' * len(all_order_ids))), list(all_order_ids))
        
        orders_needing_update = [row[0] for row in cursor.fetchall()]
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
                            SET customer_name = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (customer_name, order_id))
                        
                        if customer_name:
                            customers_updated += 1
                    
                    # Small delay between API calls
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error fetching order {order_id}: {e}")
            
            # Update progress
            sync_status["last_sync_message"] = f"Fetched {i+len(batch)} of {min(len(orders_needing_update), 500)} orders..."
        
        conn.commit()
        conn.close()
        
        sync_status["last_sync_status"] = "success"
        sync_status["last_sync_message"] = f"Synced {sync_status['items_synced']} returns, updated {customers_updated} customer names"
        sync_status["last_sync"] = datetime.now().isoformat()
            
    except Exception as e:
        sync_status["last_sync_status"] = "error"
        sync_status["last_sync_message"] = f"Sync failed: {str(e)}"
    
    finally:
        sync_status["is_running"] = False

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
            cursor.execute("SELECT name FROM clients WHERE id = ?", (client_id,))
            result = cursor.fetchone()
            if result:
                client_name = result[0]
        
        # Get statistics
        where_clause = "WHERE 1=1"
        params = []
        if client_id:
            where_clause += " AND r.client_id = ?"
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
            LIMIT 1
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
        query += " AND client_id = ?"
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
    return FileResponse('templates/settings.html')

@app.get("/api/settings")
async def get_settings():
    """Get all system settings"""
    conn = get_db_connection()
    if not USE_AZURE_SQL:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create settings table if it doesn't exist
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
        
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
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

if __name__ == "__main__":
    import uvicorn
    # Use Azure's PORT environment variable if available
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8015)))
    uvicorn.run(app, host="0.0.0.0", port=port)