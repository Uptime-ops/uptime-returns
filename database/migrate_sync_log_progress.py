#!/usr/bin/env python3
"""
Database migration script to add real-time progress tracking columns to SyncLog table.
This script adds the new columns needed for real-time sync progress tracking.
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import engine, SessionLocal, SyncLog
from sqlalchemy import text

def migrate_sqlite():
    """Migrate SQLite database to add new SyncLog columns"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'warehance_returns.db')
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(sync_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = [
            ('current_phase', 'TEXT'),
            ('total_to_process', 'INTEGER'),
            ('processed_count', 'INTEGER'),
            ('last_progress_update', 'TIMESTAMP'),
            ('current_operation', 'TEXT')
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                print(f"Adding column: {column_name}")
                cursor.execute(f"ALTER TABLE sync_logs ADD COLUMN {column_name} {column_def}")
            else:
                print(f"Column {column_name} already exists, skipping")
        
        conn.commit()
        conn.close()
        
        print("SQLite migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error migrating SQLite database: {e}")
        return False

def migrate_azure_sql():
    """Migrate Azure SQL database to add new SyncLog columns"""
    try:
        db = SessionLocal()
        
        # Check if columns already exist by trying to query them
        try:
            db.execute(text("SELECT current_phase FROM sync_logs LIMIT 1"))
            print("Azure SQL columns already exist, skipping migration")
            return True
        except:
            pass  # Columns don't exist, proceed with migration
        
        # Add new columns
        new_columns = [
            "ALTER TABLE sync_logs ADD current_phase VARCHAR(100) DEFAULT 'initializing'",
            "ALTER TABLE sync_logs ADD total_to_process INTEGER DEFAULT 0",
            "ALTER TABLE sync_logs ADD processed_count INTEGER DEFAULT 0", 
            "ALTER TABLE sync_logs ADD last_progress_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE sync_logs ADD current_operation VARCHAR(500)"
        ]
        
        for sql in new_columns:
            print(f"Executing: {sql}")
            db.execute(text(sql))
        
        db.commit()
        db.close()
        
        print("Azure SQL migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error migrating Azure SQL database: {e}")
        return False

def main():
    """Main migration function"""
    print("Starting SyncLog progress tracking migration...")
    print(f"Timestamp: {datetime.now()}")
    
    # Check if we're using Azure SQL or SQLite
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and 'sqlserver' in database_url.lower():
        print("Detected Azure SQL database")
        success = migrate_azure_sql()
    else:
        print("Detected SQLite database")
        success = migrate_sqlite()
    
    if success:
        print("Migration completed successfully!")
        print("New SyncLog columns added:")
        print("- current_phase: Current sync phase (initializing, fetching, processing, completed)")
        print("- total_to_process: Total number of items to process")
        print("- processed_count: Number of items processed so far")
        print("- last_progress_update: Timestamp of last progress update")
        print("- current_operation: Description of current operation")
    else:
        print("Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
