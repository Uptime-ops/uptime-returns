# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Warehance Returns - A comprehensive returns management system integrated with the Warehance API for tracking and analyzing product returns.

## Project Status

**Current Version:** V15 - Fully functional returns management system with Azure SQL compatibility
**Server Port:** 8015 (http://localhost:8015)
**Main Application:** web/app_v2.py (current primary with Azure SQL support)
**Backup Applications:** web/enhanced_app.py, web/simple_app.py

### Technology Stack
- **Backend**: FastAPI (Python)
- **Database**: Dual-compatible (SQLite for local development, Azure SQL Server for production)
- **Frontend**: HTML/JavaScript with Bootstrap 5
- **API Integration**: Warehance API (returns, products, orders endpoints)
- **CSV Export**: StreamingResponse with custom formatting
- **Cloud Platform**: Azure App Service with GitHub Actions CI/CD
- **Security**: Environment variable configuration for API keys

### Project Structure
```
Warehance Returns/
├── web/                    # Web application files
│   ├── enhanced_app.py    # Main FastAPI application (current)
│   ├── simple_app.py      # Simplified backup version
│   ├── templates/         # HTML templates
│   │   └── index.html    # Main dashboard UI
│   └── static/           # Static assets
├── database/             # Database models and configurations
├── scripts/             # Utility scripts
├── config/              # Configuration files
├── logs/               # Application logs
└── warehance_returns.db  # SQLite database
```

## Key Features Implemented

### 1. Returns Management
- Full CRUD operations for returns
- Real-time sync with Warehance API (690+ returns with pagination)
- Return status tracking and filtering
- Search functionality with multiple filters
- Detailed return modal with product information

### 2. Product Integration
- Fetches and stores 3,500+ products from Warehance API
- Links products to return items with quantities
- Handles bundle items with proper quantity display
- Shows order items as proxy when return items unavailable (for older returns)
- Real product names and SKUs displayed

### 3. Order Integration
- Fetches associated order details for each return
- Displays order items with quantities
- Handles bundle items (items with bundle_order_item_id)
- Extracts customer name from ship_to_address JSON field

### 4. CSV Export (Custom Format)
- One row per product line item
- Columns: Client, Customer Name, Order Date, Return Date, Order Number, Item Name, Order Qty, Return Qty, Reason for Return
- Supports bulk export with proper data formatting
- StreamingResponse for efficient large file handling

### 5. Sync System
- Manual sync trigger with progress display
- Shows sync status (last sync time, items processed) near Sync Now button
- Implements API pagination to fetch all returns (not just first 100)
- Background task processing for non-blocking sync
- Real-time progress updates during sync

### 6. Analytics Dashboard
- Returns by status visualization (charts)
- Returns over time chart
- Top return reasons analysis
- Top returned products listing
- Dashboard statistics (total returns, processed, pending)

## Database Schema

- **returns**: Core return records from Warehance (690+ records)
- **clients**: Customer/client information (7+ clients)
- **warehouses**: Warehouse locations
- **orders**: Associated order data with customer details
- **products**: Product catalog (3,500+ items)
- **return_items**: Individual items in returns with quantities and reasons

## API Endpoints

### Core Endpoints
- `GET /`: Main dashboard interface
- `GET /api/returns`: List all returns with filtering and pagination
- `GET /api/returns/{id}`: Get specific return details with items
- `POST /api/sync/trigger`: Trigger manual sync with Warehance
- `GET /api/sync/status`: Get current sync status
- `GET /api/returns/export/csv`: Export returns as CSV (custom format)

### Analytics Endpoints
- `GET /api/analytics/returns-by-status`: Returns breakdown by status
- `GET /api/analytics/returns-over-time`: Time series data for charts
- `GET /api/analytics/top-return-reasons`: Most common return reasons
- `GET /api/analytics/top-returned-products`: Products with highest return rates

### Support Endpoints
- `GET /api/clients`: List all clients
- `GET /api/warehouses`: List all warehouses
- `GET /api/dashboard/stats`: Dashboard statistics

## Known Issues and Solutions

### 1. Port Conflicts
- Application has progressed through ports 8000-8015 due to conflicts
- Current stable port: 8015
- Solution: Use `netstat -ano | findstr :PORT` to check port usage
- Multiple background processes may still be running on older ports

### 2. Database Path Issues
- Error: "no such table: returns"
- Solution: Database path must be '../warehance_returns.db' (relative to web folder)
- Fixed by correcting path in enhanced_app.py

### 3. API Response Structure
- Older returns (before Sept 2025) have "items": null in API response
- Solution: Fetch associated order to display order items as proxy
- Newer returns (Sept 2025+) have complete product information with quantities

### 4. Bundle Items Display
- Bundle items show 0 quantity in API response
- Solution: Detect bundle_order_item_id and set display quantity to 1
- Frontend updated to handle this case properly

### 5. SQLAlchemy Issues
- Original app.py had Query.order_by() issues with LIMIT
- Solution: Switched to raw SQL queries in enhanced_app.py

### 6. Azure SQL Server Compatibility (RESOLVED - V11-V15)
- **Date Conversion Errors**: API dates from Warehance need conversion for SQL Server
- **SQL Parameterization**: Azure SQL requires `%s` placeholders vs SQLite `?`
- **LIMIT Syntax**: Azure SQL uses `OFFSET/FETCH` instead of `LIMIT/OFFSET`
- **Column Naming**: Azure SQL requires aliases for aggregate functions like `COUNT(*)`
- **Empty IN Clauses**: Must check for empty lists before generating `WHERE id IN ()`
- **Solution**: Implemented dual-compatibility functions in app_v2.py

## Development Guidelines

### Running the Application

**Local Development:**
```bash
cd web
python app_v2.py
# Access at http://localhost:8015
```

**Azure Production:**
- Deployed via GitHub Actions to Azure App Service
- Environment variables configured in Azure Application Settings
- Automatic deployment on push to main branch

### Sync Process
1. Click "Sync Now" button in UI
2. System fetches all returns with pagination (100 items per page)
3. Fetches associated products and orders
4. Updates local database with latest data
5. Shows progress in real-time with item counts
6. Displays last sync time and status

### CSV Export Format Requirements
- One row per product line item (not per return)
- Must include all specified columns in order
- Customer name extracted from ship_to_address JSON
- Dates formatted for readability (ISO format)
- Handles null/missing data gracefully

### Testing Checklist
- [ ] Sync functionality with large datasets (690+ returns)
- [ ] CSV export format matches client requirements
- [ ] Pagination works for API calls
- [ ] Bundle items display correctly (quantity = 1)
- [ ] Return details modal shows all items
- [ ] Sync status updates in real-time
- [ ] All charts and analytics load properly

## Important Configuration

### API Token
- **SECURITY FIXED**: Warehance API token now uses environment variables
- Local development: Set `WAREHANCE_API_KEY` environment variable
- Azure production: Configured in Azure Application Settings
- **No longer hardcoded** in source code for security

### Current Data Statistics
- **Total Returns**: 977+ available via Warehance API
- **Active Clients**: 7+ (Euro Brands, MRG Brands, Fast Fwd, etc.)
- **Products**: 3,500+ synced from Warehance
- **Database**: Dual-platform support (SQLite + Azure SQL)
- **Azure Production**: Fully deployed and operational

## Recent Updates and Fixes

### Legacy Updates (Pre-Azure)
1. **CSV Export Enhancement**: Modified to show one row per line item with specific columns
2. **Sync Pagination**: Fixed to fetch all 690+ returns (was limited to 100)
3. **Sync Status Display**: Added real-time status near Sync Now button
4. **Bundle Items Fix**: Corrected quantity display for bundle items
5. **Product Integration**: Integrated real product data from Warehance API
6. **Customer Name**: Extracted from ship_to_address JSON field
7. **Order Items Display**: Shows order items when return items are null
8. **Port Migration**: Moved from 8000→8015 due to conflicts
9. **Frontend Updates**: Fixed Return Details modal to show both notes and items
10. **Database Path Fix**: Corrected relative path to database file

### Azure SQL Compatibility (V11-V15) - September 2025
11. **V11 - Date Conversion**: Added `convert_date_for_sql()` function to handle Warehance API date formats for Azure SQL Server
12. **V12 - SQL Parameterization**: Attempted incorrect `%s` → `?` conversion (reverted)
13. **V13 - Empty IN Clause Fix**: Added null checks to prevent `WHERE id IN ()` syntax errors
14. **V14 - LIMIT Syntax**: Added `format_limit_clause()` for Azure SQL `OFFSET/FETCH` vs SQLite `LIMIT/OFFSET`
15. **V14 - Column Naming**: Added aliases for `COUNT(*)` queries to prevent "columns with no names" errors
16. **V15 - Final Parameterization**: Fixed remaining `?` placeholders in sync queries (clients, warehouses, returns)
17. **Security Enhancement**: Moved API keys to environment variables, removed from source code
18. **GitHub Actions**: Enhanced CI/CD pipeline with proper virtual environment handling
19. **Dual Database Support**: Single codebase now supports both SQLite (local) and Azure SQL (production)

## Azure SQL Compatibility Functions

The application includes several helper functions in `app_v2.py` for database compatibility:

### Core Compatibility Functions
```python
def get_param_placeholder():
    """Returns '%s' for Azure SQL, '?' for SQLite"""
    return "%s" if USE_AZURE_SQL else "?"

def format_in_clause(count):
    """Formats IN clause with correct placeholders"""
    placeholder = get_param_placeholder()
    return ','.join([placeholder] * count)

def format_limit_clause(limit, offset=0):
    """Formats LIMIT clause with correct syntax"""
    if USE_AZURE_SQL:
        return f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
    else:
        return f"LIMIT {limit} OFFSET {offset}" if offset > 0 else f"LIMIT {limit}"

def convert_date_for_sql(date_string):
    """Converts API dates to SQL Server compatible format"""
    # Handles multiple Warehance API date formats
    # Returns YYYY-MM-DD HH:MM:SS format for Azure SQL
```

### Usage Guidelines
- **Always use these functions** for new SQL queries
- **Test both databases** when making SQL changes
- **Add column aliases** for aggregate functions (e.g., `COUNT(*) as total_count`)
- **Check for empty lists** before generating IN clauses

## Azure Deployment Information

### GitHub Repository
- **Public Repository**: https://github.com/Uptime-ops/uptime-returns
- **Main Branch**: Automatic deployment to Azure on push
- **Security**: API keys stored in GitHub Secrets and Azure Application Settings

### Azure Configuration
- **Platform**: Azure App Service 
- **Database**: Azure SQL Server (`uptime-returns-sql.database.windows.net`)
- **Environment Variables**: Configured in Azure Application Settings
- **Deployment**: GitHub Actions workflow (`.github/workflows/main_uptime-returns.yml`)

### Version History
- **V11**: Date conversion for Azure SQL
- **V12**: Incorrect parameterization attempt (reverted)  
- **V13**: Empty IN clause fixes
- **V14**: LIMIT syntax and column naming
- **V15**: Final parameterization fixes - **CURRENT PRODUCTION VERSION**

## Notes

- This project directory is located in OneDrive, which may have sync implications
- Multiple background processes may be running on different ports (check and kill if needed)
- Returns data includes both historical (with limited info) and recent data (with full details)
- API updates are not retroactive - older returns maintain their original structure
- **Azure SQL compatibility is complete** - sync should work with all 977+ returns from Warehance API