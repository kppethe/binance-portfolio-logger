# Binance Portfolio Logger - Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues with the Binance Portfolio Logger system.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Configuration Problems](#configuration-problems)
- [API Connection Issues](#api-connection-issues)
- [Google Sheets Problems](#google-sheets-problems)
- [Service and Scheduling Issues](#service-and-scheduling-issues)
- [Performance Problems](#performance-problems)
- [Security and Permission Issues](#security-and-permission-issues)
- [Proxmox-Specific Issues](#proxmox-specific-issues)
- [Log Analysis](#log-analysis)
- [Recovery Procedures](#recovery-procedures)

---

## Quick Diagnostics

### Health Check Script

Run the built-in health check to quickly identify issues:

```bash
# From container or system
cd /opt/binance-portfolio-logger
sudo -u binance-logger ./venv/bin/python health_check.py
```

### System Status Check

```bash
# Check service status
systemctl status binance-portfolio-logger.timer
systemctl status binance-portfolio-logger.service

# Check recent logs
journalctl -u binance-portfolio-logger --since "1 hour ago"

# Test manual execution
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py
```

### Network Connectivity Test

```bash
# Test API endpoints
curl -I https://api.binance.com/api/v3/ping
curl -I https://sheets.googleapis.com

# Test DNS resolution
nslookup api.binance.com
nslookup sheets.googleapis.com
```

---

## Installation Issues

### Proxmox Installation Script Failures

#### Container Creation Failed

**Symptoms:**
- Script exits with "Failed to create container"
- Container ID already exists error

**Solutions:**
```bash
# Check if container ID is already in use
pct status [CONTAINER_ID]

# List all containers
pct list

# Use different container ID
./proxmox-install.sh
# Enter different ID when prompted
```

#### Template Download Failed

**Symptoms:**
- "Failed to download container template"
- Network timeout during template download

**Solutions:**
```bash
# Check internet connectivity
ping 8.8.8.8

# Manually download template
pveam update
pveam available | grep ubuntu-22.04
pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.zst

# Check storage space
df -h
```

#### Python Dependencies Installation Failed

**Symptoms:**
- pip install errors
- Module not found errors

**Solutions:**
```bash
# Update pip and try again
pct exec [CONTAINER_ID] -- bash -c "
cd /opt/binance-portfolio-logger
sudo -u binance-logger ./venv/bin/pip install --upgrade pip
sudo -u binance-logger ./venv/bin/pip install -r requirements.txt --no-cache-dir
"

# Check Python version
pct exec [CONTAINER_ID] -- python3 --version

# Install system dependencies if missing
pct exec [CONTAINER_ID] -- apt update
pct exec [CONTAINER_ID] -- apt install -y python3-dev build-essential
```

### Manual Installation Issues

#### Permission Denied During Setup

**Symptoms:**
- Cannot create directories
- Cannot copy files

**Solutions:**
```bash
# Ensure running as root
sudo su -

# Check current user
whoami

# Fix ownership after installation
chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
chown -R binance-logger:binance-logger /var/log/binance-portfolio
```

#### Python Virtual Environment Issues

**Symptoms:**
- venv creation fails
- Module import errors

**Solutions:**
```bash
# Install python3-venv if missing
apt install python3-venv python3-pip

# Recreate virtual environment
rm -rf /opt/binance-portfolio-logger/venv
sudo -u binance-logger python3 -m venv /opt/binance-portfolio-logger/venv

# Upgrade pip before installing packages
sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/pip install --upgrade pip
```

---

## Configuration Problems

### Environment Variables Not Loading

**Symptoms:**
- "BINANCE_API_KEY not found" errors
- Configuration validation failures

**Diagnosis:**
```bash
# Check .env file exists and has correct permissions
ls -la /opt/binance-portfolio-logger/.env

# Verify file contents (be careful not to expose secrets)
sudo -u binance-logger head -1 /opt/binance-portfolio-logger/.env
```

**Solutions:**
```bash
# Fix file permissions
chown binance-logger:binance-logger /opt/binance-portfolio-logger/.env
chmod 600 /opt/binance-portfolio-logger/.env

# Verify environment variables are set
sudo -u binance-logger bash -c "cd /opt/binance-portfolio-logger && python3 -c 'import os; print(os.getenv(\"BINANCE_API_KEY\", \"NOT_SET\"))'"
```

### Invalid Configuration Values

**Symptoms:**
- Validation errors on startup
- "Invalid configuration" messages

**Common Issues and Fixes:**

1. **Missing Google Spreadsheet ID:**
   ```bash
   # Check if GOOGLE_SPREADSHEET_ID is set
   grep GOOGLE_SPREADSHEET_ID /opt/binance-portfolio-logger/.env
   
   # Extract ID from Google Sheets URL
   # URL: https://docs.google.com/spreadsheets/d/1ABC123DEF456/edit
   # ID: 1ABC123DEF456
   ```

2. **Incorrect Service Account Path:**
   ```bash
   # Verify file exists
   ls -la /opt/binance-portfolio-logger/credentials/service-account.json
   
   # Check JSON validity
   python3 -m json.tool /opt/binance-portfolio-logger/credentials/service-account.json
   ```

3. **Invalid Log File Path:**
   ```bash
   # Ensure log directory exists
   mkdir -p /var/log/binance-portfolio
   chown binance-logger:binance-logger /var/log/binance-portfolio
   ```

---

## API Connection Issues

### Binance API Problems

#### Authentication Failures

**Symptoms:**
- "Invalid API key" errors
- 401 Unauthorized responses

**Diagnosis:**
```bash
# Test API key validity
curl -H "X-MBX-APIKEY: YOUR_API_KEY" "https://api.binance.com/api/v3/account"
```

**Solutions:**
1. **Verify API Key and Secret:**
   - Check for extra spaces or characters
   - Ensure API key has read permissions
   - Verify API key is not expired

2. **Check IP Restrictions:**
   - If IP whitelisting is enabled, add server IP
   - Test from the same IP as the server

3. **API Key Permissions:**
   - Ensure "Enable Reading" is checked
   - "Enable Spot & Margin Trading" should be unchecked
   - "Enable Futures" should be unchecked (unless needed)

#### Rate Limiting Issues

**Symptoms:**
- "Rate limit exceeded" errors
- 429 HTTP status codes

**Solutions:**
```bash
# Check current rate limit status
curl -I "https://api.binance.com/api/v3/exchangeInfo"

# Implement delays in configuration
# Add to .env file:
echo "API_DELAY_SECONDS=1" >> /opt/binance-portfolio-logger/.env
```

#### Network Connectivity Issues

**Symptoms:**
- Connection timeout errors
- DNS resolution failures

**Diagnosis:**
```bash
# Test basic connectivity
ping api.binance.com

# Test HTTPS connectivity
curl -I https://api.binance.com/api/v3/ping

# Check DNS resolution
nslookup api.binance.com

# Test from container (if using Proxmox)
pct exec [CONTAINER_ID] -- curl -I https://api.binance.com/api/v3/ping
```

**Solutions:**
1. **Firewall Issues:**
   ```bash
   # Check UFW status
   ufw status
   
   # Allow outbound HTTPS
   ufw allow out 443/tcp
   ```

2. **DNS Issues:**
   ```bash
   # Update DNS servers
   echo "nameserver 8.8.8.8" >> /etc/resolv.conf
   echo "nameserver 1.1.1.1" >> /etc/resolv.conf
   ```

3. **Proxy Configuration:**
   ```bash
   # If behind corporate proxy, configure environment
   export https_proxy=http://proxy.company.com:8080
   export http_proxy=http://proxy.company.com:8080
   ```

---

## Google Sheets Problems

### Authentication Issues

**Symptoms:**
- "Authentication failed" errors
- "Service account not found" errors

**Diagnosis:**
```bash
# Verify service account file exists and is valid JSON
ls -la /opt/binance-portfolio-logger/credentials/service-account.json
python3 -m json.tool /opt/binance-portfolio-logger/credentials/service-account.json
```

**Solutions:**

1. **Service Account File Issues:**
   ```bash
   # Check file permissions
   chmod 600 /opt/binance-portfolio-logger/credentials/service-account.json
   chown binance-logger:binance-logger /opt/binance-portfolio-logger/credentials/service-account.json
   
   # Verify JSON structure
   python3 -c "
   import json
   with open('/opt/binance-portfolio-logger/credentials/service-account.json') as f:
       data = json.load(f)
       print('Service account email:', data.get('client_email'))
       print('Project ID:', data.get('project_id'))
   "
   ```

2. **Google Cloud Project Configuration:**
   - Ensure Google Sheets API is enabled
   - Verify service account has proper roles
   - Check if service account key is active

3. **Spreadsheet Access:**
   ```bash
   # Test spreadsheet access
   python3 -c "
   import gspread
   gc = gspread.service_account('/opt/binance-portfolio-logger/credentials/service-account.json')
   sheet = gc.open_by_key('YOUR_SPREADSHEET_ID')
   print('Spreadsheet title:', sheet.title)
   "
   ```

### Quota and Rate Limiting

**Symptoms:**
- "Quota exceeded" errors
- "Rate limit exceeded" for Google Sheets API

**Solutions:**
1. **Check API Quotas:**
   - Visit Google Cloud Console
   - Check APIs & Services > Quotas
   - Monitor Google Sheets API usage

2. **Implement Retry Logic:**
   - The application includes built-in retry logic
   - Increase retry delays if needed

3. **Reduce API Calls:**
   - Batch operations where possible
   - Cache data when appropriate

### Spreadsheet and Worksheet Issues

**Symptoms:**
- "Spreadsheet not found" errors
- "Worksheet not found" errors

**Solutions:**

1. **Verify Spreadsheet ID:**
   ```bash
   # Extract ID from URL
   # https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   grep GOOGLE_SPREADSHEET_ID /opt/binance-portfolio-logger/.env
   ```

2. **Check Worksheet Name:**
   ```bash
   # Default worksheet name is "Binance Portfolio"
   # Verify it exists or update configuration
   grep GOOGLE_SHEET_NAME /opt/binance-portfolio-logger/.env
   ```

3. **Share Spreadsheet:**
   - Share spreadsheet with service account email
   - Grant "Editor" permissions
   - Service account email is in the JSON file: `client_email` field

---

## Service and Scheduling Issues

### Systemd Service Problems

**Symptoms:**
- Service fails to start
- Timer not triggering execution

**Diagnosis:**
```bash
# Check service status
systemctl status binance-portfolio-logger.service
systemctl status binance-portfolio-logger.timer

# View service logs
journalctl -u binance-portfolio-logger -f

# Check timer schedule
systemctl list-timers binance-portfolio-logger.timer
```

**Solutions:**

1. **Service File Issues:**
   ```bash
   # Verify service files exist
   ls -la /etc/systemd/system/binance-portfolio-logger.*
   
   # Reload systemd configuration
   systemctl daemon-reload
   
   # Enable and start timer
   systemctl enable binance-portfolio-logger.timer
   systemctl start binance-portfolio-logger.timer
   ```

2. **Path Issues in Service File:**
   ```bash
   # Check service file paths
   cat /etc/systemd/system/binance-portfolio-logger.service
   
   # Verify Python executable path
   ls -la /opt/binance-portfolio-logger/venv/bin/python
   
   # Verify main.py exists
   ls -la /opt/binance-portfolio-logger/main.py
   ```

3. **User and Permission Issues:**
   ```bash
   # Verify binance-logger user exists
   id binance-logger
   
   # Test manual execution as service user
   sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py
   ```

### Cron Job Issues (Alternative Scheduling)

**Symptoms:**
- Cron job not executing
- No output in cron logs

**Diagnosis:**
```bash
# Check cron service
systemctl status cron

# View cron logs
grep CRON /var/log/syslog | tail -20

# Check user's crontab
sudo -u binance-logger crontab -l
```

**Solutions:**
```bash
# Ensure cron service is running
systemctl enable cron
systemctl start cron

# Add logging to cron job
sudo -u binance-logger crontab -e
# Add: 0 8 * * * /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py >> /var/log/binance-portfolio/cron.log 2>&1

# Test cron job manually
sudo -u binance-logger bash -c "cd /opt/binance-portfolio-logger && ./venv/bin/python main.py"
```

---

## Performance Problems

### Slow Execution Times

**Symptoms:**
- Execution takes longer than 30 seconds
- Timeout errors

**Diagnosis:**
```bash
# Time the execution
time sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py

# Check system resources
htop
free -h
df -h
```

**Solutions:**

1. **Network Latency:**
   ```bash
   # Test API response times
   time curl -I https://api.binance.com/api/v3/ping
   time curl -I https://sheets.googleapis.com
   
   # Consider using different DNS servers
   echo "nameserver 1.1.1.1" > /etc/resolv.conf
   ```

2. **Large Portfolio Optimization:**
   - Reduce number of API calls
   - Implement caching for price data
   - Filter out very small balances

3. **System Resource Issues:**
   ```bash
   # Increase container resources (Proxmox)
   pct set [CONTAINER_ID] --memory 1024 --cores 2
   
   # Check for memory leaks
   ps aux | grep python
   ```

### Memory Usage Issues

**Symptoms:**
- Out of memory errors
- System becomes unresponsive

**Solutions:**
```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head -10

# Increase container memory (Proxmox)
pct set [CONTAINER_ID] --memory 1024

# Optimize Python memory usage
export PYTHONOPTIMIZE=1
```

---

## Security and Permission Issues

### File Permission Problems

**Symptoms:**
- "Permission denied" errors
- Cannot read configuration files

**Diagnosis:**
```bash
# Check file permissions
ls -la /opt/binance-portfolio-logger/
ls -la /opt/binance-portfolio-logger/.env
ls -la /opt/binance-portfolio-logger/credentials/
```

**Solutions:**
```bash
# Fix application directory permissions
chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
chmod 750 /opt/binance-portfolio-logger

# Fix configuration file permissions
chmod 600 /opt/binance-portfolio-logger/.env
chmod 600 /opt/binance-portfolio-logger/credentials/*

# Fix log directory permissions
chown -R binance-logger:binance-logger /var/log/binance-portfolio
chmod 755 /var/log/binance-portfolio
```

### Security Audit Failures

**Symptoms:**
- Security warnings in logs
- Audit script failures

**Solutions:**
```bash
# Run security audit
cd /opt/binance-portfolio-logger
sudo -u binance-logger ./venv/bin/python security_audit.py

# Fix common security issues
chmod 700 /opt/binance-portfolio-logger/credentials
chmod 600 /opt/binance-portfolio-logger/credentials/*
chmod 600 /opt/binance-portfolio-logger/.env

# Remove world-readable permissions
find /opt/binance-portfolio-logger -type f -perm /o+r -exec chmod o-r {} \;
```

---

## Proxmox-Specific Issues

### Container Won't Start

**Symptoms:**
- Container status shows "stopped"
- Cannot enter container

**Diagnosis:**
```bash
# Check container status
pct status [CONTAINER_ID]

# View container logs
journalctl -u pve-container@[CONTAINER_ID]

# Check container configuration
pct config [CONTAINER_ID]
```

**Solutions:**
```bash
# Try starting container manually
pct start [CONTAINER_ID]

# Check storage availability
pvesm status

# Verify container configuration
pct config [CONTAINER_ID]

# Check for resource conflicts
pct list
```

### Network Issues in Container

**Symptoms:**
- No internet connectivity from container
- Cannot reach external APIs

**Diagnosis:**
```bash
# Check container network configuration
pct exec [CONTAINER_ID] -- ip addr show

# Test connectivity from container
pct exec [CONTAINER_ID] -- ping 8.8.8.8
pct exec [CONTAINER_ID] -- curl -I https://google.com

# Check Proxmox bridge configuration
ip addr show vmbr0
```

**Solutions:**
```bash
# Restart container networking
pct exec [CONTAINER_ID] -- systemctl restart networking

# Check firewall rules on Proxmox host
iptables -L

# Verify bridge configuration
cat /etc/network/interfaces
```

### Storage Issues

**Symptoms:**
- Disk full errors
- Cannot write to storage

**Diagnosis:**
```bash
# Check container disk usage
pct exec [CONTAINER_ID] -- df -h

# Check Proxmox storage
pvesm status
df -h
```

**Solutions:**
```bash
# Resize container disk
pct resize [CONTAINER_ID] rootfs +2G

# Clean up logs
pct exec [CONTAINER_ID] -- find /var/log -name "*.log.*" -mtime +7 -delete

# Clean up temporary files
pct exec [CONTAINER_ID] -- apt autoremove
pct exec [CONTAINER_ID] -- apt autoclean
```

---

## Log Analysis

### Understanding Log Files

**Application Logs:**
- `/var/log/binance-portfolio/portfolio.log` - Main application log
- `/var/log/binance-portfolio/errors.log` - Error-specific log
- `/var/log/binance-portfolio/metrics.log` - Performance metrics

**System Logs:**
- `journalctl -u binance-portfolio-logger` - Systemd service logs
- `/var/log/syslog` - System messages
- `/var/log/cron.log` - Cron execution logs (if using cron)

### Common Log Patterns

**Successful Execution:**
```
2024-01-15 08:00:01 [INFO] Execution started
2024-01-15 08:00:02 [INFO] Configuration loaded successfully
2024-01-15 08:00:03 [INFO] Retrieved 15 asset balances
2024-01-15 08:00:05 [INFO] Portfolio value calculated: $45,234.56
2024-01-15 08:00:06 [INFO] Data logged to Google Sheets successfully
2024-01-15 08:00:06 [INFO] Execution completed successfully in 5.2 seconds
```

**API Connection Issues:**
```
2024-01-15 08:00:03 [ERROR] Binance API connection failed: Connection timeout
2024-01-15 08:00:05 [INFO] Retrying API call (attempt 2/3)
2024-01-15 08:00:07 [ERROR] Binance API connection failed: Connection timeout
2024-01-15 08:00:09 [INFO] Retrying API call (attempt 3/3)
2024-01-15 08:00:11 [ERROR] Max retries exceeded for Binance API
```

**Configuration Issues:**
```
2024-01-15 08:00:01 [ERROR] Configuration validation failed
2024-01-15 08:00:01 [ERROR] BINANCE_API_KEY environment variable not set
2024-01-15 08:00:01 [ERROR] Execution failed: Invalid configuration
```

### Log Analysis Commands

```bash
# View recent logs
tail -f /var/log/binance-portfolio/portfolio.log

# Search for errors
grep -i error /var/log/binance-portfolio/portfolio.log | tail -20

# Check execution history
grep "Execution completed" /var/log/binance-portfolio/portfolio.log | tail -10

# Monitor real-time logs
journalctl -u binance-portfolio-logger -f

# Check logs from specific time period
journalctl -u binance-portfolio-logger --since "2024-01-15 08:00:00" --until "2024-01-15 09:00:00"

# Search for specific patterns
grep -E "(ERROR|WARN)" /var/log/binance-portfolio/portfolio.log | tail -20
```

---

## Recovery Procedures

### Complete System Recovery

If the system is completely broken, follow these steps:

1. **Backup Current Configuration:**
   ```bash
   # Backup configuration files
   cp /opt/binance-portfolio-logger/.env /tmp/backup.env
   cp -r /opt/binance-portfolio-logger/credentials /tmp/backup-credentials
   ```

2. **Reinstall Application:**
   ```bash
   # For Proxmox: Destroy and recreate container
   pct stop [CONTAINER_ID]
   pct destroy [CONTAINER_ID]
   ./proxmox-install.sh
   
   # For manual installation: Remove and reinstall
   rm -rf /opt/binance-portfolio-logger
   ./setup.sh
   ```

3. **Restore Configuration:**
   ```bash
   # Restore backed up configuration
   cp /tmp/backup.env /opt/binance-portfolio-logger/.env
   cp -r /tmp/backup-credentials/* /opt/binance-portfolio-logger/credentials/
   chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
   ```

### Partial Recovery

For specific component failures:

1. **Reinstall Python Dependencies:**
   ```bash
   cd /opt/binance-portfolio-logger
   rm -rf venv
   sudo -u binance-logger python3 -m venv venv
   sudo -u binance-logger ./venv/bin/pip install -r requirements.txt
   ```

2. **Reset Service Configuration:**
   ```bash
   systemctl stop binance-portfolio-logger.timer
   systemctl disable binance-portfolio-logger.timer
   cp binance-portfolio-logger.service /etc/systemd/system/
   cp binance-portfolio-logger.timer /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable binance-portfolio-logger.timer
   systemctl start binance-portfolio-logger.timer
   ```

3. **Reset Log Files:**
   ```bash
   rm -f /var/log/binance-portfolio/*.log
   mkdir -p /var/log/binance-portfolio
   chown -R binance-logger:binance-logger /var/log/binance-portfolio
   ```

### Emergency Contacts and Resources

**Documentation:**
- Main README: `/opt/binance-portfolio-logger/README.md`
- API Documentation: `/opt/binance-portfolio-logger/docs/api_documentation.md`
- Deployment Guide: `/opt/binance-portfolio-logger/DEPLOYMENT.md`

**Validation Tools:**
- Health Check: `python health_check.py`
- Setup Validation: `python validate_setup.py`
- Security Audit: `python security_audit.py`

**External Resources:**
- Binance API Documentation: https://binance-docs.github.io/apidocs/
- Google Sheets API Documentation: https://developers.google.com/sheets/api
- Proxmox Documentation: https://pve.proxmox.com/pve-docs/

---

## Getting Help

If you're still experiencing issues after following this guide:

1. **Collect Diagnostic Information:**
   ```bash
   # Create diagnostic report
   echo "=== System Information ===" > diagnostic_report.txt
   uname -a >> diagnostic_report.txt
   echo "=== Container Info (if Proxmox) ===" >> diagnostic_report.txt
   pct config [CONTAINER_ID] >> diagnostic_report.txt 2>/dev/null || echo "Not running in Proxmox" >> diagnostic_report.txt
   echo "=== Service Status ===" >> diagnostic_report.txt
   systemctl status binance-portfolio-logger.timer >> diagnostic_report.txt
   echo "=== Recent Logs ===" >> diagnostic_report.txt
   tail -50 /var/log/binance-portfolio/portfolio.log >> diagnostic_report.txt
   echo "=== Configuration (sanitized) ===" >> diagnostic_report.txt
   grep -v "API_KEY\|API_SECRET" /opt/binance-portfolio-logger/.env >> diagnostic_report.txt
   ```

2. **Check GitHub Issues:**
   - Search existing issues for similar problems
   - Create a new issue with your diagnostic report

3. **Community Support:**
   - Include relevant log excerpts (with sensitive data removed)
   - Describe your environment (Proxmox version, container specs, etc.)
   - List the steps you've already tried

Remember to never share your actual API keys, secrets, or other sensitive information when seeking help.