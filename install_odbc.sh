#!/bin/bash
# Install ODBC drivers for Azure SQL on Linux

echo "=== Installing ODBC Drivers for SQL Server ==="

# Check if we're on Azure App Service
if [ ! -z "$WEBSITE_INSTANCE_ID" ]; then
    echo "Running on Azure App Service"
    
    # Check if drivers are already installed
    if odbcinst -q -d 2>/dev/null | grep -q "ODBC Driver.*SQL Server"; then
        echo "ODBC drivers already installed"
    else
        echo "Attempting to install ODBC drivers..."
        
        # Try to use apt-get if available (may not have permissions)
        if command -v apt-get &> /dev/null; then
            # Add Microsoft's GPG key and repository
            curl -sSL https://packages.microsoft.com/keys/microsoft.asc 2>/dev/null | apt-key add - 2>/dev/null || true
            curl -sSL https://packages.microsoft.com/config/debian/11/prod.list 2>/dev/null > /etc/apt/sources.list.d/mssql-release.list 2>/dev/null || true
            
            # Update and install
            apt-get update -qq 2>/dev/null || true
            ACCEPT_EULA=Y apt-get install -y -qq msodbcsql17 msodbcsql18 unixodbc-dev 2>/dev/null || true
        fi
        
        # If apt-get fails, try alternative method
        if [ $? -ne 0 ]; then
            echo "apt-get failed, trying alternative installation..."
            
            # Download and extract manually
            mkdir -p /tmp/odbc_install
            cd /tmp/odbc_install
            
            # Try to download the .deb package directly
            wget -q https://packages.microsoft.com/debian/11/prod/pool/main/m/msodbcsql17/msodbcsql17_17.10.5.1-1_amd64.deb || true
            wget -q https://packages.microsoft.com/debian/11/prod/pool/main/m/msodbcsql18/msodbcsql18_18.3.2.1-1_amd64.deb || true
            
            # Extract without installing (in case we don't have dpkg permissions)
            if [ -f msodbcsql17_17.10.5.1-1_amd64.deb ]; then
                ar x msodbcsql17_17.10.5.1-1_amd64.deb
                tar -xf data.tar.* -C / 2>/dev/null || true
            fi
            
            if [ -f msodbcsql18_18.3.2.1-1_amd64.deb ]; then
                ar x msodbcsql18_18.3.2.1-1_amd64.deb
                tar -xf data.tar.* -C / 2>/dev/null || true
            fi
            
            cd /
            rm -rf /tmp/odbc_install
        fi
    fi
    
    # Configure ODBC
    echo "Configuring ODBC..."
    
    # Create odbcinst.ini if it doesn't exist
    if [ ! -f /etc/odbcinst.ini ]; then
        cat > /etc/odbcinst.ini << 'EOL'
[ODBC Driver 17 for SQL Server]
Description=Microsoft ODBC Driver 17 for SQL Server
Driver=/opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17.10.so.5.1
UsageCount=1

[ODBC Driver 18 for SQL Server]
Description=Microsoft ODBC Driver 18 for SQL Server
Driver=/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.3.so.2.1
UsageCount=1
EOL
    fi
    
    # Set environment variables
    export ODBCSYSINI=/etc
    export ODBCINI=/etc/odbc.ini
    
    # Verify installation
    echo "Checking ODBC installation..."
    odbcinst -q -d || echo "odbcinst not available"
    
    echo "Available ODBC drivers:"
    python -c "import pyodbc; print(pyodbc.drivers())" 2>/dev/null || echo "Could not list drivers from Python"
    
    echo "=== ODBC Driver Installation Complete ==="
else
    echo "Not running on Azure App Service, skipping ODBC installation"
fi