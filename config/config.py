"""
Configuration module for Warehance Returns Management System
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

class Settings(BaseSettings):
    """Application settings"""
    
    # Warehance API
    warehance_api_key: str = Field(default=os.getenv("WAREHANCE_API_KEY", ""))
    warehance_api_url: str = Field(default=os.getenv("WAREHANCE_API_URL", "https://api.warehance.com/v1"))
    
    # Database - SQLite
    database_type: str = Field(default=os.getenv("DATABASE_TYPE", "sqlite"))
    database_path: str = Field(default=os.getenv("DATABASE_PATH", "warehance_returns.db"))
    
    # Application
    app_env: str = Field(default=os.getenv("APP_ENV", "development"))
    app_debug: bool = Field(default=os.getenv("APP_DEBUG", "true").lower() == "true")
    app_port: int = Field(default=int(os.getenv("APP_PORT", "8000")))
    app_host: str = Field(default=os.getenv("APP_HOST", "0.0.0.0"))
    
    # Email
    smtp_host: str = Field(default=os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = Field(default=int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = Field(default=os.getenv("SMTP_USER", ""))
    smtp_password: str = Field(default=os.getenv("SMTP_PASSWORD", ""))
    email_from: str = Field(default=os.getenv("EMAIL_FROM", ""))
    email_from_name: str = Field(default=os.getenv("EMAIL_FROM_NAME", "Warehance Returns System"))
    
    # Security
    secret_key: str = Field(default=os.getenv("SECRET_KEY", "change-this-in-production"))
    access_token_expire_minutes: int = Field(default=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")))
    
    # Sync Settings
    sync_interval_hours: int = Field(default=int(os.getenv("SYNC_INTERVAL_HOURS", "1")))
    max_retries: int = Field(default=int(os.getenv("MAX_RETRIES", "3")))
    retry_delay_seconds: int = Field(default=int(os.getenv("RETRY_DELAY_SECONDS", "5")))
    
    # Pagination
    api_page_size: int = Field(default=int(os.getenv("API_PAGE_SIZE", "100")))
    web_page_size: int = Field(default=int(os.getenv("WEB_PAGE_SIZE", "50")))
    
    # Logging
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = Field(default=os.getenv("LOG_FILE", "logs/app.log"))
    
    # File Storage
    upload_dir: str = Field(default=os.getenv("UPLOAD_DIR", "uploads"))
    reports_dir: str = Field(default=os.getenv("REPORTS_DIR", "reports/generated"))
    
    @property
    def database_url(self) -> str:
        """Generate database URL for SQLAlchemy"""
        if self.database_type == "sqlite":
            # For SQLite, use a file-based database
            return f"sqlite:///{self.database_path}"
        else:
            # PostgreSQL fallback
            database_user = os.getenv("DATABASE_USER", "postgres")
            database_password = os.getenv("DATABASE_PASSWORD", "")
            database_host = os.getenv("DATABASE_HOST", "localhost")
            database_port = os.getenv("DATABASE_PORT", "5432")
            database_name = os.getenv("DATABASE_NAME", "warehance_returns")
            return f"postgresql://{database_user}:{database_password}@{database_host}:{database_port}/{database_name}"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.app_env == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.app_env == "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
# Create global settings instance
settings = Settings()

# Create necessary directories
def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        settings.upload_dir,
        settings.reports_dir,
        os.path.dirname(settings.log_file) if settings.log_file else "logs"
    ]
    
    for directory in directories:
        if directory:
            os.makedirs(directory, exist_ok=True)

# Initialize directories when module is imported
create_directories()