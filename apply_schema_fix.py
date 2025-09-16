#!/usr/bin/env python3
"""
SQLite Schema Fix Script
This script applies the BIGINT data type fixes to the SQLite database
"""

import sqlite3
import os
import shutil
from datetime import datetime

def backup_database(db_path):
    """Create a backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path.replace('.db', '')}_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path

def apply_schema_fix(db_path):
    """Apply the schema fix to convert INTEGER to BIGINT"""
    
    # Read the schema fix script
    with open('database/alter_schema_sqlite_bigint_fix.sql', 'r') as f:
        schema_sql = f.read()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🔄 Applying schema fix...")
        
        # Execute the schema fix script
        cursor.executescript(schema_sql)
        
        # Verify the changes
        print("\n🔍 Verifying schema changes...")
        
        # Check key tables
        tables_to_check = [
            ('clients', 'id'),
            ('products', 'id'), 
            ('returns', 'id'),
            ('return_items', 'return_id'),
            ('return_items', 'product_id'),
            ('orders', 'id'),
            ('email_shares', 'client_id'),
            ('email_share_items', 'return_id')
        ]
        
        for table, column in tables_to_check:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                for col in columns:
                    if col[1] == column:  # col[1] is column name
                        data_type = col[2]  # col[2] is data type
                        status = "✅" if data_type.upper() == "BIGINT" else "❌"
                        print(f"  {status} {table}.{column}: {data_type}")
                        break
            except Exception as e:
                print(f"  ❌ Error checking {table}.{column}: {e}")
        
        conn.commit()
        print("\n✅ Schema fix applied successfully!")
        
    except Exception as e:
        print(f"❌ Error applying schema fix: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    db_path = "warehance_returns.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    print(f"🔄 Starting schema fix for: {db_path}")
    
    # Create backup
    backup_path = backup_database(db_path)
    
    # Apply schema fix
    apply_schema_fix(db_path)
    
    print(f"\n🎉 Schema fix completed!")
    print(f"📁 Original database: {db_path}")
    print(f"💾 Backup created: {backup_path}")
    print(f"\n📋 Summary of changes:")
    print(f"   • All ID fields converted from INTEGER to BIGINT")
    print(f"   • Prevents overflow issues with large API IDs")
    print(f"   • Matches Azure SQL schema data types")

if __name__ == "__main__":
    main()
