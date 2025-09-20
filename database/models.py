"""
SQLAlchemy database models for Warehance Returns Management System
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, BigInteger, String, Integer, Boolean,
    DateTime, Text, DECIMAL, ForeignKey, JSON, Enum,
    UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.sql import func
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import settings

# Create base class for models
Base = declarative_base()

# Create engine (set echo=False to avoid verbose output)
engine = create_engine(settings.database_url, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Client(Base):
    __tablename__ = "clients"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    returns = relationship("Return", back_populates="client")
    email_shares = relationship("EmailShare", back_populates="client")


class Warehouse(Base):
    __tablename__ = "warehouses"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    returns = relationship("Return", back_populates="warehouse")


class Store(Base):
    __tablename__ = "stores"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    return_integrations = relationship("ReturnIntegration", back_populates="store")


class ReturnIntegration(Base):
    __tablename__ = "return_integrations"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    return_integration_type = Column(String(100))
    store_id = Column(BigInteger, ForeignKey("stores.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="return_integrations")
    returns = relationship("Return", back_populates="return_integration")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(BigInteger, primary_key=True)
    order_number = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    returns = relationship("Return", back_populates="order")


class Product(Base):
    __tablename__ = "products"
    
    id = Column(BigInteger, primary_key=True)
    sku = Column(String(100), nullable=False, unique=True)
    name = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    return_items = relationship("ReturnItem", back_populates="product")


class Return(Base):
    __tablename__ = "returns"
    
    id = Column(BigInteger, primary_key=True)
    api_id = Column(String(100))
    paid_by = Column(String(50))
    status = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    warehouse_note = Column(Text)
    customer_note = Column(Text)
    tracking_number = Column(String(255))
    tracking_url = Column(Text)
    carrier = Column(String(100))
    service = Column(String(100))
    label_cost = Column(DECIMAL(10, 2))
    label_pdf_url = Column(Text)
    rma_slip_url = Column(Text)
    label_voided = Column(Boolean, default=False)
    client_id = Column(BigInteger, ForeignKey("clients.id"))
    warehouse_id = Column(BigInteger, ForeignKey("warehouses.id"))
    order_id = Column(BigInteger, ForeignKey("orders.id"))
    return_integration_id = Column(BigInteger, ForeignKey("return_integrations.id"))
    
    # Metadata
    first_synced_at = Column(DateTime, default=datetime.utcnow)
    last_synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="returns")
    warehouse = relationship("Warehouse", back_populates="returns")
    order = relationship("Order", back_populates="returns")
    return_integration = relationship("ReturnIntegration", back_populates="returns")
    items = relationship("ReturnItem", back_populates="return_obj", cascade="all, delete-orphan")
    email_share_items = relationship("EmailShareItem", back_populates="return_obj")
    
    # Indexes
    __table_args__ = (
        Index("idx_returns_client_id", "client_id"),
        Index("idx_returns_status", "status"),
        Index("idx_returns_created_at", "created_at"),
        Index("idx_returns_processed", "processed"),
        Index("idx_returns_warehouse_id", "warehouse_id"),
    )
    
    def to_dict(self):
        """Convert return object to dictionary"""
        result = {
            "id": self.id,
            "api_id": self.api_id,
            "paid_by": self.paid_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "warehouse_note": self.warehouse_note,
            "customer_note": self.customer_note,
            "tracking_number": self.tracking_number,
            "tracking_url": self.tracking_url,
            "carrier": self.carrier,
            "service": self.service,
            "label_cost": float(self.label_cost) if self.label_cost else None,
            "label_pdf_url": self.label_pdf_url,
            "rma_slip_url": self.rma_slip_url,
            "label_voided": self.label_voided,
            "client_name": None,
            "warehouse_name": None,
            "order_number": None,
            "items_count": 0
        }
        
        # Try to get related data without triggering queries
        try:
            if self.client:
                result["client_name"] = self.client.name
        except:
            pass
            
        try:
            if self.warehouse:
                result["warehouse_name"] = self.warehouse.name
        except:
            pass
            
        try:
            if self.order:
                result["order_number"] = self.order.order_number
        except:
            pass
            
        try:
            if self.items:
                result["items_count"] = len(self.items)
        except:
            pass
            
        return result


class ReturnItem(Base):
    __tablename__ = "return_items"
    
    id = Column(BigInteger, primary_key=True)
    return_id = Column(BigInteger, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id"))
    quantity = Column(Integer)
    return_reasons = Column(Text)  # Store as JSON string for SQLite
    condition_on_arrival = Column(Text)  # Store as JSON string for SQLite
    quantity_received = Column(Integer)
    quantity_rejected = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    return_obj = relationship("Return", back_populates="items")
    product = relationship("Product", back_populates="return_items")
    
    # Indexes
    __table_args__ = (
        Index("idx_return_items_return_id", "return_id"),
        Index("idx_return_items_product_id", "product_id"),
    )


class EmailShare(Base):
    __tablename__ = "email_shares"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(BigInteger, ForeignKey("clients.id"), nullable=False)
    share_date = Column(DateTime, default=datetime.utcnow)
    date_range_start = Column(DateTime, nullable=False)
    date_range_end = Column(DateTime, nullable=False)
    recipient_email = Column(String(255))
    subject = Column(String(500))
    total_returns_shared = Column(Integer, default=0)
    share_status = Column(String(50), default="pending")  # pending, sent, failed
    sent_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    
    # Relationships
    client = relationship("Client", back_populates="email_shares")
    share_items = relationship("EmailShareItem", back_populates="email_share", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_email_shares_client_id", "client_id"),
        Index("idx_email_shares_date_range", "date_range_start", "date_range_end"),
    )


class EmailShareItem(Base):
    __tablename__ = "email_share_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_share_id = Column(Integer, ForeignKey("email_shares.id", ondelete="CASCADE"), nullable=False)
    return_id = Column(BigInteger, ForeignKey("returns.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    email_share = relationship("EmailShare", back_populates="share_items")
    return_obj = relationship("Return", back_populates="email_share_items")
    
    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("email_share_id", "return_id"),
        Index("idx_email_share_items_return_id", "return_id"),
    )


class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), default="full")  # full, incremental
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), default="running")  # running, completed, failed
    total_pages = Column(Integer, default=0)
    total_returns_fetched = Column(Integer, default=0)
    new_returns = Column(Integer, default=0)
    updated_returns = Column(Integer, default=0)
    error_message = Column(Text)
    sync_metadata = Column('metadata', JSON)
    
    # Real-time progress tracking
    current_phase = Column(String(100), default="initializing")  # initializing, fetching, processing, completed
    total_to_process = Column(Integer, default=0)  # Total items that need to be processed
    processed_count = Column(Integer, default=0)  # Items processed so far
    last_progress_update = Column(DateTime, default=datetime.utcnow)
    current_operation = Column(String(500))  # Current operation description
    
    # Indexes
    __table_args__ = (
        Index("idx_sync_logs_status", "status"),
        Index("idx_sync_logs_started_at", "started_at"),
    )
    
    def to_dict(self):
        """Convert sync log to dictionary"""
        return {
            "id": self.id,
            "sync_type": self.sync_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "total_pages": self.total_pages,
            "total_returns_fetched": self.total_returns_fetched,
            "new_returns": self.new_returns,
            "updated_returns": self.updated_returns,
            "error_message": self.error_message,
            "metadata": self.sync_metadata,
            # Real-time progress fields
            "current_phase": self.current_phase,
            "total_to_process": self.total_to_process,
            "processed_count": self.processed_count,
            "last_progress_update": self.last_progress_update.isoformat() if self.last_progress_update else None,
            "current_operation": self.current_operation,
            # Calculated progress percentage
            "progress_percentage": round((self.processed_count / self.total_to_process * 100), 1) if self.total_to_process > 0 else 0
        }


def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    # Initialize database when running this module directly
    init_database()