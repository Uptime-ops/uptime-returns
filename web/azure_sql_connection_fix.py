"""
Emergency fix for Azure SQL connection - paste this into Azure Portal's App Service Editor
or use in Kudu console to directly update enhanced_app.py
"""

# Replace the get_db_connection function starting around line 32 with this:

def get_db_connection():
    """Get Azure SQL connection with fallback"""
    if pyodbc:
        # Parse the DATABASE_URL to ensure it has the right format
        import re
        
        # Extract components from the connection string
        conn_str = DATABASE_URL
        
        # Try different connection string formats
        if 'Driver=' not in conn_str and 'DRIVER=' not in conn_str:
            # Try multiple drivers in order of likelihood
            drivers = [
                'ODBC Driver 17 for SQL Server',
                'ODBC Driver 18 for SQL Server',
                'SQL Server Native Client 11.0',
                'SQL Server',
                'FreeTDS',
                'ODBC Driver 13 for SQL Server'
            ]
            
            for driver in drivers:
                try:
                    test_conn_str = f"DRIVER={{{driver}}};{conn_str}"
                    if 'TrustServerCertificate=' not in test_conn_str:
                        test_conn_str += ';TrustServerCertificate=yes'
                    
                    print(f"Attempting connection with driver: {driver}")
                    conn = pyodbc.connect(test_conn_str)
                    print(f"SUCCESS: Connected with {driver}")
                    
                    # Configure encoding
                    conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
                    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
                    conn.setencoding(encoding='utf-8')
                    return conn
                except Exception as e:
                    print(f"Failed with {driver}: {str(e)[:100]}")
                    continue
            
            # If no driver worked, list what's available
            available = pyodbc.drivers()
            print(f"ERROR: No driver worked. Available drivers: {available}")
            raise Exception(f"Could not connect to Azure SQL. Available drivers: {available}")
        else:
            # Connection string already has a driver
            conn = pyodbc.connect(conn_str)
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            conn.setencoding(encoding='utf-8')
            return conn
    else:
        raise Exception("pyodbc not installed - needed for Azure SQL")