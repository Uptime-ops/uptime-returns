-- SQLite Schema Data Type Fix Script
-- This script converts INTEGER fields to BIGINT to match Azure SQL schema
-- and prevent ID overflow issues with large API data

-- Note: SQLite doesn't support ALTER COLUMN, so we need to recreate tables
-- This script should be run on a fresh database or after backing up data

-- Drop existing tables in correct order (due to foreign keys)
DROP TABLE IF EXISTS email_share_items;
DROP TABLE IF EXISTS return_items;
DROP TABLE IF EXISTS email_shares;
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS return_integrations;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS clients;

-- Recreate tables with correct BIGINT data types

-- Clients table
CREATE TABLE clients (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouses table
CREATE TABLE warehouses (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores table
CREATE TABLE stores (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Return integrations table
CREATE TABLE return_integrations (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    return_integration_type TEXT,
    store_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

-- Orders table
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    order_number TEXT NOT NULL,
    customer_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Returns table
CREATE TABLE returns (
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
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (return_integration_id) REFERENCES return_integrations(id)
);

-- Return items table
CREATE TABLE return_items (
    id BIGINT PRIMARY KEY,
    return_id BIGINT NOT NULL,
    product_id BIGINT,
    quantity INTEGER,
    return_reasons TEXT, -- JSON array stored as text
    condition_on_arrival TEXT, -- JSON array stored as text
    quantity_received INTEGER DEFAULT 0,
    quantity_rejected INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Email shares tracking table
CREATE TABLE email_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id BIGINT NOT NULL,
    share_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    recipient_email TEXT,
    subject TEXT,
    total_returns_shared INTEGER DEFAULT 0,
    share_status TEXT DEFAULT 'pending', -- pending, sent, failed
    sent_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Track individual returns in each email share
CREATE TABLE email_share_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_share_id INTEGER NOT NULL,
    return_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_share_id) REFERENCES email_shares(id) ON DELETE CASCADE,
    FOREIGN KEY (return_id) REFERENCES returns(id),
    UNIQUE(email_share_id, return_id)
);

-- Sync logs for tracking API synchronization
CREATE TABLE sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT DEFAULT 'full', -- full, incremental
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running', -- running, completed, failed
    items_processed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_returns_client_id ON returns(client_id);
CREATE INDEX idx_returns_created_at ON returns(created_at);
CREATE INDEX idx_returns_processed ON returns(processed);
CREATE INDEX idx_returns_warehouse_id ON returns(warehouse_id);
CREATE INDEX idx_return_items_return_id ON return_items(return_id);
CREATE INDEX idx_return_items_product_id ON return_items(product_id);
CREATE INDEX idx_email_shares_client_id ON email_shares(client_id);
CREATE INDEX idx_email_shares_date_range ON email_shares(date_range_start, date_range_end);
CREATE INDEX idx_email_share_items_return_id ON email_share_items(return_id);
CREATE INDEX idx_sync_logs_status ON sync_logs(status);
CREATE INDEX idx_sync_logs_started_at ON sync_logs(started_at);

-- Create views for common queries

-- View for unshared returns
CREATE VIEW unshared_returns AS
SELECT r.id, r.api_id, r.status, r.created_at, r.tracking_number,
       c.name as client_name, w.name as warehouse_name
FROM returns r
LEFT JOIN clients c ON r.client_id = c.id
LEFT JOIN warehouses w ON r.warehouse_id = w.id
WHERE r.id NOT IN (
    SELECT DISTINCT return_id 
    FROM email_share_items esi
    JOIN email_shares es ON esi.email_share_id = es.id
    WHERE es.share_status = 'sent'
);

-- View for client return summary
CREATE VIEW client_return_summary AS
SELECT c.id as client_id, c.name as client_name,
       COUNT(r.id) as total_returns,
       COUNT(CASE WHEN r.processed = 1 THEN 1 END) as processed_returns,
       COUNT(CASE WHEN r.processed = 0 THEN 1 END) as pending_returns
FROM clients c
LEFT JOIN returns r ON c.id = r.client_id
GROUP BY c.id, c.name;

-- Success message
SELECT 'Schema updated successfully! All ID fields are now BIGINT to prevent overflow issues.' as message;
