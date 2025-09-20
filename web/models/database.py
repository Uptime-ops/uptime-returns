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

    # First, let's see what tables actually exist
    try:
        cursor.execute("SELECT name FROM sysobjects WHERE xtype='U' ORDER BY name")
        actual_tables = [row[0] if isinstance(row, tuple) else row['name'] for row in cursor.fetchall()]
        print(f"Actual tables in database: {actual_tables}")

        counts = {}
        for table in actual_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                result = cursor.fetchone()
                count = result[0] if isinstance(result, tuple) else result['count']
                counts[table] = count
            except Exception as table_error:
                print(f"Error counting {table}: {table_error}")
                counts[table] = 0

        return counts
    except Exception as e:
        print(f"Error getting table counts: {e}")
        return {}
    finally:
        conn.close()

print("Database models loaded")