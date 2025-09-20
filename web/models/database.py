# Database table schemas (Azure SQL only)
from config.database import get_db_connection, get_placeholder

def create_tables():
    """Create all required tables for Warehance Returns"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        print("Creating database tables...")

        # Clients table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='clients' AND xtype='U')
            CREATE TABLE clients (
                id BIGINT PRIMARY KEY,
                name NVARCHAR(255)
            )
        """)

        # Warehouses table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='warehouses' AND xtype='U')
            CREATE TABLE warehouses (
                id BIGINT PRIMARY KEY,
                name NVARCHAR(255)
            )
        """)

        # Returns table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='returns' AND xtype='U')
            CREATE TABLE returns (
                id BIGINT PRIMARY KEY,
                status NVARCHAR(50),
                tracking_number NVARCHAR(100),
                created_at DATETIME2,
                updated_at DATETIME2,
                processed BIT DEFAULT 0,
                client_id BIGINT,
                warehouse_id BIGINT,
                order_id BIGINT,
                notes NTEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
            )
        """)

        # Products table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='products' AND xtype='U')
            CREATE TABLE products (
                id BIGINT PRIMARY KEY,
                sku NVARCHAR(255),
                name NVARCHAR(500),
                description NTEXT,
                created_at DATETIME2,
                updated_at DATETIME2
            )
        """)

        # Return items table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='return_items' AND xtype='U')
            CREATE TABLE return_items (
                id BIGINT PRIMARY KEY,
                return_id BIGINT NOT NULL,
                product_id BIGINT,
                quantity INT DEFAULT 0,
                quantity_received INT DEFAULT 0,
                return_reasons NTEXT,
                condition_on_arrival NVARCHAR(100),
                FOREIGN KEY (return_id) REFERENCES returns(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # Orders table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='orders' AND xtype='U')
            CREATE TABLE orders (
                id BIGINT PRIMARY KEY,
                order_number NVARCHAR(100),
                status NVARCHAR(50),
                created_at DATETIME2,
                updated_at DATETIME2,
                customer_name NVARCHAR(255),
                ship_to_address NTEXT,
                total_amount DECIMAL(10,2)
            )
        """)

        # Order items table (NEW - for order item details)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='order_items' AND xtype='U')
            CREATE TABLE order_items (
                id BIGINT PRIMARY KEY,
                order_id BIGINT NOT NULL,
                product_id BIGINT,
                quantity INT DEFAULT 0,
                price DECIMAL(10,2),
                sku NVARCHAR(255),
                name NVARCHAR(500),
                bundle_order_item_id BIGINT,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        conn.commit()
        print("All tables created successfully")

    except Exception as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

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