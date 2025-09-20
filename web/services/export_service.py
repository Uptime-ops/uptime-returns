# Clean CSV export service with built-in data integrity
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional
from config.database import get_db_connection

class CleanExportService:
    """Simplified CSV export with data integrity built-in"""

    def __init__(self):
        self.integrity_stats = {
            "total_returns": 0,
            "total_items": 0,
            "duplicates_skipped": 0,
            "suspicious_orders": 0,
            "clean_exports": 0
        }

    def export_returns_csv(self, filters: Optional[Dict] = None) -> io.StringIO:
        """Export returns to CSV with one row per item"""
        print("📤 Starting clean CSV export...")

        # Reset stats
        self.integrity_stats = {k: 0 for k in self.integrity_stats}

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Build query with filters
            query, params = self._build_export_query(filters or {})

            # Execute query
            cursor.execute(query, params)
            returns_data = cursor.fetchall()

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Convert to dictionaries
            returns = [dict(zip(columns, row)) for row in returns_data]

            self.integrity_stats["total_returns"] = len(returns)
            print(f"  📊 Processing {len(returns)} returns")

            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                'Client', 'Customer Name', 'Order Date', 'Return Date',
                'Order Number', 'Item Name', 'Order Qty', 'Return Qty',
                'Reason for Return'
            ])

            # Process each return
            for return_row in returns:
                self._process_return_for_csv(cursor, return_row, writer)

            # Print integrity report
            self._print_integrity_report()

            return output

        except Exception as e:
            print(f"❌ CSV export failed: {e}")
            raise
        finally:
            conn.close()

    def _build_export_query(self, filters: Dict) -> tuple:
        """Build SQL query with filters"""
        base_query = """
            SELECT
                r.id as return_id,
                r.status,
                r.created_at as return_date,
                r.tracking_number,
                c.name as client_name,
                w.name as warehouse_name,
                r.order_id,
                o.order_number,
                o.created_at as order_date,
                o.customer_name
            FROM returns r
            LEFT JOIN clients c ON r.client_id = c.id
            LEFT JOIN warehouses w ON r.warehouse_id = w.id
            LEFT JOIN orders o ON r.order_id = o.id
            WHERE 1=1
        """

        params = []

        # Apply filters
        if filters.get('client_id'):
            base_query += " AND r.client_id = %s"
            params.append(filters['client_id'])

        if filters.get('status'):
            if filters['status'] == 'pending':
                base_query += " AND r.processed = 0"
            elif filters['status'] == 'processed':
                base_query += " AND r.processed = 1"

        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            base_query += " AND (r.tracking_number LIKE %s OR CAST(r.id AS NVARCHAR) LIKE %s OR c.name LIKE %s)"
            params.extend([search_term, search_term, search_term])

        base_query += " ORDER BY r.created_at DESC"

        return base_query, params

    def _process_return_for_csv(self, cursor, return_row: Dict, writer):
        """Process a single return and write its items to CSV"""
        return_id = return_row['return_id']

        # Get return items for this return
        cursor.execute("""
            SELECT
                ri.id,
                ri.quantity as order_quantity,
                ri.quantity_received as return_quantity,
                ri.return_reasons,
                COALESCE(p.name, oi.name, 'Unknown Product') as item_name,
                COALESCE(p.sku, oi.sku, 'Unknown SKU') as sku
            FROM return_items ri
            LEFT JOIN products p ON ri.product_id = p.id
            LEFT JOIN order_items oi ON ri.product_id = oi.product_id AND oi.order_id = %s
            WHERE ri.return_id = %s
        """, (return_row['order_id'], return_id))

        items = cursor.fetchall()
        item_columns = [desc[0] for desc in cursor.description]
        items = [dict(zip(item_columns, item)) for item in items]

        if not items:
            # No return items - create placeholder row
            self._write_csv_row(writer, return_row, {
                'item_name': 'No items found',
                'order_quantity': 0,
                'return_quantity': 0,
                'return_reasons': 'No return items in database'
            })
            return

        # Track duplicates for this return
        seen_items = set()

        for item in items:
            # Check for duplicates
            item_key = f"{item['id']}-{item['item_name']}-{item['sku']}"

            if item_key in seen_items:
                self.integrity_stats["duplicates_skipped"] += 1
                print(f"  ⚠️ Skipping duplicate item: {item['item_name']} (return {return_id})")
                continue

            seen_items.add(item_key)

            # Write clean row
            self._write_csv_row(writer, return_row, item)
            self.integrity_stats["total_items"] += 1

    def _write_csv_row(self, writer, return_row: Dict, item: Dict):
        """Write a single CSV row with data integrity validation"""

        # Validate order number
        order_number = return_row.get('order_number', '')
        clean_order_number = self._validate_order_number(
            order_number,
            return_row['return_id'],
            return_row['order_id']
        )

        # Parse return reasons
        reasons = self._parse_return_reasons(item.get('return_reasons', ''))

        # Format dates
        order_date = self._format_date(return_row.get('order_date'))
        return_date = self._format_date(return_row.get('return_date'))

        # Write row
        writer.writerow([
            return_row.get('client_name', ''),
            return_row.get('customer_name', ''),
            order_date,
            return_date,
            clean_order_number,
            item.get('item_name', ''),
            item.get('order_quantity', 0),
            item.get('return_quantity', 0),
            reasons
        ])

        self.integrity_stats["clean_exports"] += 1

    def _validate_order_number(self, order_number: str, return_id: int, order_id: int) -> str:
        """Validate and clean order number"""
        if not order_number:
            return ''

        order_str = str(order_number)

        # Check if it's suspiciously long (likely an ID)
        if order_str.isdigit() and len(order_str) > 10:
            self.integrity_stats["suspicious_orders"] += 1
            print(f"  ⚠️ Suspicious order number (ID?): {order_number}")
            return f"ID-{order_number}"

        # Check if it matches return ID or order ID
        if order_str == str(return_id):
            self.integrity_stats["suspicious_orders"] += 1
            print(f"  ⚠️ Order number is return ID: {order_number}")
            return f"RETURN-{order_number}"

        if order_str == str(order_id):
            self.integrity_stats["suspicious_orders"] += 1
            print(f"  ⚠️ Order number is order ID: {order_number}")
            return f"ORDER-{order_number}"

        return order_number

    def _parse_return_reasons(self, reasons_json: str) -> str:
        """Parse return reasons from JSON"""
        if not reasons_json:
            return ''

        try:
            import json
            reasons = json.loads(reasons_json)
            if isinstance(reasons, list):
                return ', '.join(reasons)
            return str(reasons)
        except:
            return str(reasons_json)

    def _format_date(self, date_value) -> str:
        """Format date for CSV"""
        if not date_value:
            return ''

        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d')

        # Try to parse string date
        try:
            if isinstance(date_value, str):
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
        except:
            pass

        return str(date_value)

    def _print_integrity_report(self):
        """Print data integrity report"""
        print(f"\n{'='*60}")
        print(f"📊 CSV EXPORT INTEGRITY REPORT")
        print(f"{'='*60}")
        print(f"✅ Total returns processed: {self.integrity_stats['total_returns']}")
        print(f"📦 Total items exported: {self.integrity_stats['total_items']}")
        print(f"🔄 Duplicates skipped: {self.integrity_stats['duplicates_skipped']}")
        print(f"⚠️ Suspicious order numbers: {self.integrity_stats['suspicious_orders']}")
        print(f"✅ Clean rows exported: {self.integrity_stats['clean_exports']}")

        if self.integrity_stats['duplicates_skipped'] == 0 and self.integrity_stats['suspicious_orders'] == 0:
            print(f"🎉 NO DATA INTEGRITY ISSUES - Export is clean!")
        else:
            print(f"⚠️ Data integrity issues found - check logs above")

        print(f"{'='*60}\n")

print("Clean export service loaded")