# Database table schemas (Azure SQL only)
from config.database import get_db_connection, get_placeholder

def create_tables():
    """Skip table creation - use existing database schema"""
    print("Using existing database schema (tables already exist)")
    # The database already has the correct schema from the old app
    # No need to create new tables
    return True

def get_table_counts():
    """Get record counts for all tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = ['clients', 'warehouses', 'returns', 'products', 'return_items', 'orders', 'order_items']
    counts = {}

    try:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            counts[table] = count

        return counts
    except Exception as e:
        print(f"Error getting table counts: {e}")
        return {}
    finally:
        conn.close()

print("Database models loaded")