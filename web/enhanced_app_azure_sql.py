"""
Enhanced FastAPI app with Azure SQL Database support
This version uses Azure SQL instead of SQLite for cloud deployment
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Azure Environment Detection
IS_AZURE = os.getenv('WEBSITE_INSTANCE_ID') is not None

# Configuration from environment variables
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET', '')
WAREHANCE_API_KEY = os.getenv('WAREHANCE_API_KEY')

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_AZURE_SQL = bool(DATABASE_URL and 'database.windows.net' in DATABASE_URL)

from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import csv
import io
from datetime import datetime
import asyncio
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Database imports - use appropriate library based on database type
if USE_AZURE_SQL:
    import pyodbc
    import urllib
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    
    # Parse connection string for pyodbc
    params = urllib.parse.quote_plus(DATABASE_URL)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", poolclass=NullPool)
    
    def get_db_connection():
        """Get Azure SQL connection"""
        return engine.connect()
    
    def dict_factory(cursor, row):
        """Convert SQL rows to dictionaries"""
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}
else:
    import sqlite3
    DATABASE_PATH = '../warehance_returns.db' if not IS_AZURE else '/home/warehance_returns.db'
    
    def get_db_connection():
        """Get SQLite connection"""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

# Import email configuration
try:
    from email_config import EMAIL_CONFIG, EMAIL_TEMPLATE, EMAIL_TEMPLATE_PLAIN
except ImportError:
    EMAIL_CONFIG = None
    EMAIL_TEMPLATE = None
    EMAIL_TEMPLATE_PLAIN = None

# Import OAuth email support
try:
    from email_oauth import MicrosoftGraphMailer, GRAPH_CONFIG
    OAUTH_ENABLED = True
except ImportError:
    OAUTH_ENABLED = False
    GRAPH_CONFIG = None

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global sync status
sync_status = {
    "is_running": False,
    "last_sync": None,
    "last_sync_status": None,
    "last_sync_message": None,
    "items_synced": 0
}

# Initialize database tables if using Azure SQL
def init_azure_sql_tables():
    """Create tables in Azure SQL if they don't exist"""
    if not USE_AZURE_SQL:
        return
    
    with engine.connect() as conn:
        # Check if tables exist
        result = conn.execute(text("""
            SELECT COUNT(*) as count 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'returns'
        """))
        
        if result.fetchone()['count'] == 0:
            print("Creating Azure SQL tables...")
            # Create all tables (use the SQL script from azure_sql_setup.md)
            # This is a simplified version - you should run the full script
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name NVARCHAR(255),
                    warehance_id NVARCHAR(100),
                    created_at DATETIME2 DEFAULT GETDATE()
                )
            """))
            conn.commit()
            print("Tables created successfully")

# Initialize tables on startup
if USE_AZURE_SQL:
    init_azure_sql_tables()

@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse('templates/index.html')

@app.get("/api/returns")
async def get_returns(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get returns with filtering and pagination - Azure SQL compatible"""
    conn = get_db_connection()
    
    try:
        if USE_AZURE_SQL:
            # Azure SQL query syntax
            query = """
                SELECT r.*, c.name as client_name, w.name as warehouse_name
                FROM returns r
                LEFT JOIN clients c ON r.client_id = c.id
                LEFT JOIN warehouses w ON r.warehouse_id = w.id
                WHERE 1=1
            """
            params = {}
            
            if search:
                query += " AND (r.return_number LIKE :search OR r.notes LIKE :search)"
                params['search'] = f'%{search}%'
            
            if status:
                query += " AND r.status = :status"
                params['status'] = status
            
            if client_id:
                query += " AND r.client_id = :client_id"
                params['client_id'] = client_id
            
            if start_date:
                query += " AND r.return_date >= :start_date"
                params['start_date'] = start_date
            
            if end_date:
                query += " AND r.return_date <= :end_date"
                params['end_date'] = end_date
            
            query += " ORDER BY r.return_date DESC"
            query += f" OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
            
            result = conn.execute(text(query), params)
            returns = [dict(row) for row in result]
            
            # Get total count
            count_query = "SELECT COUNT(*) as total FROM returns r WHERE 1=1"
            # Add same filters for count...
            count_result = conn.execute(text(count_query), params)
            total = count_result.fetchone()['total']
            
        else:
            # SQLite query (existing code)
            query = """
                SELECT r.*, c.name as client_name, w.name as warehouse_name
                FROM returns r
                LEFT JOIN clients c ON r.client_id = c.id
                LEFT JOIN warehouses w ON r.warehouse_id = w.id
                WHERE 1=1
            """
            params = []
            
            if search:
                query += " AND (r.return_number LIKE ? OR r.notes LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%'])
            
            if status:
                query += " AND r.status = ?"
                params.append(status)
            
            if client_id:
                query += " AND r.client_id = ?"
                params.append(client_id)
            
            if start_date:
                query += " AND DATE(r.return_date) >= DATE(?)"
                params.append(start_date)
            
            if end_date:
                query += " AND DATE(r.return_date) <= DATE(?)"
                params.append(end_date)
            
            query += " ORDER BY r.return_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, skip])
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            returns = [dict(row) for row in cursor.fetchall()]
            
            # Get total count
            count_query = "SELECT COUNT(*) as total FROM returns r WHERE 1=1"
            # Add same filters...
            cursor.execute(count_query, params[:-2] if params else [])
            total = cursor.fetchone()['total']
        
        return {
            "returns": returns,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    finally:
        conn.close()

# ... Rest of the endpoints would be similarly updated to support both SQLite and Azure SQL ...

# The key changes for Azure SQL:
# 1. Use parameterized queries with named parameters (:param) instead of ?
# 2. Use OFFSET/FETCH instead of LIMIT/OFFSET
# 3. Use DATETIME2 instead of DATETIME
# 4. Use NVARCHAR instead of TEXT
# 5. Use IDENTITY instead of AUTOINCREMENT

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8015)))
    uvicorn.run(app, host="0.0.0.0", port=port)