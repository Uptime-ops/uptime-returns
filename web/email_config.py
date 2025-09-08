"""
Email Configuration for Warehance Returns System
"""

# Email Server Configuration (Update these with your Exchange settings)
EMAIL_CONFIG = {
    # SMTP Settings for Exchange/Office 365
    "SMTP_SERVER": "smtp.office365.com",  # Office 365 SMTP server
    "SMTP_PORT": 587,
    "USE_TLS": True,
    
    # Authentication - Use your personal account that has "Send As" permissions
    "AUTH_EMAIL": "your.email@uptimeops.net",  # Your personal email with permissions
    "AUTH_PASSWORD": "",  # Your personal account password
    
    # Shared Mailbox Settings
    "SENDER_EMAIL": "returns@uptimeops.net",  # The shared mailbox address
    "SENDER_NAME": "Uptime Ops Returns Team",
    
    # Default Settings
    "DEFAULT_SUBJECT": "Returns Report - {client_name} - {date}",
    "CC_EMAILS": [],  # Optional CC recipients
    "BCC_EMAILS": [],  # Optional BCC recipients
}

# Email Template for Client Reports
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }
        .logo {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .content {
            background: white;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-radius: 0 0 10px 10px;
        }
        .greeting {
            font-size: 18px;
            margin-bottom: 20px;
        }
        .summary-box {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .summary-title {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            margin-top: 5px;
        }
        .attachment-note {
            background: #e8f4f8;
            border: 1px solid #b8e0ec;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .attachment-icon {
            color: #0066cc;
            font-weight: bold;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #666;
            font-size: 14px;
        }
        .button {
            display: inline-block;
            padding: 12px 30px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .contact-info {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th {
            background: #667eea;
            color: white;
            padding: 10px;
            text-align: left;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">📦 Warehance Returns Report</div>
        <div>{report_date}</div>
    </div>
    
    <div class="content">
        <div class="greeting">
            Dear {client_name} Team,
        </div>
        
        <p>Please find attached your returns report for the period of <strong>{date_range}</strong>.</p>
        
        <div class="summary-box">
            <div class="summary-title">📊 Report Summary</div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{total_returns}</div>
                    <div class="stat-label">Total Returns</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{processed_returns}</div>
                    <div class="stat-label">Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{pending_returns}</div>
                    <div class="stat-label">Pending</div>
                </div>
            </div>
        </div>

        <div class="summary-box">
            <div class="summary-title">📈 Key Highlights</div>
            <ul>
                <li>Total items returned: <strong>{total_items}</strong></li>
                <li>Most common return reason: <strong>{top_reason}</strong></li>
                <li>Average processing time: <strong>{avg_processing_time}</strong></li>
            </ul>
        </div>
        
        <div class="attachment-note">
            <span class="attachment-icon">📎 Attachment:</span> 
            <strong>{attachment_name}</strong><br>
            This CSV file contains detailed information about all returns including:
            <ul style="margin-top: 10px;">
                <li>Customer information</li>
                <li>Order and return dates</li>
                <li>Product details and quantities</li>
                <li>Return reasons</li>
            </ul>
        </div>
        
        <div class="contact-info">
            <strong>Need assistance?</strong><br>
            If you have any questions about this report, please don't hesitate to contact us.<br>
            Email: support@warehance.com | Phone: 1-800-RETURNS
        </div>
    </div>
    
    <div class="footer">
        <p>This is an automated report from the Warehance Returns Management System</p>
        <p>&copy; {year} Warehance. All rights reserved.</p>
    </div>
</body>
</html>
"""

# Plain text version for fallback
EMAIL_TEMPLATE_PLAIN = """
Warehance Returns Report
========================

Dear {client_name} Team,

Please find attached your returns report for the period of {date_range}.

REPORT SUMMARY
--------------
• Total Returns: {total_returns}
• Processed: {processed_returns}
• Pending: {pending_returns}

KEY HIGHLIGHTS
--------------
• Total items returned: {total_items}
• Most common return reason: {top_reason}
• Average processing time: {avg_processing_time}

The attached CSV file ({attachment_name}) contains detailed information about all returns.

If you have any questions about this report, please contact us at support@warehance.com

Best regards,
Warehance Returns Team

---
This is an automated report from the Warehance Returns Management System
© {year} Warehance. All rights reserved.
"""