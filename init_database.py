"""
Initialize SQLite database for Warehance Returns
No installation required - SQLite comes with Python!
"""

import sqlite3
import os
from pathlib import Path

def init_database():
    """Initialize the SQLite database with schema"""
    
    # Database file path
    db_path = "warehance_returns.db"
    
    # Schema file path
    schema_path = Path("database/schema_sqlite.sql")
    
    print("=" * 50)
    print("Initializing SQLite Database")
    print("=" * 50)
    
    try:
        # Connect to SQLite database (creates file if doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Read and execute schema
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute all SQL statements
        cursor.executescript(schema_sql)
        
        # Commit changes
        conn.commit()
        
        print(f"[SUCCESS] Database created successfully: {db_path}")
        print(f"[SUCCESS] Schema applied from: {schema_path}")
        
        # Show created tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        print("\nTables created:")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.close()
        
        print("\n[SUCCESS] Database is ready to use!")
        print("\nNext steps:")
        print("1. Run: python scripts/sync_returns.py")
        print("2. Run: python web/app.py")
        print("3. Visit: http://localhost:8000")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
        return False

if __name__ == "__main__":
    init_database()