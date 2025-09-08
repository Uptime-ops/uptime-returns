"""
Quick fix script to update enhanced_app.py for Azure SQL compatibility
"""

# Add this helper function at the top of enhanced_app.py after the database configuration:

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

# For each endpoint, update like this:

# Example for /api/clients:
"""
@app.get("/api/clients")
async def get_clients():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM clients ORDER BY name")
        
        if USE_AZURE_SQL:
            rows = cursor.fetchall()
            clients = rows_to_dict(cursor, rows)
        else:
            clients = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        return clients
    except Exception as e:
        print(f"Error in get_clients: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return []
"""

# The main issue is that SQLite uses different row handling than pyodbc
# We need to handle both cases properly