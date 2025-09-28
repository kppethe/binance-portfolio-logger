#!/bin/bash

# Binance Portfolio Logger Setup Script
# This script automates the installation and configuration process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
APP_NAME="binance-portfolio-logger"
APP_USER="binance-logger"
APP_DIR="/opt/${APP_NAME}"
LOG_DIR="/var/log/binance-portfolio"
VENV_DIR="${APP_DIR}/venv"
CREDENTIALS_DIR="${APP_DIR}/credentials"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Function to check system requirements
check_system_requirements() {
    print_status "Checking system requirements..."
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        print_error "Cannot determine OS version"
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        print_warning "This script is designed for Ubuntu/Debian. Proceeding anyway..."
    fi
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$PYTHON_VERSION < 3.9" | bc -l) -eq 1 ]]; then
        print_error "Python 3.9+ is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "System requirements check passed"
}

# Function to install system dependencies
install_system_dependencies() {
    print_status "Installing system dependencies..."
    
    apt update
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        cron \
        logrotate \
        bc \
        curl \
        wget
    
    print_success "System dependencies installed"
}

# Function to create application user
create_app_user() {
    print_status "Creating application user..."
    
    if id "$APP_USER" &>/dev/null; then
        print_warning "User $APP_USER already exists"
    else
        useradd -m -s /bin/bash "$APP_USER"
        print_success "User $APP_USER created"
    fi
}

# Function to create directory structure
create_directories() {
    print_status "Creating directory structure..."
    
    # Create application directory
    mkdir -p "$APP_DIR"
    mkdir -p "$CREDENTIALS_DIR"
    mkdir -p "$LOG_DIR"
    
    # Set ownership
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
    
    # Set permissions
    chmod 750 "$APP_DIR"
    chmod 700 "$CREDENTIALS_DIR"
    chmod 755 "$LOG_DIR"
    
    print_success "Directory structure created"
}

# Function to setup Python virtual environment
setup_python_environment() {
    print_status "Setting up Python virtual environment..."
    
    # Create virtual environment as app user
    sudo -u "$APP_USER" python3 -m venv "$VENV_DIR"
    
    # Upgrade pip
    sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip
    
    # Install requirements if requirements.txt exists
    if [[ -f "requirements.txt" ]]; then
        sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -r requirements.txt
        print_success "Python dependencies installed"
    else
        print_warning "requirements.txt not found. Installing basic dependencies..."
        sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install \
            python-binance==1.0.19 \
            gspread==5.12.4 \
            python-dotenv==1.0.0 \
            structlog==23.2.0
    fi
    
    print_success "Python environment setup complete"
}

# Function to copy application files
copy_application_files() {
    print_status "Copying application files..."
    
    # Copy source files
    if [[ -d "src" ]]; then
        cp -r src/* "$APP_DIR/"
        chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    fi
    
    # Copy main application file
    if [[ -f "main.py" ]]; then
        cp main.py "$APP_DIR/"
        chown "$APP_USER:$APP_USER" "$APP_DIR/main.py"
        chmod 755 "$APP_DIR/main.py"
    fi
    
    # Copy configuration template
    if [[ -f ".env.example" ]]; then
        cp .env.example "$APP_DIR/"
        chown "$APP_USER:$APP_USER" "$APP_DIR/.env.example"
    fi
    
    print_success "Application files copied"
}

# Function to setup configuration
setup_configuration() {
    print_status "Setting up configuration..."
    
    # Create .env file if it doesn't exist
    if [[ ! -f "$APP_DIR/.env" ]]; then
        if [[ -f "$APP_DIR/.env.example" ]]; then
            cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        else
            touch "$APP_DIR/.env"
        fi
        chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
        chmod 600 "$APP_DIR/.env"
        
        print_warning "Configuration file created at $APP_DIR/.env"
        print_warning "Please edit this file with your actual credentials before running the application"
    fi
    
    print_success "Configuration setup complete"
}

# Function to setup log rotation
setup_log_rotation() {
    print_status "Setting up log rotation..."
    
    cat > /etc/logrotate.d/binance-portfolio << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        # Send HUP signal to application if it's running
        pkill -HUP -f "python.*main.py" || true
    endscript
}
EOF
    
    print_success "Log rotation configured"
}

# Function to setup systemd service
setup_systemd_service() {
    print_status "Setting up systemd service..."
    
    if [[ -f "binance-portfolio-logger.service" ]]; then
        cp binance-portfolio-logger.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable binance-portfolio-logger.service
        print_success "Systemd service installed and enabled"
    else
        print_warning "Service file not found. Skipping systemd setup."
    fi
}

# Function to setup cron job
setup_cron_job() {
    print_status "Setting up cron job..."
    
    # Create cron job for daily execution at 8:00 AM
    CRON_JOB="0 8 * * * $VENV_DIR/bin/python $APP_DIR/main.py >> $LOG_DIR/cron.log 2>&1"
    
    # Add cron job for app user
    (sudo -u "$APP_USER" crontab -l 2>/dev/null; echo "$CRON_JOB") | sudo -u "$APP_USER" crontab -
    
    print_success "Cron job configured for daily execution at 8:00 AM"
}

# Function to run validation
run_validation() {
    print_status "Running validation checks..."
    
    if [[ -f "validate_setup.py" ]]; then
        sudo -u "$APP_USER" "$VENV_DIR/bin/python" validate_setup.py
    else
        print_warning "Validation script not found. Skipping validation."
    fi
}

# Function to display post-installation instructions
show_post_install_instructions() {
    echo
    print_success "Installation completed successfully!"
    echo
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Edit the configuration file: $APP_DIR/.env"
    echo "2. Add your Binance API credentials"
    echo "3. Add your Google Service Account JSON file to: $CREDENTIALS_DIR/"
    echo "4. Update the Google Spreadsheet ID in the configuration"
    echo "5. Test the application: sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/main.py"
    echo "6. Check logs: tail -f $LOG_DIR/portfolio.log"
    echo
    echo -e "${YELLOW}Service management:${NC}"
    echo "- Start service: systemctl start binance-portfolio-logger"
    echo "- Stop service: systemctl stop binance-portfolio-logger"
    echo "- Check status: systemctl status binance-portfolio-logger"
    echo "- View logs: journalctl -u binance-portfolio-logger -f"
    echo
    echo -e "${YELLOW}Cron job:${NC}"
    echo "- View cron jobs: sudo -u $APP_USER crontab -l"
    echo "- Edit cron jobs: sudo -u $APP_USER crontab -e"
    echo
}

# Main installation function
main() {
    echo -e "${BLUE}Binance Portfolio Logger Setup${NC}"
    echo "=================================="
    echo
    
    check_root
    check_system_requirements
    install_system_dependencies
    create_app_user
    create_directories
    setup_python_environment
    copy_application_files
    setup_configuration
    setup_log_rotation
    setup_systemd_service
    setup_cron_job
    run_validation
    show_post_install_instructions
}

# Run main function
main "$@"