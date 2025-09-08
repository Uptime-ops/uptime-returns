"""
FastAPI Backend for Warehance Returns Management System
"""

import sys
import os
import json
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import pandas as pd
from io import BytesIO

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, Query, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, distinct
from pydantic import BaseModel, Field
from loguru import logger

from config.config import settings
from database.models import (
    get_db, Return, ReturnItem, Client, Warehouse,
    Product, EmailShare, EmailShareItem, SyncLog
)
from scripts.sync_returns import WarehanceAPISync

# Initialize FastAPI app
app = FastAPI(
    title="Warehance Returns Management",
    description="API for managing and tracking Warehance returns",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (create directory if doesn't exist)
import os
static_dir = "static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configure logger
logger.add(settings.log_file, rotation="10 MB", retention="30 days", level=settings.log_level)


# Pydantic models for API
class ReturnFilter(BaseModel):
    client_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    status: Optional[str] = None
    processed: Optional[bool] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    unshared_only: bool = False
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)


class EmailShareRequest(BaseModel):
    client_id: int
    date_range_start: date
    date_range_end: date
    recipient_email: str
    subject: Optional[str] = None
    notes: Optional[str] = None
    return_ids: Optional[List[int]] = None


class SyncRequest(BaseModel):
    sync_type: str = "full"


class DashboardStats(BaseModel):
    total_returns: int
    pending_returns: int
    processed_returns: int
    total_clients: int
    total_warehouses: int
    returns_today: int
    returns_this_week: int
    returns_this_month: int
    unshared_returns: int
    last_sync: Optional[datetime] = None


# API Endpoints

@app.get("/")
async def root():
    """Serve the main HTML dashboard"""
    return FileResponse("web/templates/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    try:
        # Basic counts
        total_returns = db.query(func.count(Return.id)).scalar()
        pending_returns = db.query(func.count(Return.id)).filter(
            Return.processed == False
        ).scalar()
        processed_returns = db.query(func.count(Return.id)).filter(
            Return.processed == True
        ).scalar()
        
        total_clients = db.query(func.count(distinct(Client.id))).scalar()
        total_warehouses = db.query(func.count(distinct(Warehouse.id))).scalar()
        
        # Date-based counts
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        returns_today = db.query(func.count(Return.id)).filter(
            func.date(Return.created_at) == today
        ).scalar()
        
        returns_this_week = db.query(func.count(Return.id)).filter(
            func.date(Return.created_at) >= week_ago
        ).scalar()
        
        returns_this_month = db.query(func.count(Return.id)).filter(
            func.date(Return.created_at) >= month_ago
        ).scalar()
        
        # Unshared returns count
        shared_return_ids = db.query(distinct(EmailShareItem.return_id)).join(
            EmailShare, EmailShareItem.email_share_id == EmailShare.id
        ).filter(EmailShare.share_status == "sent").subquery()
        
        unshared_returns = db.query(func.count(Return.id)).filter(
            ~Return.id.in_(shared_return_ids)
        ).scalar()
        
        # Last sync time
        last_sync = db.query(SyncLog).filter(
            SyncLog.status == "completed"
        ).order_by(SyncLog.completed_at.desc()).first()
        
        return DashboardStats(
            total_returns=total_returns or 0,
            pending_returns=pending_returns or 0,
            processed_returns=processed_returns or 0,
            total_clients=total_clients or 0,
            total_warehouses=total_warehouses or 0,
            returns_today=returns_today or 0,
            returns_this_week=returns_this_week or 0,
            returns_this_month=returns_this_month or 0,
            unshared_returns=unshared_returns or 0,
            last_sync=last_sync.completed_at if last_sync else None
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/returns/search")
async def search_returns(
    filter_params: ReturnFilter,
    db: Session = Depends(get_db)
):
    """Search and filter returns with pagination"""
    try:
        # Use raw SQL to avoid SQLAlchemy issues
        sql_query = """
        SELECT r.id, r.status, r.created_at, r.tracking_number, 
               r.processed, r.api_id,
               c.name as client_name, 
               w.name as warehouse_name
        FROM returns r
        LEFT JOIN clients c ON r.client_id = c.id
        LEFT JOIN warehouses w ON r.warehouse_id = w.id
        WHERE 1=1
        """
        params = {}
        
        if filter_params.client_id:
            sql_query += " AND r.client_id = :client_id"
            params['client_id'] = filter_params.client_id
            
        if filter_params.status:
            sql_query += " AND r.status = :status"
            params['status'] = filter_params.status
        
        # Get count
        count_query = f"SELECT COUNT(*) FROM ({sql_query}) as cnt"
        total_count = db.execute(count_query, params).scalar()
        
        # Add pagination
        sql_query += " LIMIT :limit OFFSET :offset"
        params['limit'] = filter_params.limit
        params['offset'] = (filter_params.page - 1) * filter_params.limit
        
        # Execute query
        results = db.execute(sql_query, params).fetchall()
        
        # Convert to list of dicts
        return_list = []
        for row in results:
            return_list.append({
                "id": row.id,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "tracking_number": row.tracking_number,
                "processed": row.processed,
                "api_id": row.api_id,
                "client_name": row.client_name,
                "warehouse_name": row.warehouse_name,
                "is_shared": False
            })
        
        return {
            "returns": return_list,
            "total_count": total_count,
            "page": filter_params.page,
            "limit": filter_params.limit,
            "total_pages": (total_count + filter_params.limit - 1) // filter_params.limit if total_count > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error searching returns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/returns/{return_id}")
async def get_return_detail(return_id: int, db: Session = Depends(get_db)):
    """Get detailed information for a specific return"""
    try:
        return_obj = db.query(Return).filter(Return.id == return_id).first()
        
        if not return_obj:
            raise HTTPException(status_code=404, detail="Return not found")
        
        # Get return data
        return_data = return_obj.to_dict()
        
        # Add items details
        items = []
        for item in return_obj.items:
            item_dict = {
                "id": item.id,
                "quantity": item.quantity,
                "return_reasons": item.return_reasons,
                "condition_on_arrival": item.condition_on_arrival,
                "quantity_received": item.quantity_received,
                "quantity_rejected": item.quantity_rejected,
                "product": {
                    "id": item.product.id,
                    "sku": item.product.sku,
                    "name": item.product.name
                } if item.product else None
            }
            items.append(item_dict)
        
        return_data["items"] = items
        
        # Check if return has been shared
        shared = db.query(EmailShareItem).join(
            EmailShare, EmailShareItem.email_share_id == EmailShare.id
        ).filter(
            EmailShareItem.return_id == return_id,
            EmailShare.share_status == "sent"
        ).first()
        
        return_data["is_shared"] = shared is not None
        
        return return_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting return detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clients")
async def get_clients(db: Session = Depends(get_db)):
    """Get list of all clients"""
    try:
        clients = db.query(Client).order_by(Client.name).all()
        return [{"id": c.id, "name": c.name} for c in clients]
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/warehouses")
async def get_warehouses(db: Session = Depends(get_db)):
    """Get list of all warehouses"""
    try:
        warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
        return [{"id": w.id, "name": w.name} for w in warehouses]
    except Exception as e:
        logger.error(f"Error getting warehouses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email-shares/create")
async def create_email_share(
    share_request: EmailShareRequest,
    db: Session = Depends(get_db)
):
    """Create a new email share record"""
    try:
        # Get returns to share
        query = db.query(Return).filter(
            Return.client_id == share_request.client_id,
            func.date(Return.created_at) >= share_request.date_range_start,
            func.date(Return.created_at) <= share_request.date_range_end
        )
        
        # If specific return IDs provided, filter by those
        if share_request.return_ids:
            query = query.filter(Return.id.in_(share_request.return_ids))
        
        # Exclude already shared returns
        shared_return_ids = db.query(distinct(EmailShareItem.return_id)).join(
            EmailShare, EmailShareItem.email_share_id == EmailShare.id
        ).filter(
            EmailShare.client_id == share_request.client_id,
            EmailShare.share_status == "sent"
        ).subquery()
        
        query = query.filter(~Return.id.in_(shared_return_ids))
        
        returns_to_share = query.all()
        
        if not returns_to_share:
            raise HTTPException(status_code=400, detail="No unshared returns found for the specified criteria")
        
        # Create email share record
        email_share = EmailShare(
            client_id=share_request.client_id,
            date_range_start=share_request.date_range_start,
            date_range_end=share_request.date_range_end,
            recipient_email=share_request.recipient_email,
            subject=share_request.subject or f"Returns Report - {share_request.date_range_start} to {share_request.date_range_end}",
            total_returns_shared=len(returns_to_share),
            share_status="pending",
            notes=share_request.notes,
            created_by="system"
        )
        
        db.add(email_share)
        db.flush()  # Get the ID
        
        # Add share items
        for return_obj in returns_to_share:
            share_item = EmailShareItem(
                email_share_id=email_share.id,
                return_id=return_obj.id
            )
            db.add(share_item)
        
        db.commit()
        
        return {
            "id": email_share.id,
            "client_id": email_share.client_id,
            "total_returns_shared": email_share.total_returns_shared,
            "recipient_email": email_share.recipient_email,
            "status": email_share.share_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating email share: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email-shares/history")
async def get_email_share_history(
    client_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get email share history"""
    try:
        query = db.query(EmailShare).join(Client)
        
        if client_id:
            query = query.filter(EmailShare.client_id == client_id)
        
        query = query.order_by(EmailShare.created_at.desc()).limit(limit)
        
        shares = query.all()
        
        result = []
        for share in shares:
            result.append({
                "id": share.id,
                "client_id": share.client_id,
                "client_name": share.client.name,
                "date_range_start": share.date_range_start.isoformat(),
                "date_range_end": share.date_range_end.isoformat(),
                "recipient_email": share.recipient_email,
                "total_returns_shared": share.total_returns_shared,
                "share_status": share.share_status,
                "sent_at": share.sent_at.isoformat() if share.sent_at else None,
                "created_at": share.created_at.isoformat()
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting email share history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/trigger")
async def trigger_sync(
    sync_request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger a manual sync of returns data"""
    try:
        # Check if a sync is already running
        running_sync = db.query(SyncLog).filter(
            SyncLog.status == "running"
        ).first()
        
        if running_sync:
            return {
                "status": "error",
                "message": "A sync is already in progress",
                "sync_id": running_sync.id
            }
        
        # Create sync log entry
        sync_log = SyncLog(
            sync_type=sync_request.sync_type,
            status="pending"
        )
        db.add(sync_log)
        db.commit()
        
        # Add to background tasks
        def run_sync():
            syncer = WarehanceAPISync()
            syncer.run_sync(sync_request.sync_type)
        
        background_tasks.add_task(run_sync)
        
        return {
            "status": "started",
            "message": f"{sync_request.sync_type.capitalize()} sync started",
            "sync_id": sync_log.id
        }
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Get current sync status and history"""
    try:
        # Get current/latest sync
        latest_sync = db.query(SyncLog).order_by(
            SyncLog.started_at.desc()
        ).first()
        
        # Get sync history
        history = db.query(SyncLog).filter(
            SyncLog.status.in_(["completed", "failed"])
        ).order_by(SyncLog.started_at.desc()).limit(10).all()
        
        return {
            "current_sync": latest_sync.to_dict() if latest_sync else None,
            "history": [sync.to_dict() for sync in history]
        }
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/returns")
async def export_returns(
    format: str = Query(default="csv", regex="^(csv|excel)$"),
    client_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Export returns data to CSV or Excel"""
    try:
        query = db.query(Return).join(Client, isouter=True).join(Warehouse, isouter=True)
        
        # Apply filters
        if client_id:
            query = query.filter(Return.client_id == client_id)
        
        if date_from:
            query = query.filter(func.date(Return.created_at) >= date_from)
        
        if date_to:
            query = query.filter(func.date(Return.created_at) <= date_to)
        
        returns = query.all()
        
        # Convert to DataFrame
        data = []
        for r in returns:
            data.append({
                "Return ID": r.id,
                "API ID": r.api_id,
                "Client": r.client.name if r.client else "",
                "Warehouse": r.warehouse.name if r.warehouse else "",
                "Status": r.status,
                "Processed": r.processed,
                "Created At": r.created_at,
                "Tracking Number": r.tracking_number,
                "Carrier": r.carrier,
                "Label Cost": r.label_cost
            })
        
        df = pd.DataFrame(data)
        
        # Generate file
        if format == "csv":
            output = BytesIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=returns_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
        else:  # Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Returns', index=False)
            output.seek(0)
            
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=returns_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
                }
            )
            
    except Exception as e:
        logger.error(f"Error exporting returns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/return-reasons")
async def get_return_reasons_analytics(db: Session = Depends(get_db)):
    """Get analytics on return reasons"""
    try:
        # For SQLite, we need to process JSON differently
        # Get all return items with reasons
        items_with_reasons = db.query(ReturnItem).filter(
            ReturnItem.return_reasons != None,
            ReturnItem.return_reasons != '[]'
        ).all()
        
        # Process reasons manually since SQLite doesn't have unnest
        reason_counts = {}
        for item in items_with_reasons:
            try:
                reasons = json.loads(item.return_reasons) if isinstance(item.return_reasons, str) else item.return_reasons
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
            except:
                continue
        
        # Convert to list and sort by count
        result = [{"reason": reason, "count": count} for reason, count in reason_counts.items()]
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return result[:20]  # Return top 20
        
    except Exception as e:
        logger.error(f"Error getting return reasons analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        reload=False  # Disable reload to save resources
    )