"""
Fetch real products from Warehance API and populate the database
"""
import requests
import sqlite3
import json
import os
from datetime import datetime

# API Configuration
API_KEY = os.getenv('WAREHANCE_API_KEY')
if not API_KEY:
    raise ValueError("WAREHANCE_API_KEY environment variable must be set")
API_URL = "https://api.warehance.com/v1"

def fetch_products():
    """Fetch products from Warehance API"""
    headers = {
        "X-API-KEY": API_KEY,
        "accept": "application/json"
    }
    
    all_products = []
    page = 1
    
    while True:
        params = {
            "page": page,
            "limit": 100
        }
        
        print(f"Fetching products page {page}...")
        response = requests.get(f"{API_URL}/products", headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching products: {response.status_code}")
            break
            
        data = response.json()
        
        if data.get("status") == "success":
            products_data = data.get("data", {}).get("products", [])
            if not products_data:
                break
                
            all_products.extend(products_data)
            print(f"Fetched {len(products_data)} products from page {page}")
            
            # Check if there are more pages
            total_count = data.get("data", {}).get("total_count", 0)
            if len(all_products) >= total_count:
                break
                
            page += 1
        else:
            print(f"API returned non-success status: {data}")
            break
    
    return all_products

def update_database(products):
    """Update database with real products"""
    conn = sqlite3.connect('warehance_returns.db')
    cursor = conn.cursor()
    
    # Clear existing sample products
    print("Clearing sample products...")
    cursor.execute("DELETE FROM return_items")
    cursor.execute("DELETE FROM products")
    
    # Insert real products
    print(f"Inserting {len(products)} real products...")
    for product in products:
        cursor.execute('''
            INSERT OR REPLACE INTO products (id, sku, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            product['id'],
            product.get('sku', ''),
            product.get('name', ''),
            datetime.now(),
            datetime.now()
        ))
    
    conn.commit()
    
    # Verify the data
    cursor.execute('SELECT COUNT(*) FROM products')
    print(f'Total products in database: {cursor.fetchone()[0]}')
    
    # Show sample products
    cursor.execute('SELECT id, sku, name FROM products LIMIT 10')
    print('\nSample products:')
    for row in cursor.fetchall():
        print(f'  ID: {row[0]}, SKU: {row[1]}, Name: {row[2]}')
    
    conn.close()

def fetch_and_populate_return_items():
    """Fetch individual returns to get their items"""
    conn = sqlite3.connect('warehance_returns.db')
    cursor = conn.cursor()
    
    # Get some return IDs to fetch details for
    cursor.execute('SELECT id FROM returns LIMIT 20')
    return_ids = [row[0] for row in cursor.fetchall()]
    
    headers = {
        "X-API-KEY": API_KEY,
        "accept": "application/json"
    }
    
    item_id = 3000  # Starting ID for return items
    items_added = 0
    
    for return_id in return_ids:
        print(f"Fetching details for return {return_id}...")
        response = requests.get(f"{API_URL}/returns/{return_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return_data = data.get("data", {})
                items = return_data.get("items", [])
                
                for item in items:
                    product = item.get("product", {})
                    if product:
                        # First ensure the product exists
                        cursor.execute('''
                            INSERT OR REPLACE INTO products (id, sku, name, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            product['id'],
                            product.get('sku', ''),
                            product.get('name', ''),
                            datetime.now(),
                            datetime.now()
                        ))
                        
                        # Then add the return item
                        cursor.execute('''
                            INSERT OR REPLACE INTO return_items (
                                id, return_id, product_id, quantity, 
                                return_reasons, condition_on_arrival,
                                quantity_received, quantity_rejected,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            item_id,
                            return_id,
                            product['id'],
                            item.get('quantity', 0),
                            json.dumps(item.get('return_reasons', [])),
                            json.dumps(item.get('condition_on_arrival', [])),
                            item.get('quantity_received', 0),
                            item.get('quantity_rejected', 0),
                            datetime.now(),
                            datetime.now()
                        ))
                        item_id += 1
                        items_added += 1
    
    conn.commit()
    
    # Verify the return items
    cursor.execute('SELECT COUNT(*) FROM return_items')
    print(f'\nTotal return items in database: {cursor.fetchone()[0]}')
    
    # Show sample return items with products
    cursor.execute('''
        SELECT r.id, p.sku, p.name, ri.quantity
        FROM returns r
        JOIN return_items ri ON r.id = ri.return_id
        JOIN products p ON ri.product_id = p.id
        LIMIT 5
    ''')
    
    print('\nSample return items with real products:')
    for row in cursor.fetchall():
        print(f'Return {row[0]}: {row[2]} (SKU: {row[1]}) - Qty: {row[3]}')
    
    conn.close()
    print(f'\nSuccessfully added {items_added} return items')

if __name__ == "__main__":
    print("Fetching real products from Warehance API...")
    products = fetch_products()
    
    if products:
        print(f"\nFetched {len(products)} products total")
        update_database(products)
        
        print("\n" + "="*50)
        print("Fetching return details to populate return items...")
        fetch_and_populate_return_items()
    else:
        print("No products fetched from API")
    
    print("\nDone! Real product data has been populated.")