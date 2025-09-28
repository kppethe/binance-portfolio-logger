# Binance Portfolio Logger - Deployment Guide

This guide provides comprehensive deployment options for the Binance Portfolio Logger, with automated Proxmox installation and manual setup instructions.

## Proxmox Automated Installation (Recommended)

The easiest way to deploy the Binance Portfolio Logger is using our automated Proxmox installation script, similar to the popular Proxmox VE Helper-Scripts.

### Prerequisites

- Proxmox VE 7.0 or higher
- Root access to Proxmox host
- Internet connectivity
- At least 8GB free storage
- 512MB RAM available for the container

### One-Command Installation

1. **Download and run the Proxmox installation script:**
   ```bash
   bash -c "$(wget -qLO - https://raw.githubusercontent.com/your-username/binance-portfolio-logger/main/proxmox-install.sh)"
   ```

   Or if you have the repository locally:
   ```bash
   chmod +x proxmox-install.sh
   sudo ./proxmox-install.sh
   ```

2. **Follow the interactive prompts:**
   - Container ID (auto-detected)
   - Container name and hostname
   - Root password
   - Resource allocation (RAM, CPU, Disk)
   - Network configuration
   - Storage selection

3. **Configure your credentials after installation:**
   ```bash
   pct enter [CONTAINER_ID]
   nano /opt/binance-portfolio-logger/.env
   ```

4. **Add your Google Service Account JSON file:**
   ```bash
   # Copy your service-account.json to the container
   # Place it in: /opt/binance-portfolio-logger/credentials/
   chown binance-logger:binance-logger /opt/binance-portfolio-logger/credentials/service-account.json
   chmod 600 /opt/binance-portfolio-logger/credentials/service-account.json
   ```

5. **Enable and start the service:**
   ```bash
   systemctl enable binance-portfolio-logger.timer
   systemctl start binance-portfolio-logger.timer
   ```

### What the Proxmox Script Does

The automated installation script performs the following:

1. **Container Creation:**
   - Creates Ubuntu 22.04 LXC container
   - Configures networking (DHCP or static IP)
   - Sets up proper resource allocation
   - Enables container auto-start

2. **System Setup:**
   - Updates system packages
   - Installs Python 3.9+, pip, git, cron
   - Creates dedicated `binance-logger` user
   - Sets up proper directory structure and permissions

3. **Application Installation:**
   - Clones/copies application code
   - Creates Python virtual environment
   - Installs all Python dependencies
   - Sets up configuration templates

4. **Service Configuration:**
   - Installs systemd service and timer files
   - Configures log rotation
   - Sets up firewall rules (UFW)
   - Creates monitoring and health check scripts

5. **Security Hardening:**
   - Sets restrictive file permissions
   - Configures non-privileged user execution
   - Enables firewall with minimal required access
   - Removes unnecessary privileges

### Script Options

```bash
# Show help
./proxmox-install.sh --help

# Uninstall (remove container)
./proxmox-install.sh --uninstall
```

## Manual Installation (Alternative)

If you prefer manual installation or are not using Proxmox, follow these steps:

### Manual Installation Steps

#### 1. System Requirements

- **Operating System:** Ubuntu 20.04+ or Debian 11+
- **Python:** 3.9 or higher
- **Memory:** Minimum 512MB RAM
- **Storage:** Minimum 2GB free space
- **Network:** Internet access to Binance API and Google Sheets API

#### 2. Pre-Installation Setup

##### Create Binance API Keys
1. Log into your Binance account
2. Go to API Management
3. Create a new API key with **read-only** permissions
4. Note down the API Key and Secret Key
5. Optionally, restrict API access to your server's IP address

##### Setup Google Sheets Integration
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API
4. Create a Service Account
5. Download the Service Account JSON key file
6. Create a Google Sheet and share it with the service account email

#### 3. Manual Installation

##### Option A: Using Setup Script
```bash
# Download the repository
git clone <repository-url>
cd binance-portfolio-logger

# Make setup script executable
chmod +x setup.sh

# Run setup as root
sudo ./setup.sh
```

##### Option B: Step-by-Step Manual Installation
```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git cron logrotate

# Create application user
sudo useradd -m -s /bin/bash binance-logger

# Create directories
sudo mkdir -p /opt/binance-portfolio-logger/credentials
sudo mkdir -p /var/log/binance-portfolio
sudo chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
sudo chown -R binance-logger:binance-logger /var/log/binance-portfolio

# Setup Python environment
sudo -u binance-logger python3 -m venv /opt/binance-portfolio-logger/venv
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/pip install -r requirements.txt

# Copy application files
sudo cp -r src/* /opt/binance-portfolio-logger/
sudo cp main.py /opt/binance-portfolio-logger/
sudo cp .env.example /opt/binance-portfolio-logger/.env
sudo chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
```

