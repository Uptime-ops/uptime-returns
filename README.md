# Warehance Returns Management System

A comprehensive system for managing and tracking returns from the Warehance API, with features for filtering, email sharing, and analytics.

## Features

- **Automated API Sync**: Fetch and store returns data from Warehance API with pagination support
- **Web Dashboard**: Interactive HTML interface with real-time filtering and search
- **Client Filtering**: Filter returns by client, warehouse, status, and date ranges
- **Email Sharing**: Track which returns have been shared with clients and prevent duplicate shares
- **Export Functionality**: Export returns data to CSV or Excel format
- **Analytics Dashboard**: Visualize return trends, reasons, and patterns
- **Share Tracking**: Keep detailed records of what was shared with each client and when

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Git (optional)

## Installation

### 1. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup PostgreSQL Database

1. Install PostgreSQL if not already installed
2. Create a new database:

```sql
CREATE DATABASE warehance_returns;
```

3. Create database tables:

```bash
# Using psql
psql -U your_username -d warehance_returns -f database/schema.sql

# Or using Python
python -c "from database.models import init_database; init_database()"
```

### 3. Configure Environment

1. Update the `.env` file in the `config` folder:

```env
# Update database credentials
DATABASE_USER=your_db_user
DATABASE_PASSWORD=your_db_password

# Email configuration (for sending reports)
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com

# The API key is already configured
```

**Note**: For Gmail, you'll need to use an App Password instead of your regular password. Enable 2FA and generate an app password at https://myaccount.google.com/apppasswords

## Running the System

### 1. Initial Data Sync

First, sync all returns from the Warehance API:

```bash
python scripts/sync_returns.py
```

This will fetch all returns and store them in your PostgreSQL database.

### 2. Start the Web Application

```bash
cd web
python app.py
```

Or use uvicorn for production:

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at: http://localhost:8000

### 3. Send Email Reports (Optional)

To send pending email shares:

```bash
python scripts/email_sender.py
```

## Usage Guide

### Dashboard Overview

1. Navigate to http://localhost:8000
2. The dashboard shows:
   - Total returns count
   - Pending vs processed returns
   - Unshared returns count
   - Monthly trends
   - Status distribution

### Managing Returns

1. Click on "Returns" in the navigation
2. Use filters to find specific returns:
   - Select client from dropdown
   - Choose date range
   - Filter by status (Pending/Processed)
   - Check "Show Unshared Only" to see returns not yet sent to clients
3. Click the eye icon to view detailed return information
4. Use "Export" button to download filtered data

### Creating Email Shares

1. Go to "Email Shares" section
2. Click "Create New Share"
3. Fill in:
   - Client to share with
   - Date range of returns
   - Recipient email address
   - Optional subject and notes
4. The system will:
   - Find all unshared returns for that client in the date range
   - Create a share record
   - Track which returns were included
   - Prevent those returns from being shared again

### Syncing Data

- Click "Sync Now" in the navigation to manually trigger a sync
- The system will fetch new returns from the API
- A notification will show sync progress

### Analytics

View analytics by clicking "Analytics" in the navigation:
- Top return reasons
- Returns by client
- Returns by warehouse
- Trend analysis

## Scheduling Automated Tasks

### Windows (Task Scheduler)

1. Create a batch file `sync_returns.bat`:
```batch
@echo off
cd /d "C:\Users\ccayo\OneDrive\Desktop\Warehance Returns"
call venv\Scripts\activate
python scripts\sync_returns.py
```

2. Open Task Scheduler and create a task to run this batch file hourly

### Linux/Mac (Cron)

Add to crontab (`crontab -e`):
```bash
# Sync returns every hour
0 * * * * cd /path/to/warehance-returns && /path/to/venv/bin/python scripts/sync_returns.py

# Send pending emails daily at 9 AM
0 9 * * * cd /path/to/warehance-returns && /path/to/venv/bin/python scripts/email_sender.py
```

## API Endpoints

The FastAPI backend provides these endpoints:

- `GET /` - Main dashboard
- `GET /api/health` - Health check
- `GET /api/dashboard/stats` - Dashboard statistics
- `POST /api/returns/search` - Search and filter returns
- `GET /api/returns/{id}` - Get return details
- `GET /api/clients` - List all clients
- `GET /api/warehouses` - List all warehouses
- `POST /api/email-shares/create` - Create email share
- `GET /api/email-shares/history` - Email share history
- `POST /api/sync/trigger` - Trigger manual sync
- `GET /api/export/returns` - Export returns to CSV/Excel
- `GET /api/analytics/return-reasons` - Return reasons analytics

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL is running: `pg_ctl status` or `sudo service postgresql status`
- Check credentials in `.env` file
- Ensure database exists: `psql -U postgres -l`

### API Sync Issues
- Verify API key is correct in `.env`
- Check internet connection
- Look at logs in `logs/app.log`
- Try running with debug: `python scripts/sync_returns.py`

### Email Sending Issues
- Verify SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password
- Check if "Less secure app access" is needed (not recommended)
- Review email logs in `logs/app.log`

### Web Interface Issues
- Clear browser cache
- Check browser console for errors (F12)
- Verify all JavaScript libraries are loading
- Ensure port 8000 is not blocked

## Security Notes

- **Never commit** the `.env` file with real credentials
- Use environment variables in production
- Set up HTTPS with SSL certificates for production
- Implement authentication for the web interface in production
- Regularly backup your PostgreSQL database
- Keep the API key secure and rotate if compromised

## Future Enhancements

Consider adding:
- User authentication and role-based access
- Automated email scheduling with templates per client
- Webhook integration for real-time updates
- Mobile-responsive improvements
- Advanced analytics with predictive insights
- Integration with other warehouse systems
- Automated report generation on schedule
- Return processing workflow management

## Support

For issues or questions:
1. Check the logs in `logs/app.log`
2. Review the troubleshooting section
3. Verify all dependencies are installed
4. Ensure database schema is up to date

## License

Private use only. All rights reserved.