"""
Initialize Azure SQL Database with required tables
"""
import os
import pyodbc
import sys

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', '')

def create_tables():
    """Create all required tables in Azure SQL Database"""
    
    # Parse connection string
    conn_params = {}
    for part in DATABASE_URL.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            conn_params[key.strip().upper()] = value.strip()
    
    # Extract connection parameters
    server = conn_params.get('SERVER', '').replace('tcp:', '').replace(',1433', '')
    database = conn_params.get('DATABASE', '')
    username = conn_params.get('USER ID', '') or conn_params.get('USER', '') or conn_params.get('UID', '')
    password = conn_params.get('PASSWORD', '') or conn_params.get('PWD', '')
    
    # Connect to database
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=yes"
    )
    
    print(f"Connecting to {server}/{database}...")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Create tables
    tables = [
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INT PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS warehouses (
            id INT PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INT PRIMARY KEY,
            order_number NVARCHAR(100),
            customer_name NVARCHAR(255),
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS products (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sku NVARCHAR(100),
            name NVARCHAR(500),
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS returns (
            id INT PRIMARY KEY,
            api_id NVARCHAR(100),
            paid_by NVARCHAR(50),
            status NVARCHAR(50),
            created_at DATETIME,
            updated_at DATETIME,
            processed BIT DEFAULT 0,
            processed_at DATETIME,
            warehouse_note NVARCHAR(MAX),
            customer_note NVARCHAR(MAX),
            tracking_number NVARCHAR(100),
            tracking_url NVARCHAR(500),
            carrier NVARCHAR(100),
            service NVARCHAR(100),
            label_cost DECIMAL(10,2),
            label_pdf_url NVARCHAR(500),
            rma_slip_url NVARCHAR(500),
            label_voided BIT DEFAULT 0,
            client_id INT,
            warehouse_id INT,
            order_id INT,
            return_integration_id NVARCHAR(100),
            last_synced_at DATETIME,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS return_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            return_id INT,
            product_id INT,
            quantity INT DEFAULT 0,
            return_reasons NVARCHAR(MAX),
            condition_on_arrival NVARCHAR(MAX),
            quantity_received INT DEFAULT 0,
            quantity_rejected INT DEFAULT 0,
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE(),
            FOREIGN KEY (return_id) REFERENCES returns(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS email_history (
            id INT IDENTITY(1,1) PRIMARY KEY,
            client_id INT,
            client_name NVARCHAR(255),
            recipient_email NVARCHAR(255),
            subject NVARCHAR(500),
            attachment_name NVARCHAR(255),
            sent_date DATETIME DEFAULT GETDATE(),
            sent_by NVARCHAR(100),
            status NVARCHAR(50)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS email_share_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            return_id INT,
            share_id INT,
            created_at DATETIME DEFAULT GETDATE()
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS sync_logs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            status NVARCHAR(50),
            items_synced INT DEFAULT 0,
            started_at DATETIME DEFAULT GETDATE(),
            completed_at DATETIME,
            error_message NVARCHAR(MAX)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS settings (
            [key] NVARCHAR(100) PRIMARY KEY,
            value NVARCHAR(MAX),
            updated_at DATETIME DEFAULT GETDATE()
        )
        """
    ]
    
    # Azure SQL doesn't support IF NOT EXISTS, so we need to check first
    for i, create_sql in enumerate(tables):
        # Extract table name from CREATE TABLE statement
        import re
        match = re.search(r'CREATE TABLE IF NOT EXISTS (\w+)', create_sql)
        if match:
            table_name = match.group(1)
            
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = ?
            """, (table_name,))
            
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                # Remove IF NOT EXISTS clause for Azure SQL
                create_sql = create_sql.replace('IF NOT EXISTS ', '')
                print(f"Creating table: {table_name}")
                cursor.execute(create_sql)
                conn.commit()
            else:
                print(f"Table already exists: {table_name}")
    
    print("Database initialization complete!")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_tables()