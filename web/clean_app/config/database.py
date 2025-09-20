# Azure SQL Database connection (clean, no SQLite complexity)
import pyodbc
import os
from typing import Optional

# Azure SQL Connection Configuration
AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "uptime-returns-sql.database.windows.net")
AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "uptime-returns")
AZURE_SQL_USERNAME = os.getenv("AZURE_SQL_USERNAME", "uptime-admin")
AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD", "")

def get_connection_string() -> str:
    """Get Azure SQL connection string"""
    return (
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server=tcp:{AZURE_SQL_SERVER},1433;"
        f"Database={AZURE_SQL_DATABASE};"
        f"Uid={AZURE_SQL_USERNAME};"
        f"Pwd={AZURE_SQL_PASSWORD};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )

def get_db_connection():
    """Get database connection (Azure SQL only)"""
    try:
        connection_string = get_connection_string()
        conn = pyodbc.connect(connection_string)
        print("Azure SQL connection established")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

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