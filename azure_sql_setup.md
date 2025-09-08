# Azure SQL Database Setup for Uptime Returns

## Step 1: Create Azure SQL Database

### In Azure Portal:

1. **Search for "SQL databases"** and click "+ Create"

2. **Basic Settings:**
   - Resource group: `rg-uptime-returns` (same as your app)
   - Database name: `uptime-returns-db`
   - Server: Click "Create new"
     - Server name: `uptime-returns-sql` (must be globally unique)
     - Location: Same as your App Service
     - Authentication method: "Use SQL authentication"
     - Server admin login: `uptimeadmin`
     - Password: [Create strong password - save this!]
     - Click "OK"

3. **Want to use SQL elastic pool?** No

4. **Workload environment:** Development

5. **Compute + storage:** 
   - Click "Configure database"
   - Service tier: "Basic" (5 DTUs, 2GB - perfect for your needs)
   - This costs ~$5/month
   - Click "Apply"

6. **Backup storage redundancy:** Locally-redundant (cheapest)

7. Click **"Review + create"** → **"Create"**

## Step 2: Configure Firewall

1. **After creation, go to your SQL Server** (not database)
   - Resource: `uptime-returns-sql`

2. **In left menu → "Networking"**

3. **Firewall rules:**
   - Allow Azure services: **Yes** (so your App Service can connect)
   - Add your current IP: Click "+ Add your client IPv4 address"
   - Save

## Step 3: Get Connection String

1. **Go to your SQL Database** (uptime-returns-db)

2. **Left menu → "Connection strings"**

3. **Copy the ADO.NET connection string**, it looks like:
   ```
   Server=tcp:uptime-returns-sql.database.windows.net,1433;Initial Catalog=uptime-returns-db;Persist Security Info=False;User ID=uptimeadmin;Password={your_password};MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;
   ```

4. **Replace {your_password}** with your actual password

## Step 4: Add Connection String to App Service

1. **Go to your App Service** (uptime-returns)

2. **Configuration → Application settings**

3. **Add new connection string:**
   - Name: `DATABASE_URL`
   - Value: [Your connection string from Step 3]
   - Type: `SQLAzure`

4. **Save**

## Step 5: Create Database Tables

### Option A: Using Azure Portal Query Editor

1. **In your SQL Database** → "Query editor (preview)"
2. **Login** with your admin credentials
3. **Run this SQL script:**

```sql
-- Clients table
CREATE TABLE clients (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255),
    warehance_id NVARCHAR(100),
    created_at DATETIME2 DEFAULT GETDATE()
);

-- Warehouses table
CREATE TABLE warehouses (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255),
    warehance_id NVARCHAR(100),
    created_at DATETIME2 DEFAULT GETDATE()
);

-- Orders table
CREATE TABLE orders (
    id INT IDENTITY(1,1) PRIMARY KEY,
    warehance_id NVARCHAR(100) UNIQUE,
    order_number NVARCHAR(100),
    order_date DATETIME2,
    customer_name NVARCHAR(255),
    ship_to_address NVARCHAR(MAX),
    created_at DATETIME2 DEFAULT GETDATE()
);

-- Products table
CREATE TABLE products (
    id INT IDENTITY(1,1) PRIMARY KEY,
    warehance_id NVARCHAR(100) UNIQUE,
    sku NVARCHAR(100),
    name NVARCHAR(500),
    barcode NVARCHAR(100),
    created_at DATETIME2 DEFAULT GETDATE()
);

-- Returns table
CREATE TABLE returns (
    id INT IDENTITY(1,1) PRIMARY KEY,
    warehance_id NVARCHAR(100) UNIQUE,
    return_number NVARCHAR(100),
    status NVARCHAR(50),
    client_id INT,
    warehouse_id INT,
    order_id INT,
    return_date DATETIME2,
    notes NVARCHAR(MAX),
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

-- Return items table
CREATE TABLE return_items (
    id INT IDENTITY(1,1) PRIMARY KEY,
    return_id INT,
    product_id INT,
    quantity INT,
    reason NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETDATE(),
    FOREIGN KEY (return_id) REFERENCES returns(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Email history table
CREATE TABLE email_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    client_id INT,
    client_name NVARCHAR(255),
    recipient_email NVARCHAR(255),
    subject NVARCHAR(500),
    attachment_name NVARCHAR(255),
    sent_date DATETIME2 DEFAULT GETDATE(),
    sent_by NVARCHAR(100),
    status NVARCHAR(50),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Settings table
CREATE TABLE settings (
    [key] NVARCHAR(100) PRIMARY KEY,
    value NVARCHAR(MAX),
    updated_at DATETIME2 DEFAULT GETDATE()
);

-- Create indexes for better performance
CREATE INDEX idx_returns_warehance_id ON returns(warehance_id);
CREATE INDEX idx_orders_warehance_id ON orders(warehance_id);
CREATE INDEX idx_products_warehance_id ON products(warehance_id);
CREATE INDEX idx_returns_client_id ON returns(client_id);
CREATE INDEX idx_return_items_return_id ON return_items(return_id);
```

### Option B: Let the app create tables automatically
(I'll update the code to auto-create tables on first run)

## Step 6: Update Application Code

The application needs to use pyodbc instead of sqlite3. Here are the required changes:

### Install new dependencies:
```bash
pip install pyodbc sqlalchemy pymssql
```

### Update requirements.txt:
```
pyodbc==5.0.1
pymssql==2.2.11
sqlalchemy==2.0.23
```

## Connection String Format for Python:

For SQLAlchemy:
```python
DATABASE_URL = "mssql+pyodbc://uptimeadmin:password@uptime-returns-sql.database.windows.net/uptime-returns-db?driver=ODBC+Driver+17+for+SQL+Server"
```

Or using pymssql:
```python
DATABASE_URL = "mssql+pymssql://uptimeadmin:password@uptime-returns-sql.database.windows.net/uptime-returns-db"
```

## Step 7: Benefits You Get

✅ **Automatic Backups**: Azure backs up your database automatically
✅ **High Availability**: 99.99% uptime SLA
✅ **Security**: Encrypted at rest and in transit
✅ **Scalability**: Can grow as your data grows
✅ **Disaster Recovery**: Built-in geo-replication options
✅ **Query from anywhere**: Use Azure Portal, SSMS, or any SQL client
✅ **No local storage**: All data in the cloud

## Monitoring Your Database

1. **In Azure Portal** → Your SQL Database
2. **Monitoring** section shows:
   - DTU usage
   - Storage usage
   - Connections
   - Deadlocks

3. **Set up alerts** for:
   - High DTU usage
   - Storage approaching limit
   - Failed connections

## Cost Breakdown

- **Basic Tier (5 DTU, 2GB)**: ~$5/month
- **Standard S0 (10 DTU, 250GB)**: ~$15/month
- **Standard S1 (20 DTU, 250GB)**: ~$30/month

Start with Basic, upgrade if needed (takes 1 minute to scale up).

## Security Best Practices

1. **Use Azure Key Vault** for connection string (optional but recommended)
2. **Enable Advanced Data Security** ($15/month - optional)
3. **Regular backups** (automatic with Azure SQL)
4. **IP restrictions** on firewall
5. **Use managed identity** for App Service connection (advanced)