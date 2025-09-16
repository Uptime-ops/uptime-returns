-- SQLite Existing Database Data Type Fix Script
-- This script attempts to fix data types in an existing database
-- WARNING: SQLite has limited ALTER support, so some operations may not work

-- Note: SQLite doesn't support ALTER COLUMN for changing data types
-- The safest approach is to recreate the database using the full schema
-- This script is provided for reference but may not work on all SQLite versions

-- Check current schema
.schema

-- Attempt to add new columns with correct types (if supported)
-- This is a workaround since SQLite doesn't support ALTER COLUMN

-- For clients table
-- ALTER TABLE clients ADD COLUMN id_new BIGINT;
-- UPDATE clients SET id_new = id;
-- ALTER TABLE clients DROP COLUMN id;
-- ALTER TABLE clients RENAME COLUMN id_new TO id;

-- For warehouses table  
-- ALTER TABLE warehouses ADD COLUMN id_new BIGINT;
-- UPDATE warehouses SET id_new = id;
-- ALTER TABLE warehouses DROP COLUMN id;
-- ALTER TABLE warehouses RENAME COLUMN id_new TO id;

-- For stores table
-- ALTER TABLE stores ADD COLUMN id_new BIGINT;
-- UPDATE stores SET id_new = id;
-- ALTER TABLE stores DROP COLUMN id;
-- ALTER TABLE stores RENAME COLUMN id_new TO id;

-- For return_integrations table
-- ALTER TABLE return_integrations ADD COLUMN id_new BIGINT;
-- UPDATE return_integrations SET id_new = id;
-- ALTER TABLE return_integrations DROP COLUMN id;
-- ALTER TABLE return_integrations RENAME COLUMN id_new TO id;

-- ALTER TABLE return_integrations ADD COLUMN store_id_new BIGINT;
-- UPDATE return_integrations SET store_id_new = store_id;
-- ALTER TABLE return_integrations DROP COLUMN store_id;
-- ALTER TABLE return_integrations RENAME COLUMN store_id_new TO store_id;

-- For orders table
-- ALTER TABLE orders ADD COLUMN id_new BIGINT;
-- UPDATE orders SET id_new = id;
-- ALTER TABLE orders DROP COLUMN id;
-- ALTER TABLE orders RENAME COLUMN id_new TO id;

-- For products table
-- ALTER TABLE products ADD COLUMN id_new BIGINT;
-- UPDATE products SET id_new = id;
-- ALTER TABLE products DROP COLUMN id;
-- ALTER TABLE products RENAME COLUMN id_new TO id;

-- For returns table
-- ALTER TABLE returns ADD COLUMN id_new BIGINT;
-- UPDATE returns SET id_new = id;
-- ALTER TABLE returns DROP COLUMN id;
-- ALTER TABLE returns RENAME COLUMN id_new TO id;

-- ALTER TABLE returns ADD COLUMN client_id_new BIGINT;
-- UPDATE returns SET client_id_new = client_id;
-- ALTER TABLE returns DROP COLUMN client_id;
-- ALTER TABLE returns RENAME COLUMN client_id_new TO client_id;

-- ALTER TABLE returns ADD COLUMN warehouse_id_new BIGINT;
-- UPDATE returns SET warehouse_id_new = warehouse_id;
-- ALTER TABLE returns DROP COLUMN warehouse_id;
-- ALTER TABLE returns RENAME COLUMN warehouse_id_new TO warehouse_id;

-- ALTER TABLE returns ADD COLUMN order_id_new BIGINT;
-- UPDATE returns SET order_id_new = order_id;
-- ALTER TABLE returns DROP COLUMN order_id;
-- ALTER TABLE returns RENAME COLUMN order_id_new TO order_id;

-- For return_items table
-- ALTER TABLE return_items ADD COLUMN id_new BIGINT;
-- UPDATE return_items SET id_new = id;
-- ALTER TABLE return_items DROP COLUMN id;
-- ALTER TABLE return_items RENAME COLUMN id_new TO id;

-- ALTER TABLE return_items ADD COLUMN return_id_new BIGINT;
-- UPDATE return_items SET return_id_new = return_id;
-- ALTER TABLE return_items DROP COLUMN return_id;
-- ALTER TABLE return_items RENAME COLUMN return_id_new TO return_id;

-- ALTER TABLE return_items ADD COLUMN product_id_new BIGINT;
-- UPDATE return_items SET product_id_new = product_id;
-- ALTER TABLE return_items DROP COLUMN product_id;
-- ALTER TABLE return_items RENAME COLUMN product_id_new TO product_id;

-- For email_share_items table
-- ALTER TABLE email_share_items ADD COLUMN return_id_new BIGINT;
-- UPDATE email_share_items SET return_id_new = return_id;
-- ALTER TABLE email_share_items DROP COLUMN return_id;
-- ALTER TABLE email_share_items RENAME COLUMN return_id_new TO return_id;

-- IMPORTANT: The above ALTER statements may not work in all SQLite versions
-- The recommended approach is to use the full schema recreation script:
-- database/alter_schema_sqlite_bigint_fix.sql

SELECT 'WARNING: SQLite ALTER COLUMN support is limited. Use the full schema recreation script instead.' as message;
