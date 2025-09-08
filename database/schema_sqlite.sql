-- Warehance Returns Database Schema
-- SQLite Database

-- Drop existing tables if they exist
DROP TABLE IF EXISTS email_share_items;
DROP TABLE IF EXISTS email_shares;
DROP TABLE IF EXISTS return_items;
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS return_integrations;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS sync_logs;

-- Clients table
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouses table
CREATE TABLE warehouses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores table
CREATE TABLE stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Return integrations table
CREATE TABLE return_integrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    return_integration_type TEXT,
    store_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

-- Orders table
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    order_number TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main returns table
CREATE TABLE returns (
    id INTEGER PRIMARY KEY,
    api_id TEXT,
    paid_by TEXT,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    processed INTEGER DEFAULT 0,
    processed_at TIMESTAMP,
    warehouse_note TEXT,
    customer_note TEXT,
    tracking_number TEXT,
    tracking_url TEXT,
    carrier TEXT,
    service TEXT,
    label_cost REAL,
    label_pdf_url TEXT,
    rma_slip_url TEXT,
    label_voided INTEGER DEFAULT 0,
    client_id INTEGER,
    warehouse_id INTEGER,
    order_id INTEGER,
    return_integration_id INTEGER,
    first_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (return_integration_id) REFERENCES return_integrations(id)
);

-- Return items table
CREATE TABLE return_items (
    id INTEGER PRIMARY KEY,
    return_id INTEGER NOT NULL,
    product_id INTEGER,
    quantity INTEGER,
    return_reasons TEXT, -- JSON array stored as text
    condition_on_arrival TEXT, -- JSON array stored as text
    quantity_received INTEGER,
    quantity_rejected INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Email shares tracking table
CREATE TABLE email_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
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
    return_id INTEGER NOT NULL,
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
    total_pages INTEGER DEFAULT 0,
    total_returns_fetched INTEGER DEFAULT 0,
    new_returns INTEGER DEFAULT 0,
    updated_returns INTEGER DEFAULT 0,
    error_message TEXT,
    metadata TEXT -- JSON stored as text
);

-- Create indexes for better query performance
CREATE INDEX idx_returns_client_id ON returns(client_id);
CREATE INDEX idx_returns_status ON returns(status);
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
SELECT r.*, c.name as client_name, w.name as warehouse_name
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
SELECT 
    c.id as client_id,
    c.name as client_name,
    COUNT(r.id) as total_returns,
    SUM(CASE WHEN r.processed = 1 THEN 1 ELSE 0 END) as processed_returns,
    SUM(CASE WHEN r.processed = 0 THEN 1 ELSE 0 END) as pending_returns,
    MAX(r.created_at) as last_return_date
FROM clients c
LEFT JOIN returns r ON c.id = r.client_id
GROUP BY c.id, c.name;