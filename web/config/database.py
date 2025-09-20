# Azure SQL Database connection (clean, no SQLite complexity)
import pyodbc
import os
from typing import Optional

# Try pymssql as fallback for Azure SQL (same as old app)
try:
    import pymssql
    print("pymssql imported successfully")
except ImportError:
    pymssql = None
    print("pymssql not available")

# Use the same DATABASE_URL environment variable as the old app
DATABASE_URL = os.getenv('DATABASE_URL', '')

def get_connection_string() -> str:
    """Get Azure SQL connection string from DATABASE_URL environment variable"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    # DATABASE_URL is already a complete connection string from Azure
    return DATABASE_URL

def get_db_connection():
    """Get database connection with pymssql fallback (same as old app)"""

    # List available ODBC drivers for diagnostics
    try:
        available_drivers = pyodbc.drivers()
        print(f"Available ODBC drivers: {available_drivers}")
    except Exception as e:
        print(f"ERROR listing drivers: {e}")

    # First try pymssql as it's simpler and doesn't need ODBC drivers
    if pymssql:
        try:
            print("Attempting pymssql connection...")
            # Parse DATABASE_URL - same parsing logic as old app
            conn_params = {}
            for part in DATABASE_URL.split(';'):
                if '=' in part:
                    key, value = part.split('=', 1)
                    conn_params[key.strip().upper()] = value.strip()

            # Extract connection parameters
            server = conn_params.get('SERVER', '').replace('tcp:', '').replace(',1433', '')
            database = conn_params.get('DATABASE', '') or conn_params.get('INITIAL CATALOG', '') or 'uptime-returns-db'
            user = conn_params.get('UID', '') or conn_params.get('USER ID', '')
            password = conn_params.get('PWD', '') or conn_params.get('PASSWORD', '')

            print(f"pymssql connecting to server: {server}, database: {database}")

            conn = pymssql.connect(
                server=server,
                user=user,
                password=password,
                database=database,
                timeout=30,
                login_timeout=30
            )
            print("pymssql connection successful!")
            return conn

        except Exception as pymssql_error:
            print(f"pymssql connection failed: {pymssql_error}")

    # Fallback to pyodbc (original method)
    try:
        print("Attempting pyodbc connection...")
        connection_string = get_connection_string()
        conn = pyodbc.connect(connection_string)
        print("pyodbc connection successful!")
        return conn
    except Exception as e:
        print(f"pyodbc connection failed: {e}")
        raise Exception(f"Both pymssql and pyodbc connections failed. Last error: {e}")

def test_connection() -> bool:
    """Test database connectivity"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        conn.close()
        print(f"✅ Database test successful: {result}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

# SQL parameter placeholder (Azure SQL uses %s)
def get_placeholder() -> str:
    """Get SQL parameter placeholder for Azure SQL"""
    return "%s"

def format_in_clause(count: int) -> str:
    """Format IN clause with correct number of placeholders"""
    return ','.join([get_placeholder()] * count)

print("Database config loaded (Azure SQL only)")