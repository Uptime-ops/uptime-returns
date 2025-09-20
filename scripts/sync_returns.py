"""
Warehance API Sync Script
Fetches returns data from Warehance API and stores in PostgreSQL database
"""

import sys
import os
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json
from loguru import logger

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import settings
from database.models import (
    SessionLocal, Return, ReturnItem, Client, Warehouse,
    Order, Product, Store, ReturnIntegration, SyncLog
)

# Configure logger
logger.add(settings.log_file, rotation="10 MB", retention="30 days", level=settings.log_level)


class WarehanceAPISync:
    """Handles synchronization of returns data from Warehance API"""
    
    def __init__(self):
        self.api_key = settings.warehance_api_key
        self.api_url = settings.warehance_api_url
        self.headers = {
            "X-API-KEY": self.api_key,
            "accept": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def fetch_returns_page(self, page: int = 1, limit: int = 100) -> Optional[Dict]:
        """
        Fetch a single page of returns from the API
        
        Args:
            page: Page number to fetch
            limit: Number of items per page
            
        Returns:
            API response as dictionary or None if error
        """
        try:
            params = {
                "page": page,
                "limit": limit
            }
            
            url = f"{self.api_url}/returns"
            logger.info(f"Fetching page {page} from {url}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") == "success":
                return data.get("data", {})
            else:
                logger.error(f"API returned non-success status: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            return None
    
    def fetch_all_returns(self) -> List[Dict]:
        """
        Fetch all returns from the API using pagination
        
        Returns:
            List of all returns
        """
        all_returns = []
        page = 1
        limit = settings.api_page_size
        total_pages = None
        
        while True:
            # Add delay between requests to avoid rate limiting
            if page > 1:
                time.sleep(settings.retry_delay_seconds)
            
            page_data = self.fetch_returns_page(page, limit)
            
            if not page_data:
                logger.warning(f"Failed to fetch page {page}, stopping pagination")
                break
            
            returns = page_data.get("returns", [])
            total_count = page_data.get("total_count", 0)
            
            # Calculate total pages if not set
            if total_pages is None and total_count > 0:
                total_pages = (total_count + limit - 1) // limit
                logger.info(f"Total returns: {total_count}, Total pages: {total_pages}")
            
            if not returns:
                logger.info(f"No returns found on page {page}, stopping")
                break
            
            all_returns.extend(returns)
            logger.info(f"Fetched {len(returns)} returns from page {page}")
            
            # Check if we've reached the last page
            if total_pages and page >= total_pages:
                logger.info(f"Reached last page ({page})")
                break
            
            page += 1
            
        logger.info(f"Total returns fetched: {len(all_returns)}")
        return all_returns
    
    def upsert_client(self, db, client_data: Dict) -> Optional[Client]:
        """Insert or update client"""
        if not client_data:
            return None
            
        client = db.query(Client).filter_by(id=client_data["id"]).first()
        
        if not client:
            client = Client(
                id=client_data["id"],
                name=client_data["name"]
            )
            db.add(client)
        else:
            client.name = client_data["name"]
            
        return client
    
    def upsert_warehouse(self, db, warehouse_data: Dict) -> Optional[Warehouse]:
        """Insert or update warehouse"""
        if not warehouse_data:
            return None
            
        warehouse = db.query(Warehouse).filter_by(id=warehouse_data["id"]).first()
        
        if not warehouse:
            warehouse = Warehouse(
                id=warehouse_data["id"],
                name=warehouse_data["name"]
            )
            db.add(warehouse)
        else:
            warehouse.name = warehouse_data["name"]
            
        return warehouse
    
    def upsert_order(self, db, order_data: Dict) -> Optional[Order]:
        """Insert or update order"""
        if not order_data:
            return None
            
        order = db.query(Order).filter_by(id=order_data["id"]).first()
        
        if not order:
            order = Order(
                id=order_data["id"],
                order_number=order_data["order_number"]
            )
            db.add(order)
        else:
            order.order_number = order_data["order_number"]
            
        return order
    
    def upsert_product(self, db, product_data: Dict) -> Optional[Product]:
        """Insert or update product"""
        if not product_data:
            return None
            
        product = db.query(Product).filter_by(id=product_data["id"]).first()
        
        if not product:
            product = Product(
                id=product_data["id"],
                sku=product_data["sku"],
                name=product_data["name"]
            )
            db.add(product)
        else:
            product.sku = product_data["sku"]
            product.name = product_data["name"]
            
        return product
    
    def upsert_return_integration(self, db, integration_data: Dict) -> Optional[ReturnIntegration]:
        """Insert or update return integration"""
        if not integration_data:
            return None
            
        # Handle store if present
        store = None
        if integration_data.get("store"):
            store_data = integration_data["store"]
            store = db.query(Store).filter_by(id=store_data["id"]).first()
            
            if not store:
                store = Store(
                    id=store_data["id"],
                    name=store_data["name"]
                )
                db.add(store)
            else:
                store.name = store_data["name"]
        
        integration = db.query(ReturnIntegration).filter_by(id=integration_data["id"]).first()
        
        if not integration:
            integration = ReturnIntegration(
                id=integration_data["id"],
                name=integration_data["name"],
                return_integration_type=integration_data.get("return_integration_type"),
                store_id=store.id if store else None
            )
            db.add(integration)
        else:
            integration.name = integration_data["name"]
            integration.return_integration_type = integration_data.get("return_integration_type")
            integration.store_id = store.id if store else None
            
        return integration
    
    def parse_datetime(self, date_string: str) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not date_string:
            return None
        
        try:
            # Handle ISO format with Z suffix
            if date_string.endswith('Z'):
                date_string = date_string[:-1] + '+00:00'
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    def sync_return(self, db, return_data: Dict) -> tuple[bool, bool]:
        """
        Sync a single return to the database
        
        Returns:
            Tuple of (is_new, is_updated)
        """
        return_id = return_data["id"]
        is_new = False
        is_updated = False
        
        # Check if return already exists
        existing_return = db.query(Return).filter_by(id=return_id).first()
        
        # Upsert related entities
        client = self.upsert_client(db, return_data.get("client"))
        warehouse = self.upsert_warehouse(db, return_data.get("warehouse"))
        order = self.upsert_order(db, return_data.get("order"))
        integration = self.upsert_return_integration(db, return_data.get("return_integration"))
        
        # Create or update return
        if not existing_return:
            is_new = True
            return_obj = Return(
                id=return_id,
                api_id=return_data.get("api_id"),
                paid_by=return_data.get("paid_by"),
                status=return_data.get("status"),
                created_at=self.parse_datetime(return_data.get("created_at")),
                updated_at=self.parse_datetime(return_data.get("updated_at")),
                processed=return_data.get("processed", False),
                processed_at=self.parse_datetime(return_data.get("processed_at")),
                warehouse_note=return_data.get("warehouse_note"),
                customer_note=return_data.get("customer_note"),
                tracking_number=return_data.get("tracking_number"),
                tracking_url=return_data.get("tracking_url"),
                carrier=return_data.get("carrier"),
                service=return_data.get("service"),
                label_cost=return_data.get("label_cost"),
                label_pdf_url=return_data.get("label_pdf_url"),
                rma_slip_url=return_data.get("rma_slip_url"),
                label_voided=return_data.get("label_voided", False),
                client_id=client.id if client else None,
                warehouse_id=warehouse.id if warehouse else None,
                order_id=order.id if order else None,
                return_integration_id=integration.id if integration else None,
                first_synced_at=datetime.utcnow()
            )
            db.add(return_obj)
        else:
            # Check if updated
            if existing_return.updated_at != self.parse_datetime(return_data.get("updated_at")):
                is_updated = True
            
            # Update existing return
            existing_return.api_id = return_data.get("api_id")
            existing_return.paid_by = return_data.get("paid_by")
            existing_return.status = return_data.get("status")
            existing_return.created_at = self.parse_datetime(return_data.get("created_at"))
            existing_return.updated_at = self.parse_datetime(return_data.get("updated_at"))
            existing_return.processed = return_data.get("processed", False)
            existing_return.processed_at = self.parse_datetime(return_data.get("processed_at"))
            existing_return.warehouse_note = return_data.get("warehouse_note")
            existing_return.customer_note = return_data.get("customer_note")
            existing_return.tracking_number = return_data.get("tracking_number")
            existing_return.tracking_url = return_data.get("tracking_url")
            existing_return.carrier = return_data.get("carrier")
            existing_return.service = return_data.get("service")
            existing_return.label_cost = return_data.get("label_cost")
            existing_return.label_pdf_url = return_data.get("label_pdf_url")
            existing_return.rma_slip_url = return_data.get("rma_slip_url")
            existing_return.label_voided = return_data.get("label_voided", False)
            existing_return.client_id = client.id if client else None
            existing_return.warehouse_id = warehouse.id if warehouse else None
            existing_return.order_id = order.id if order else None
            existing_return.return_integration_id = integration.id if integration else None
            existing_return.last_synced_at = datetime.utcnow()
            return_obj = existing_return
        
        # Sync return items
        if return_data.get("items"):
            # Delete existing items for this return
            db.query(ReturnItem).filter_by(return_id=return_id).delete()
            
            for item_data in return_data["items"]:
                # Upsert product
                product = self.upsert_product(db, item_data.get("product"))
                
                # Create return item (convert arrays to JSON strings for SQLite)
                return_item = ReturnItem(
                    id=item_data["id"],
                    return_id=return_id,
                    product_id=product.id if product else None,
                    quantity=item_data.get("quantity"),
                    return_reasons=json.dumps(item_data.get("return_reasons", [])),
                    condition_on_arrival=json.dumps(item_data.get("condition_on_arrival", [])),
                    quantity_received=item_data.get("quantity_received"),
                    quantity_rejected=item_data.get("quantity_rejected")
                )
                db.add(return_item)
        
        return is_new, is_updated
    
    def run_sync(self, sync_type: str = "full") -> Dict[str, Any]:
        """
        Run the synchronization process
        
        Args:
            sync_type: Type of sync ("full" or "incremental")
            
        Returns:
            Dictionary with sync results
        """
        db = SessionLocal()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type=sync_type,
                started_at=datetime.utcnow(),
                status="running",
                current_phase="initializing",
                current_operation="Starting sync process..."
            )
            db.add(sync_log)
            db.commit()
            
            logger.info(f"Starting {sync_type} sync...")
            
            # Phase 1: Fetching returns from API
            sync_log.current_phase = "fetching"
            sync_log.current_operation = "Fetching returns from Warehance API..."
            sync_log.last_progress_update = datetime.utcnow()
            db.commit()
            
            all_returns = self.fetch_all_returns()
            
            if not all_returns:
                logger.warning("No returns fetched from API")
                sync_log.status = "completed"
                sync_log.completed_at = datetime.utcnow()
                sync_log.total_returns_fetched = 0
                sync_log.current_phase = "completed"
                sync_log.current_operation = "No returns found to sync"
                db.commit()
                return {"status": "completed", "returns_fetched": 0}
            
            # Phase 2: Processing returns
            sync_log.current_phase = "processing"
            sync_log.total_to_process = len(all_returns)
            sync_log.processed_count = 0
            sync_log.current_operation = f"Processing {len(all_returns)} returns..."
            sync_log.last_progress_update = datetime.utcnow()
            db.commit()
            
            new_count = 0
            updated_count = 0
            error_count = 0
            
            for i, return_data in enumerate(all_returns):
                try:
                    is_new, is_updated = self.sync_return(db, return_data)
                    if is_new:
                        new_count += 1
                    elif is_updated:
                        updated_count += 1
                    
                    # Commit after each return for SQLite
                    db.commit()
                    
                    # Update progress every 10 returns or at the end
                    if (i + 1) % 10 == 0 or i == len(all_returns) - 1:
                        sync_log.processed_count = i + 1
                        sync_log.current_operation = f"Processing return {i + 1} of {len(all_returns)} ({new_count} new, {updated_count} updated)"
                        sync_log.last_progress_update = datetime.utcnow()
                        db.commit()
                        
                        # Log progress every 50 returns
                        if (new_count + updated_count) % 50 == 0:
                            logger.info(f"Progress: {new_count} new, {updated_count} updated")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error syncing return {return_data.get('id')}: {e}")
                    db.rollback()
            
            # Final commit
            db.commit()
            
            # Phase 3: Completion
            sync_log.status = "completed"
            sync_log.completed_at = datetime.utcnow()
            sync_log.current_phase = "completed"
            sync_log.current_operation = f"Sync completed successfully! {new_count} new, {updated_count} updated, {error_count} errors"
            sync_log.total_returns_fetched = len(all_returns)
            sync_log.new_returns = new_count
            sync_log.updated_returns = updated_count
            sync_log.sync_metadata = {
                "error_count": error_count,
                "sync_duration_seconds": (datetime.utcnow() - sync_log.started_at).total_seconds()
            }
            db.commit()
            
            logger.info(f"Sync completed: {new_count} new, {updated_count} updated, {error_count} errors")
            
            return {
                "status": "completed",
                "returns_fetched": len(all_returns),
                "new_returns": new_count,
                "updated_returns": updated_count,
                "errors": error_count
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            
            if sync_log:
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                sync_log.current_phase = "failed"
                sync_log.current_operation = f"Sync failed: {str(e)}"
                sync_log.error_message = str(e)
                db.commit()
            
            return {
                "status": "failed",
                "error": str(e)
            }
            
        finally:
            db.close()


def main():
    """Main function to run the sync"""
    syncer = WarehanceAPISync()
    
    # Check if API key is configured
    if not syncer.api_key:
        logger.error("API key not configured. Please set WAREHANCE_API_KEY in .env file")
        return
    
    # Run sync
    result = syncer.run_sync()
    
    # Print results
    print("\n" + "="*50)
    print("SYNC RESULTS")
    print("="*50)
    for key, value in result.items():
        print(f"{key}: {value}")
    print("="*50)


if __name__ == "__main__":
    main()