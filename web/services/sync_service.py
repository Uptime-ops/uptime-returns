# Clean sync service - simplified pipeline
import requests
import json
from datetime import datetime
from typing import Dict, List, Set
from config.settings import WAREHANCE_API_KEY, WAREHANCE_BASE_URL, SYNC_BATCH_SIZE, REQUEST_TIMEOUT
from config.database import get_db_connection, get_placeholder
from models.database import create_tables

class CleanSyncService:
    """Simplified, reliable sync service"""

    def __init__(self):
        self.api_key = WAREHANCE_API_KEY
        self.headers = {
            "X-API-KEY": self.api_key,
            "accept": "application/json"
        }
        self.stats = {
            "returns_processed": 0,
            "return_items_processed": 0,
            "orders_processed": 0,
            "order_items_processed": 0,
            "errors": 0
        }

    def run_full_sync(self) -> Dict:
        """Run complete sync pipeline"""
        print("🚀 Starting clean sync pipeline...")
        sync_start = datetime.now()

        try:
            # Initialize database tables
            create_tables()

            # Step 1: Sync returns (includes return_items)
            self._sync_returns()

            # Step 2: Sync orders (includes order_items)
            self._sync_orders()

            # Calculate duration
            duration = (datetime.now() - sync_start).total_seconds()

            print(f"✅ Sync completed in {duration:.1f}s")
            print(f"📊 Stats: {self.stats}")

            return {
                "status": "success",
                "duration_seconds": duration,
                "stats": self.stats
            }

        except Exception as e:
            print(f"❌ Sync failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "stats": self.stats
            }

    def _sync_returns(self):
        """Fetch all returns with pagination and store return_items"""
        print("📦 Syncing returns...")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            offset = 0

            while True:
                # Fetch returns batch
                url = f"{WAREHANCE_BASE_URL}/returns?limit={SYNC_BATCH_SIZE}&offset={offset}"
                print(f"  📥 Fetching returns: offset {offset}")

                response = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()

                data = response.json()
                returns_batch = data.get('data', {}).get('returns', [])

                if not returns_batch:
                    print("  ✅ No more returns to process")
                    break

                # Process each return
                for return_data in returns_batch:
                    self._store_return(cursor, return_data)
                    self.stats["returns_processed"] += 1

                offset += SYNC_BATCH_SIZE

            conn.commit()
            print(f"  ✅ Returns synced: {self.stats['returns_processed']}")

        except Exception as e:
            print(f"❌ Returns sync failed: {e}")
            conn.rollback()
            self.stats["errors"] += 1
            raise
        finally:
            conn.close()

    def _store_return(self, cursor, return_data: Dict):
        """Store a single return and its items"""
        return_id = return_data.get('id')

        # Store client if exists
        if return_data.get('client'):
            client = return_data['client']
            self._upsert_client(cursor, client['id'], client.get('name', ''))

        # Store warehouse if exists
        if return_data.get('warehouse'):
            warehouse = return_data['warehouse']
            self._upsert_warehouse(cursor, warehouse['id'], warehouse.get('name', ''))

        # Store the return using simple INSERT (same as old app)
        placeholder = get_placeholder()

        # Check if return already exists
        cursor.execute(f"SELECT id FROM returns WHERE id = {placeholder}", (return_id,))
        exists = cursor.fetchone()

        if not exists:
            # Insert new return (match existing schema columns)
            cursor.execute(f"""
                INSERT INTO returns (id, status, tracking_number, created_at, updated_at, client_id, warehouse_id, order_id)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                return_id,
                return_data.get('status', ''),
                return_data.get('tracking_number', ''),
                self._parse_date(return_data.get('created_at')),
                self._parse_date(return_data.get('updated_at')),
                return_data.get('client', {}).get('id'),
                return_data.get('warehouse', {}).get('id'),
                return_data.get('order_id')
            ))
            print(f"  ✅ Inserted new return {return_id}")
        else:
            print(f"  ℹ️ Return {return_id} already exists, skipping")

        # Store return items (embedded in return response)
        items = return_data.get('items', [])
        if items:
            for item in items:
                self._store_return_item(cursor, return_id, item)
                self.stats["return_items_processed"] += 1

    def _store_return_item(self, cursor, return_id: int, item_data: Dict):
        """Store a return item (simple INSERT approach)"""
        placeholder = get_placeholder()
        item_id = item_data.get('id')

        # Check if item already exists
        cursor.execute(f"SELECT id FROM return_items WHERE id = {placeholder}", (item_id,))
        if not cursor.fetchone():
            cursor.execute(f"""
                INSERT INTO return_items (id, return_id, product_id, quantity, quantity_received, return_reasons, condition_on_arrival)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                item_id,
                return_id,
                item_data.get('product_id'),
                item_data.get('quantity', 0),
                item_data.get('quantity_received', 0),
                json.dumps(item_data.get('return_reasons', [])),
                item_data.get('condition_on_arrival', '')
            ))

    def _sync_orders(self):
        """Get unique order IDs from returns and fetch order details"""
        print("🛒 Syncing orders...")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get unique order IDs from returns
            cursor.execute("SELECT DISTINCT order_id FROM returns WHERE order_id IS NOT NULL")
            order_ids = [row[0] for row in cursor.fetchall()]

            print(f"  📝 Found {len(order_ids)} unique orders to sync")

            # Fetch each order
            for order_id in order_ids:
                self._fetch_and_store_order(cursor, order_id)
                self.stats["orders_processed"] += 1

            conn.commit()
            print(f"  ✅ Orders synced: {self.stats['orders_processed']}")

        except Exception as e:
            print(f"❌ Orders sync failed: {e}")
            conn.rollback()
            self.stats["errors"] += 1
            raise
        finally:
            conn.close()

    def _fetch_and_store_order(self, cursor, order_id: int):
        """Fetch and store a single order with its items"""
        try:
            url = f"{WAREHANCE_BASE_URL}/orders/{order_id}"
            response = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            order_data = response.json().get('data', {})

            # Store the order (simple INSERT approach)
            placeholder = get_placeholder()

            # Check if order already exists
            cursor.execute(f"SELECT id FROM orders WHERE id = {placeholder}", (order_id,))
            if not cursor.fetchone():
                cursor.execute(f"""
                    INSERT INTO orders (id, order_number, status, created_at, updated_at, customer_name, ship_to_address, total_amount)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (
                    order_id,
                    order_data.get('order_number', ''),
                    order_data.get('status', ''),
                    self._parse_date(order_data.get('created_at')),
                    self._parse_date(order_data.get('updated_at')),
                    self._extract_customer_name(order_data),
                    json.dumps(order_data.get('ship_to_address', {})),
                    order_data.get('total_amount', 0)
                ))
                print(f"  ✅ Inserted new order {order_id}")
            else:
                print(f"  ℹ️ Order {order_id} already exists, skipping")

            # Store order items (embedded in order response)
            items = order_data.get('items', [])
            for item in items:
                self._store_order_item(cursor, order_id, item)
                self.stats["order_items_processed"] += 1

        except Exception as e:
            print(f"❌ Failed to fetch order {order_id}: {e}")
            self.stats["errors"] += 1

    def _store_order_item(self, cursor, order_id: int, item_data: Dict):
        """Store an order item (simple INSERT approach)"""
        placeholder = get_placeholder()
        item_id = item_data.get('id')

        # Check if order item already exists
        cursor.execute(f"SELECT id FROM order_items WHERE id = {placeholder}", (item_id,))
        if not cursor.fetchone():
            cursor.execute(f"""
                INSERT INTO order_items (id, order_id, product_id, quantity, price, sku, name, bundle_order_item_id)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                item_id,
                order_id,
                item_data.get('product_id'),
                item_data.get('quantity', 0),
                item_data.get('price', 0),
                item_data.get('sku', ''),
                item_data.get('name', ''),
                item_data.get('bundle_order_item_id')
            ))

    def _upsert_client(self, cursor, client_id: int, name: str):
        """Insert client if not exists (simple approach)"""
        placeholder = get_placeholder()
        cursor.execute(f"SELECT id FROM clients WHERE id = {placeholder}", (client_id,))
        if not cursor.fetchone():
            cursor.execute(f"INSERT INTO clients (id, name) VALUES ({placeholder}, {placeholder})", (client_id, name))

    def _upsert_warehouse(self, cursor, warehouse_id: int, name: str):
        """Insert warehouse if not exists (simple approach)"""
        placeholder = get_placeholder()
        cursor.execute(f"SELECT id FROM warehouses WHERE id = {placeholder}", (warehouse_id,))
        if not cursor.fetchone():
            cursor.execute(f"INSERT INTO warehouses (id, name) VALUES ({placeholder}, {placeholder})", (warehouse_id, name))

    def _parse_date(self, date_string: str) -> str:
        """Parse API date to SQL Server format"""
        if not date_string:
            return None
        try:
            # Handle various date formats from API
            for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
            return date_string  # Return as-is if can't parse
        except:
            return None

    def _extract_customer_name(self, order_data: Dict) -> str:
        """Extract customer name from order data"""
        ship_to = order_data.get('ship_to_address', {})
        if isinstance(ship_to, dict):
            return f"{ship_to.get('first_name', '')} {ship_to.get('last_name', '')}".strip()
        return ""

print("Clean sync service loaded")