### 4. Configuration

#### Environment Variables
Edit `/opt/binance-portfolio-logger/.env`:
```bash
sudo nano /opt/binance-portfolio-logger/.env
```

Fill in your actual values:
```env
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_api_secret
GOOGLE_SERVICE_ACCOUNT_PATH=/opt/binance-portfolio-logger/credentials/service-account.json
GOOGLE_SPREADSHEET_ID=your_google_sheet_id
```

#### Google Service Account
```bash
# Copy your service account JSON file
sudo cp /path/to/your/service-account.json /opt/binance-portfolio-logger/credentials/
sudo chown binance-logger:binance-logger /opt/binance-portfolio-logger/credentials/service-account.json
sudo chmod 600 /opt/binance-portfolio-logger/credentials/service-account.json
```

### 5. Scheduling Options

#### Option A: Systemd Timer (Recommended)
```bash
# Install service and timer files
sudo cp binance-portfolio-logger.service /etc/systemd/system/
sudo cp binance-portfolio-logger.timer /etc/systemd/system/

# Enable and start the timer
sudo systemctl daemon-reload
sudo systemctl enable binance-portfolio-logger.timer
sudo systemctl start binance-portfolio-logger.timer

# Check timer status
sudo systemctl status binance-portfolio-logger.timer
```

#### Option B: Cron Job
```bash
# Edit crontab for binance-logger user
sudo -u binance-logger crontab -e

# Add this line for daily execution at 8:00 AM:
0 8 * * * /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py >> /var/log/binance-portfolio/cron.log 2>&1
```

### 6. Validation and Testing

#### Run Validation Script
```bash
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python validate_setup.py
```

#### Test Manual Execution
```bash
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py
```

#### Check Logs
```bash
# Application logs
tail -f /var/log/binance-portfolio/portfolio.log

# Error logs
tail -f /var/log/binance-portfolio/errors.log

# Systemd service logs (if using systemd)
journalctl -u binance-portfolio-logger -f
```

## Monitoring and Maintenance

### Log Files
- **Application logs:** `/var/log/binance-portfolio/portfolio.log`
- **Error logs:** `/var/log/binance-portfolio/errors.log`
- **Metrics logs:** `/var/log/binance-portfolio/metrics.log`
- **Cron logs:** `/var/log/binance-portfolio/cron.log`

### Service Management (Systemd)
```bash
# Start service manually
sudo systemctl start binance-portfolio-logger

# Check service status
sudo systemctl status binance-portfolio-logger

# View service logs
journalctl -u binance-portfolio-logger -f

# Check timer status
sudo systemctl list-timers binance-portfolio-logger.timer
```

## Proxmox Container Management

### Container Operations

```bash
# Start container
pct start [CONTAINER_ID]

# Stop container
pct stop [CONTAINER_ID]

# Enter container
pct enter [CONTAINER_ID]

# Check container status
pct status [CONTAINER_ID]

# View container configuration
pct config [CONTAINER_ID]

# Create container backup
vzdump [CONTAINER_ID] --storage [STORAGE_NAME]

# Restore from backup
pct restore [CONTAINER_ID] [BACKUP_FILE] --storage [STORAGE_NAME]
```

### Resource Management

```bash
# Modify container resources
pct set [CONTAINER_ID] --memory 1024 --cores 2

# Resize container disk
pct resize [CONTAINER_ID] rootfs +2G

# View resource usage
pct exec [CONTAINER_ID] -- htop
```

### Network Configuration

```bash
# Change container IP
pct set [CONTAINER_ID] --net0 name=eth0,bridge=vmbr0,ip=192.168.1.100/24,gw=192.168.1.1

# Enable/disable container autostart
pct set [CONTAINER_ID] --onboot 1
```

### Troubleshooting

#### Proxmox-Specific Issues

1. **Container Won't Start**
   ```bash
   # Check container configuration
   pct config [CONTAINER_ID]
   
   # Check Proxmox logs
   journalctl -u pve-container@[CONTAINER_ID]
   
   # Verify storage availability
   pvesm status
   ```

2. **Network Issues in Container**
   ```bash
   # Check bridge configuration
   ip addr show vmbr0
   
   # Test connectivity from host
   ping [CONTAINER_IP]
   
   # Check container network config
   pct exec [CONTAINER_ID] -- ip addr show
   ```

3. **Storage Issues**
   ```bash
   # Check storage usage
   df -h
   
   # Check Proxmox storage
   pvesm status
   
   # Verify container disk usage
   pct exec [CONTAINER_ID] -- df -h
   ```

