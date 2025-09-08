"""
Email Sender Script for Warehance Returns
Handles sending return reports to clients via email
"""

import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import pandas as pd
from io import BytesIO
from typing import List, Optional
from jinja2 import Template
from loguru import logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import settings
from database.models import (
    SessionLocal, EmailShare, EmailShareItem, Return, Client, ReturnItem
)


class EmailSender:
    """Handles email sending for return reports"""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.from_email = settings.email_from
        self.from_name = settings.email_from_name
        
    def create_html_report(self, returns: List[Return], client: Client, share: EmailShare) -> str:
        """
        Create HTML email report for returns
        """
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }
                .header {
                    background-color: #007bff;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }
                .container {
                    padding: 20px;
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .summary {
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    padding: 15px;
                    margin-bottom: 20px;
                }
                .summary h2 {
                    color: #007bff;
                    margin-top: 0;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th {
                    background-color: #007bff;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    border: 1px solid #ddd;
                }
                td {
                    padding: 10px;
                    border: 1px solid #ddd;
                }
                tr:nth-child(even) {
                    background-color: #f2f2f2;
                }
                .footer {
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }
                .status-pending {
                    color: #856404;
                    font-weight: bold;
                }
                .status-processed {
                    color: #155724;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Returns Report</h1>
                <p>{{ client_name }}</p>
            </div>
            
            <div class="container">
                <div class="summary">
                    <h2>Report Summary</h2>
                    <p><strong>Report Period:</strong> {{ date_from }} to {{ date_to }}</p>
                    <p><strong>Total Returns:</strong> {{ total_returns }}</p>
                    <p><strong>Pending Returns:</strong> {{ pending_returns }}</p>
                    <p><strong>Processed Returns:</strong> {{ processed_returns }}</p>
                    <p><strong>Report Generated:</strong> {{ report_date }}</p>
                </div>
                
                <h2>Returns Details</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Return ID</th>
                            <th>Order #</th>
                            <th>Status</th>
                            <th>Created Date</th>
                            <th>Tracking #</th>
                            <th>Carrier</th>
                            <th>Items</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for return in returns %}
                        <tr>
                            <td>{{ return.id }}</td>
                            <td>{{ return.order_number or 'N/A' }}</td>
                            <td class="{{ 'status-processed' if return.processed else 'status-pending' }}">
                                {{ return.status }}
                            </td>
                            <td>{{ return.created_at }}</td>
                            <td>{{ return.tracking_number or 'N/A' }}</td>
                            <td>{{ return.carrier or 'N/A' }}</td>
                            <td>{{ return.items_count }} item(s)</td>
                            <td>{{ return.customer_note or '-' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>This is an automated report from Warehance Returns Management System</p>
                <p>If you have any questions, please contact your account manager</p>
                <p>&copy; {{ current_year }} - All rights reserved</p>
            </div>
        </body>
        </html>
        """
        
        template = Template(html_template)
        
        # Prepare returns data
        returns_data = []
        pending_count = 0
        processed_count = 0
        
        for r in returns:
            return_dict = {
                'id': r.id,
                'order_number': r.order.order_number if r.order else None,
                'status': r.status,
                'processed': r.processed,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                'tracking_number': r.tracking_number,
                'carrier': r.carrier,
                'items_count': len(r.items) if r.items else 0,
                'customer_note': r.customer_note
            }
            returns_data.append(return_dict)
            
            if r.processed:
                processed_count += 1
            else:
                pending_count += 1
        
        # Render template
        html_content = template.render(
            client_name=client.name,
            date_from=share.date_range_start.strftime('%Y-%m-%d'),
            date_to=share.date_range_end.strftime('%Y-%m-%d'),
            total_returns=len(returns),
            pending_returns=pending_count,
            processed_returns=processed_count,
            report_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            returns=returns_data,
            current_year=datetime.utcnow().year
        )
        
        return html_content
    
    def create_excel_attachment(self, returns: List[Return]) -> BytesIO:
        """
        Create Excel file attachment with returns data
        """
        # Prepare data for DataFrame
        data = []
        for r in returns:
            # Basic return info
            row = {
                'Return ID': r.id,
                'API ID': r.api_id,
                'Order Number': r.order.order_number if r.order else None,
                'Client': r.client.name if r.client else None,
                'Warehouse': r.warehouse.name if r.warehouse else None,
                'Status': r.status,
                'Processed': 'Yes' if r.processed else 'No',
                'Created Date': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else None,
                'Processed Date': r.processed_at.strftime('%Y-%m-%d %H:%M') if r.processed_at else None,
                'Tracking Number': r.tracking_number,
                'Carrier': r.carrier,
                'Service': r.service,
                'Label Cost': float(r.label_cost) if r.label_cost else None,
                'Customer Note': r.customer_note,
                'Warehouse Note': r.warehouse_note
            }
            
            # If there are items, add item details
            if r.items:
                for item in r.items:
                    item_row = row.copy()
                    item_row.update({
                        'Product SKU': item.product.sku if item.product else None,
                        'Product Name': item.product.name if item.product else None,
                        'Quantity': item.quantity,
                        'Quantity Received': item.quantity_received,
                        'Quantity Rejected': item.quantity_rejected,
                        'Return Reasons': ', '.join(item.return_reasons) if item.return_reasons else None
                    })
                    data.append(item_row)
            else:
                data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Returns', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Returns']
            
            # Format header
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#007bff',
                'font_color': 'white',
                'border': 1
            })
            
            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Adjust column widths
            for idx, col in enumerate(df.columns):
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                ) + 2
                worksheet.set_column(idx, idx, min(max_len, 50))
        
        output.seek(0)
        return output
    
    def send_email(self, email_share_id: int) -> bool:
        """
        Send email for a specific email share record
        
        Args:
            email_share_id: ID of the EmailShare record
            
        Returns:
            True if email sent successfully, False otherwise
        """
        db = SessionLocal()
        
        try:
            # Get email share record
            share = db.query(EmailShare).filter_by(id=email_share_id).first()
            
            if not share:
                logger.error(f"Email share {email_share_id} not found")
                return False
            
            # Get client
            client = share.client
            
            # Get returns for this share
            returns = db.query(Return).join(
                EmailShareItem, Return.id == EmailShareItem.return_id
            ).filter(
                EmailShareItem.email_share_id == email_share_id
            ).all()
            
            if not returns:
                logger.error(f"No returns found for email share {email_share_id}")
                return False
            
            # Create email message
            msg = MIMEMultipart('mixed')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = share.recipient_email
            msg['Subject'] = share.subject or f"Returns Report - {client.name} ({share.date_range_start} to {share.date_range_end})"
            
            # Create HTML content
            html_content = self.create_html_report(returns, client, share)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Create Excel attachment
            excel_file = self.create_excel_attachment(returns)
            excel_attachment = MIMEApplication(excel_file.read())
            excel_attachment['Content-Disposition'] = f'attachment; filename="returns_report_{client.name}_{datetime.utcnow().strftime("%Y%m%d")}.xlsx"'
            msg.attach(excel_attachment)
            
            # Send email
            logger.info(f"Sending email to {share.recipient_email}")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            # Update share record
            share.share_status = 'sent'
            share.sent_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Email sent successfully for share {email_share_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email for share {email_share_id}: {e}")
            
            # Update share record with error
            if share:
                share.share_status = 'failed'
                share.notes = f"Send failed: {str(e)}"
                db.commit()
            
            return False
            
        finally:
            db.close()
    
    def send_pending_emails(self) -> dict:
        """
        Send all pending email shares
        
        Returns:
            Dictionary with send results
        """
        db = SessionLocal()
        
        try:
            # Get all pending email shares
            pending_shares = db.query(EmailShare).filter_by(share_status='pending').all()
            
            if not pending_shares:
                logger.info("No pending email shares to send")
                return {"sent": 0, "failed": 0}
            
            sent_count = 0
            failed_count = 0
            
            for share in pending_shares:
                if self.send_email(share.id):
                    sent_count += 1
                else:
                    failed_count += 1
                
                # Add delay between emails to avoid rate limiting
                time.sleep(2)
            
            return {
                "sent": sent_count,
                "failed": failed_count,
                "total": len(pending_shares)
            }
            
        finally:
            db.close()


def main():
    """Main function to send pending emails"""
    
    # Check if email credentials are configured
    if not settings.smtp_user or not settings.smtp_password:
        logger.error("Email credentials not configured. Please update .env file")
        return
    
    sender = EmailSender()
    
    logger.info("Starting email send process...")
    results = sender.send_pending_emails()
    
    logger.info(f"Email send completed: {results['sent']} sent, {results['failed']} failed")
    print(f"\nEmail Send Results:")
    print(f"Sent: {results['sent']}")
    print(f"Failed: {results['failed']}")


if __name__ == "__main__":
    main()