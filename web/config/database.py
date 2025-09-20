# Azure SQL Database connection (clean, no SQLite complexity)
import pyodbc
import os
from typing import Optional

# Use the same DATABASE_URL environment variable as the old app
DATABASE_URL = os.getenv('DATABASE_URL', '')

def get_connection_string() -> str:
    """Get Azure SQL connection string from DATABASE_URL environment variable"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    # DATABASE_URL is already a complete connection string from Azure
    return DATABASE_URL

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