#### Application-Specific Issues

1. **Permission Denied Errors**
   ```bash
   # Fix file permissions (run inside container)
   pct exec [CONTAINER_ID] -- bash -c "
   chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
   chmod 600 /opt/binance-portfolio-logger/.env
   chmod 600 /opt/binance-portfolio-logger/credentials/*
   "
   ```

2. **API Connection Issues**
   ```bash
   # Test network connectivity (from container)
   pct exec [CONTAINER_ID] -- curl -I https://api.binance.com/api/v3/ping
   pct exec [CONTAINER_ID] -- curl -I https://sheets.googleapis.com
   
   # Check firewall rules
   pct exec [CONTAINER_ID] -- ufw status
   ```

3. **Python Import Errors**
   ```bash
   # Reinstall dependencies (from container)
   pct exec [CONTAINER_ID] -- bash -c "
   cd /opt/binance-portfolio-logger
   sudo -u binance-logger ./venv/bin/pip install --upgrade pip
   sudo -u binance-logger ./venv/bin/pip install -r requirements.txt
   "
   ```

4. **Service Issues**
   ```bash
   # Check service status
   pct exec [CONTAINER_ID] -- systemctl status binance-portfolio-logger.timer
   
   # View service logs
   pct exec [CONTAINER_ID] -- journalctl -u binance-portfolio-logger -f
   
   # Restart service
   pct exec [CONTAINER_ID] -- systemctl restart binance-portfolio-logger.timer
   ```

5. **Google Sheets Access Issues**
   - Verify the service account email has access to your spreadsheet
   - Check that the Google Sheets API is enabled in your Google Cloud project
   - Ensure the service account JSON file is valid and has correct permissions

#### Log Analysis

```bash
# Check application logs (from container)
pct exec [CONTAINER_ID] -- tail -f /var/log/binance-portfolio/portfolio.log

# Check for errors in the last 24 hours
pct exec [CONTAINER_ID] -- grep -i error /var/log/binance-portfolio/portfolio.log | tail -20

# Check execution history
pct exec [CONTAINER_ID] -- grep "Execution completed" /var/log/binance-portfolio/portfolio.log | tail -10

# View systemd logs
pct exec [CONTAINER_ID] -- journalctl -u binance-portfolio-logger --since "24 hours ago"
```

#### Performance Monitoring

```bash
# Monitor container resource usage
pct exec [CONTAINER_ID] -- htop

# Check memory usage
pct exec [CONTAINER_ID] -- free -h

# Check disk usage
pct exec [CONTAINER_ID] -- df -h

# Monitor network connections
pct exec [CONTAINER_ID] -- netstat -tulpn
```

## Security Considerations

1. **File Permissions:**
   - Application directory: 750 (binance-logger:binance-logger)
   - Credentials directory: 700 (binance-logger:binance-logger)
   - Environment file: 600 (binance-logger:binance-logger)
   - Service account JSON: 600 (binance-logger:binance-logger)

2. **API Security:**
   - Use read-only Binance API keys
   - Consider IP whitelisting for API access
   - Regularly rotate API keys

3. **System Security:**
   - Run application as non-privileged user
   - Keep system and dependencies updated
   - Monitor logs for suspicious activity

## Backup and Recovery

### Configuration Backup
```bash
# Backup configuration and credentials
sudo tar -czf binance-portfolio-backup-$(date +%Y%m%d).tar.gz \
  /opt/binance-portfolio-logger/.env \
  /opt/binance-portfolio-logger/credentials/
```

### Log Backup
Logs are automatically rotated by logrotate. Historical data is preserved in Google Sheets.

### Recovery
```bash
# Restore from backup
sudo tar -xzf binance-portfolio-backup-YYYYMMDD.tar.gz -C /
sudo chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
```

## Updates and Maintenance

### Updating the Application
```bash
# Stop the service
sudo systemctl stop binance-portfolio-logger.timer

# Update code
cd /path/to/source
git pull

# Copy updated files
sudo cp -r src/* /opt/binance-portfolio-logger/
sudo cp main.py /opt/binance-portfolio-logger/
sudo chown -R binance-logger:binance-logger /opt/binance-portfolio-logger

# Update dependencies if needed
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/pip install -r requirements.txt

# Restart the service
sudo systemctl start binance-portfolio-logger.timer
```

### System Maintenance
```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Clean old logs (if needed)
sudo find /var/log/binance-portfolio -name "*.log.*" -mtime +30 -delete

# Check disk usage
df -h /var/log/binance-portfolio
```