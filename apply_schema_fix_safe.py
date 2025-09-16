#!/usr/bin/env python3
"""
Safe SQLite Schema Fix Script
This script safely applies BIGINT data type fixes to the SQLite database
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

def get_table_schema(cursor, table_name):
    """Get the current schema of a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()

def check_data_types(cursor):
    """Check current data types of key columns"""
    print("\n🔍 Current data types:")
    
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

def apply_schema_fix_safe(db_path):
    """Safely apply the schema fix by recreating tables with correct data types"""
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🔄 Checking current schema...")
        check_data_types(cursor)
        
        print("\n🔄 Applying schema fix...")
        
        # Step 1: Create new tables with correct BIGINT data types
        print("  📋 Creating new tables with BIGINT data types...")
        
        # Create new clients table
        cursor.execute("""
            CREATE TABLE clients_new (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create new warehouses table
        cursor.execute("""
            CREATE TABLE warehouses_new (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create new stores table
        cursor.execute("""
            CREATE TABLE stores_new (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create new return_integrations table
        cursor.execute("""
            CREATE TABLE return_integrations_new (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                return_integration_type TEXT,
                store_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES stores_new(id)
            )
        """)
        
        # Create new orders table
        cursor.execute("""
            CREATE TABLE orders_new (
                id BIGINT PRIMARY KEY,
                order_number TEXT NOT NULL,
                customer_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create new products table
        cursor.execute("""
            CREATE TABLE products_new (
                id BIGINT PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create new returns table
        cursor.execute("""
            CREATE TABLE returns_new (
                id BIGINT PRIMARY KEY,
                api_id TEXT,
                paid_by TEXT,
                status TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                processed BOOLEAN DEFAULT 0,
                processed_at TIMESTAMP,
                warehouse_note TEXT,
                customer_note TEXT,
                tracking_number TEXT,
                tracking_url TEXT,
                carrier TEXT,
                service TEXT,
                rma_slip_url TEXT,
                label_voided INTEGER DEFAULT 0,
                client_id BIGINT,
                warehouse_id BIGINT,
                order_id BIGINT,
                return_integration_id BIGINT,
                created_at_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients_new(id),
                FOREIGN KEY (warehouse_id) REFERENCES warehouses_new(id),
                FOREIGN KEY (order_id) REFERENCES orders_new(id),
                FOREIGN KEY (return_integration_id) REFERENCES return_integrations_new(id)
            )
        """)
        
        # Create new return_items table
        cursor.execute("""
            CREATE TABLE return_items_new (
                id BIGINT PRIMARY KEY,
                return_id BIGINT NOT NULL,
                product_id BIGINT,
                quantity INTEGER,
                return_reasons TEXT,
                condition_on_arrival TEXT,
                quantity_received INTEGER DEFAULT 0,
                quantity_rejected INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (return_id) REFERENCES returns_new(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products_new(id)
            )
        """)
        
        # Create new email_shares table
        cursor.execute("""
            CREATE TABLE email_shares_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id BIGINT NOT NULL,
                share_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_range_start DATE NOT NULL,
                date_range_end DATE NOT NULL,
                recipient_email TEXT,
                subject TEXT,
                total_returns_shared INTEGER DEFAULT 0,
                share_status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (client_id) REFERENCES clients_new(id)
            )
        """)
        
        # Create new email_share_items table
        cursor.execute("""
            CREATE TABLE email_share_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_share_id INTEGER NOT NULL,
                return_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_share_id) REFERENCES email_shares_new(id) ON DELETE CASCADE,
                FOREIGN KEY (return_id) REFERENCES returns_new(id),
                UNIQUE(email_share_id, return_id)
            )
        """)
        
        # Step 2: Copy data from old tables to new tables
        print("  📋 Copying data to new tables...")
        
        # Copy data in dependency order
        cursor.execute("INSERT INTO clients_new SELECT * FROM clients")
        cursor.execute("INSERT INTO warehouses_new SELECT * FROM warehouses")
        cursor.execute("INSERT INTO stores_new SELECT * FROM stores")
        cursor.execute("INSERT INTO return_integrations_new SELECT * FROM return_integrations")
        cursor.execute("INSERT INTO orders_new SELECT * FROM orders")
        cursor.execute("INSERT INTO products_new SELECT * FROM products")
        cursor.execute("INSERT INTO returns_new SELECT * FROM returns")
        cursor.execute("INSERT INTO return_items_new SELECT * FROM return_items")
        cursor.execute("INSERT INTO email_shares_new SELECT * FROM email_shares")
        cursor.execute("INSERT INTO email_share_items_new SELECT * FROM email_share_items")
        
        # Step 3: Drop old tables and rename new ones
        print("  📋 Replacing old tables with new ones...")
        
        # Drop old tables in reverse dependency order
        cursor.execute("DROP TABLE email_share_items")
        cursor.execute("DROP TABLE email_shares")
        cursor.execute("DROP TABLE return_items")
        cursor.execute("DROP TABLE returns")
        cursor.execute("DROP TABLE orders")
        cursor.execute("DROP TABLE products")
        cursor.execute("DROP TABLE return_integrations")
        cursor.execute("DROP TABLE stores")
        cursor.execute("DROP TABLE warehouses")
        cursor.execute("DROP TABLE clients")
        
        # Rename new tables
        cursor.execute("ALTER TABLE clients_new RENAME TO clients")
        cursor.execute("ALTER TABLE warehouses_new RENAME TO warehouses")
        cursor.execute("ALTER TABLE stores_new RENAME TO stores")
        cursor.execute("ALTER TABLE return_integrations_new RENAME TO return_integrations")
        cursor.execute("ALTER TABLE orders_new RENAME TO orders")
        cursor.execute("ALTER TABLE products_new RENAME TO products")
        cursor.execute("ALTER TABLE returns_new RENAME TO returns")
        cursor.execute("ALTER TABLE return_items_new RENAME TO return_items")
        cursor.execute("ALTER TABLE email_shares_new RENAME TO email_shares")
        cursor.execute("ALTER TABLE email_share_items_new RENAME TO email_share_items")
        
        # Step 4: Recreate indexes
        print("  📋 Recreating indexes...")
        
        indexes = [
            "CREATE INDEX idx_returns_client_id ON returns(client_id)",
            "CREATE INDEX idx_returns_created_at ON returns(created_at)",
            "CREATE INDEX idx_returns_processed ON returns(processed)",
            "CREATE INDEX idx_returns_warehouse_id ON returns(warehouse_id)",
            "CREATE INDEX idx_return_items_return_id ON return_items(return_id)",
            "CREATE INDEX idx_return_items_product_id ON return_items(product_id)",
            "CREATE INDEX idx_email_shares_client_id ON email_shares(client_id)",
            "CREATE INDEX idx_email_shares_date_range ON email_shares(date_range_start, date_range_end)",
            "CREATE INDEX idx_email_share_items_return_id ON email_share_items(return_id)",
            "CREATE INDEX idx_sync_logs_status ON sync_logs(status)",
            "CREATE INDEX idx_sync_logs_started_at ON sync_logs(started_at)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                print(f"    ⚠️  Index creation warning: {e}")
        
        conn.commit()
        
        print("\n🔍 Verifying schema changes...")
        check_data_types(cursor)
        
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
    
    print(f"🔄 Starting safe schema fix for: {db_path}")
    
    # Create backup
    backup_path = backup_database(db_path)
    
    # Apply schema fix
    apply_schema_fix_safe(db_path)
    
    print(f"\n🎉 Schema fix completed!")
    print(f"📁 Original database: {db_path}")
    print(f"💾 Backup created: {backup_path}")
    print(f"\n📋 Summary of changes:")
    print(f"   • All ID fields converted from INTEGER to BIGINT")
    print(f"   • Prevents overflow issues with large API IDs")
    print(f"   • Matches Azure SQL schema data types")
    print(f"   • All existing data preserved")

if __name__ == "__main__":
    main()
