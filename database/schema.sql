-- Warehance Returns Database Schema
-- PostgreSQL Database

-- Drop existing tables if they exist (be careful in production!)
DROP TABLE IF EXISTS email_share_items CASCADE;
DROP TABLE IF EXISTS email_shares CASCADE;
DROP TABLE IF EXISTS return_items CASCADE;
DROP TABLE IF EXISTS returns CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS return_integrations CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS warehouses CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS sync_logs CASCADE;

-- Clients table
CREATE TABLE clients (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouses table
CREATE TABLE warehouses (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores table
CREATE TABLE stores (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Return integrations table
CREATE TABLE return_integrations (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    return_integration_type VARCHAR(100),
    store_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

-- Orders table
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    order_number VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sku)
);

-- Main returns table
CREATE TABLE returns (
    id BIGINT PRIMARY KEY,
    api_id VARCHAR(100),
    paid_by VARCHAR(50),
    status VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    warehouse_note TEXT,
    customer_note TEXT,
    tracking_number VARCHAR(255),
    tracking_url TEXT,
    carrier VARCHAR(100),
    service VARCHAR(100),
    label_cost DECIMAL(10, 2),
    label_pdf_url TEXT,
    rma_slip_url TEXT,
    label_voided BOOLEAN DEFAULT FALSE,
    client_id BIGINT,
    warehouse_id BIGINT,
    order_id BIGINT,
    return_integration_id BIGINT,
    -- Metadata
    first_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    return_reasons TEXT[], -- Array of reasons
    condition_on_arrival TEXT[], -- Array of conditions
    quantity_received INTEGER,
    quantity_rejected INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Email shares tracking table
CREATE TABLE email_shares (
    id SERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    share_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    recipient_email VARCHAR(255),
    subject VARCHAR(500),
    total_returns_shared INTEGER DEFAULT 0,
    share_status VARCHAR(50) DEFAULT 'pending', -- pending, sent, failed
    sent_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Track individual returns in each email share
CREATE TABLE email_share_items (
    id SERIAL PRIMARY KEY,
    email_share_id INTEGER NOT NULL,
    return_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_share_id) REFERENCES email_shares(id) ON DELETE CASCADE,
    FOREIGN KEY (return_id) REFERENCES returns(id),
    UNIQUE(email_share_id, return_id) -- Prevent duplicate entries
);

-- Sync logs for tracking API synchronization
CREATE TABLE sync_logs (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) DEFAULT 'full', -- full, incremental
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'running', -- running, completed, failed
    total_pages INTEGER DEFAULT 0,
    total_returns_fetched INTEGER DEFAULT 0,
    new_returns INTEGER DEFAULT 0,
    updated_returns INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB -- Store additional sync details
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

-- View for returns that haven't been shared yet
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

-- View for return summary by client
CREATE VIEW client_return_summary AS
SELECT 
    c.id as client_id,
    c.name as client_name,
    COUNT(r.id) as total_returns,
    COUNT(CASE WHEN r.processed = true THEN 1 END) as processed_returns,
    COUNT(CASE WHEN r.processed = false THEN 1 END) as pending_returns,
    MAX(r.created_at) as last_return_date
FROM clients c
LEFT JOIN returns r ON c.id = r.client_id
GROUP BY c.id, c.name;

-- View for return reasons analysis
CREATE VIEW return_reasons_analysis AS
SELECT 
    unnest(ri.return_reasons) as reason,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT ri.return_id) as affected_returns
FROM return_items ri
WHERE ri.return_reasons IS NOT NULL
GROUP BY reason
ORDER BY occurrence_count DESC;

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_warehouses_updated_at BEFORE UPDATE ON warehouses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stores_updated_at BEFORE UPDATE ON stores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_return_integrations_updated_at BEFORE UPDATE ON return_integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_return_items_updated_at BEFORE UPDATE ON return_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();