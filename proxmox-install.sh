#!/usr/bin/env bash

# Binance Portfolio Logger - Proxmox Installation Script
# This script automates the complete installation of the Binance Portfolio Logger on Proxmox
# Similar to Proxmox VE Helper-Scripts format

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Binance Portfolio Logger"
CONTAINER_ID=""
CONTAINER_NAME="binance-portfolio-logger"
CONTAINER_HOSTNAME="binance-logger"
CONTAINER_PASSWORD=""
CONTAINER_DISK_SIZE="8"
CONTAINER_RAM="512"
CONTAINER_CPU_CORES="1"
CONTAINER_TEMPLATE="ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
CONTAINER_STORAGE="local-lvm"
CONTAINER_BRIDGE="vmbr0"
CONTAINER_VLAN=""
CONTAINER_IP="dhcp"
CONTAINER_GATEWAY=""
CONTAINER_DNS="8.8.8.8"

# GitHub repository (update with actual repository)
GITHUB_REPO="https://github.com/your-username/binance-portfolio-logger.git"

# Function to print colored output
print_info() {
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

print_header() {
    echo -e "${PURPLE}$1${NC}"
}

# Function to check if running on Proxmox
check_proxmox() {
    if ! command -v pct &> /dev/null; then
        print_error "This script must be run on a Proxmox VE host"
        exit 1
    fi
    
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Function to get next available container ID
get_next_container_id() {
    local next_id=100
    while pct status $next_id &>/dev/null; do
        ((next_id++))
    done
    CONTAINER_ID=$next_id
}

# Function to validate IP address
validate_ip() {
    local ip=$1
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to get user input with defaults
get_user_input() {
    print_header "=== $APP_NAME Installation Configuration ==="
    echo
    
    # Container ID
    read -p "Container ID (auto-detect next available): " input_id
    if [[ -n "$input_id" ]]; then
        if pct status $input_id &>/dev/null; then
            print_error "Container ID $input_id already exists"
            exit 1
        fi
        CONTAINER_ID=$input_id
    else
        get_next_container_id
    fi
    
    # Container name
    read -p "Container name [$CONTAINER_NAME]: " input_name
    CONTAINER_NAME=${input_name:-$CONTAINER_NAME}
    
    # Container hostname
    read -p "Container hostname [$CONTAINER_HOSTNAME]: " input_hostname
    CONTAINER_HOSTNAME=${input_hostname:-$CONTAINER_HOSTNAME}
    
    # Container password
    while [[ -z "$CONTAINER_PASSWORD" ]]; do
        read -s -p "Container root password: " CONTAINER_PASSWORD
        echo
        if [[ -z "$CONTAINER_PASSWORD" ]]; then
            print_warning "Password cannot be empty"
        fi
    done
    
    # Resources
    read -p "Disk size in GB [$CONTAINER_DISK_SIZE]: " input_disk
    CONTAINER_DISK_SIZE=${input_disk:-$CONTAINER_DISK_SIZE}
    
    read -p "RAM in MB [$CONTAINER_RAM]: " input_ram
    CONTAINER_RAM=${input_ram:-$CONTAINER_RAM}
    
    read -p "CPU cores [$CONTAINER_CPU_CORES]: " input_cpu
    CONTAINER_CPU_CORES=${input_cpu:-$CONTAINER_CPU_CORES}
    
    # Storage
    echo "Available storage:"
    pvesm status | grep -E "^[a-zA-Z]" | awk '{print "  - " $1 " (" $2 ")"}'
    read -p "Storage [$CONTAINER_STORAGE]: " input_storage
    CONTAINER_STORAGE=${input_storage:-$CONTAINER_STORAGE}
    
    # Network
    echo "Available bridges:"
    ip link show | grep -E "^[0-9]+: vmbr" | awk -F': ' '{print "  - " $2}' | awk '{print $1}'
    read -p "Network bridge [$CONTAINER_BRIDGE]: " input_bridge
    CONTAINER_BRIDGE=${input_bridge:-$CONTAINER_BRIDGE}
    
    read -p "VLAN tag (optional): " input_vlan
    CONTAINER_VLAN=$input_vlan
    
    read -p "IP address (dhcp or static IP) [$CONTAINER_IP]: " input_ip
    CONTAINER_IP=${input_ip:-$CONTAINER_IP}
    
    if [[ "$CONTAINER_IP" != "dhcp" ]]; then
        if ! validate_ip "$CONTAINER_IP"; then
            print_error "Invalid IP address format"
            exit 1
        fi
        
        read -p "Gateway IP: " CONTAINER_GATEWAY
        if [[ -n "$CONTAINER_GATEWAY" ]] && ! validate_ip "$CONTAINER_GATEWAY"; then
            print_error "Invalid gateway IP address format"
            exit 1
        fi
    fi
    
    read -p "DNS server [$CONTAINER_DNS]: " input_dns
    CONTAINER_DNS=${input_dns:-$CONTAINER_DNS}
    
    echo
    print_header "=== Configuration Summary ==="
    echo "Container ID: $CONTAINER_ID"
    echo "Container Name: $CONTAINER_NAME"
    echo "Hostname: $CONTAINER_HOSTNAME"
    echo "Disk Size: ${CONTAINER_DISK_SIZE}GB"
    echo "RAM: ${CONTAINER_RAM}MB"
    echo "CPU Cores: $CONTAINER_CPU_CORES"
    echo "Storage: $CONTAINER_STORAGE"
    echo "Network: $CONTAINER_BRIDGE"
    [[ -n "$CONTAINER_VLAN" ]] && echo "VLAN: $CONTAINER_VLAN"
    echo "IP: $CONTAINER_IP"
    [[ -n "$CONTAINER_GATEWAY" ]] && echo "Gateway: $CONTAINER_GATEWAY"
    echo "DNS: $CONTAINER_DNS"
    echo
    
    read -p "Proceed with installation? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi
}

# Function to download container template
download_template() {
    print_info "Checking for Ubuntu 22.04 template..."
    
    if ! pveam list $CONTAINER_STORAGE | grep -q "$CONTAINER_TEMPLATE"; then
        print_info "Downloading Ubuntu 22.04 template..."
        pveam download $CONTAINER_STORAGE $CONTAINER_TEMPLATE
        if [[ $? -ne 0 ]]; then
            print_error "Failed to download container template"
            exit 1
        fi
    else
        print_success "Ubuntu 22.04 template already available"
    fi
}

# Function to create container
create_container() {
    print_info "Creating LXC container..."
    
    # Build network configuration
    local net_config="name=eth0,bridge=$CONTAINER_BRIDGE"
    [[ -n "$CONTAINER_VLAN" ]] && net_config+=",tag=$CONTAINER_VLAN"
    
    if [[ "$CONTAINER_IP" == "dhcp" ]]; then
        net_config+=",ip=dhcp"
    else
        net_config+=",ip=$CONTAINER_IP/24"
        [[ -n "$CONTAINER_GATEWAY" ]] && net_config+=",gw=$CONTAINER_GATEWAY"
    fi
    
    # Create container
    pct create $CONTAINER_ID $CONTAINER_STORAGE:vztmpl/$CONTAINER_TEMPLATE \
        --hostname $CONTAINER_HOSTNAME \
        --password "$CONTAINER_PASSWORD" \
        --memory $CONTAINER_RAM \
        --cores $CONTAINER_CPU_CORES \
        --rootfs $CONTAINER_STORAGE:$CONTAINER_DISK_SIZE \
        --net0 "$net_config" \
        --nameserver $CONTAINER_DNS \
        --features nesting=1 \
        --unprivileged 1 \
        --onboot 1 \
        --start 1
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to create container"
        exit 1
    fi
    
    print_success "Container $CONTAINER_ID created successfully"
    
    # Wait for container to start
    print_info "Waiting for container to start..."
    sleep 10
    
    # Wait for network to be ready
    local max_attempts=30
    local attempt=0
    while [[ $attempt -lt $max_attempts ]]; do
        if pct exec $CONTAINER_ID -- ping -c 1 8.8.8.8 &>/dev/null; then
            break
        fi
        ((attempt++))
        sleep 2
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        print_error "Container network not ready after 60 seconds"
        exit 1
    fi
    
    print_success "Container is ready"
}

# Function to install system dependencies
install_system_dependencies() {
    print_info "Installing system dependencies..."
    
    pct exec $CONTAINER_ID -- bash -c "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get upgrade -y
        apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            git \
            curl \
            wget \
            cron \
            logrotate \
            nano \
            htop \
            systemd \
            ca-certificates \
            gnupg \
            lsb-release
    "
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to install system dependencies"
        exit 1
    fi
    
    print_success "System dependencies installed"
}

# Function to create application user
create_app_user() {
    print_info "Creating application user..."
    
    pct exec $CONTAINER_ID -- bash -c "
        useradd -m -s /bin/bash binance-logger
        usermod -aG sudo binance-logger
        mkdir -p /home/binance-logger/.ssh
        chown -R binance-logger:binance-logger /home/binance-logger
    "
    
    print_success "Application user created"
}

# Function to setup application directories
setup_directories() {
    print_info "Setting up application directories..."
    
    pct exec $CONTAINER_ID -- bash -c "
        mkdir -p /opt/binance-portfolio-logger/{credentials,logs}
        mkdir -p /var/log/binance-portfolio
        chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
        chown -R binance-logger:binance-logger /var/log/binance-portfolio
        chmod 750 /opt/binance-portfolio-logger
        chmod 700 /opt/binance-portfolio-logger/credentials
        chmod 755 /var/log/binance-portfolio
    "
    
    print_success "Application directories created"
}

# Function to clone and install application
install_application() {
    print_info "Installing Binance Portfolio Logger application..."
    
    # Clone repository (or copy files if running locally)
    if [[ -d "$(dirname "$0")" ]]; then
        # Copy local files
        print_info "Copying application files..."
        
        # Create temporary archive
        local temp_archive="/tmp/binance-portfolio-logger.tar.gz"
        tar -czf "$temp_archive" -C "$(dirname "$0")" \
            --exclude='.git' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.pytest_cache' \
            --exclude='logs/*' \
            .
        
        # Copy to container
        pct push $CONTAINER_ID "$temp_archive" /tmp/app.tar.gz
        
        # Extract in container
        pct exec $CONTAINER_ID -- bash -c "
            cd /opt/binance-portfolio-logger
            tar -xzf /tmp/app.tar.gz
            rm /tmp/app.tar.gz
            chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
        "
        
        rm "$temp_archive"
    else
        # Clone from GitHub
        print_info "Cloning from GitHub repository..."
        pct exec $CONTAINER_ID -- bash -c "
            cd /opt
            git clone $GITHUB_REPO binance-portfolio-logger-temp
            cp -r binance-portfolio-logger-temp/* binance-portfolio-logger/
            rm -rf binance-portfolio-logger-temp
            chown -R binance-logger:binance-logger /opt/binance-portfolio-logger
        "
    fi
    
    # Setup Python virtual environment
    print_info "Setting up Python virtual environment..."
    pct exec $CONTAINER_ID -- bash -c "
        cd /opt/binance-portfolio-logger
        sudo -u binance-logger python3 -m venv venv
        sudo -u binance-logger ./venv/bin/pip install --upgrade pip
        sudo -u binance-logger ./venv/bin/pip install -r requirements.txt
    "
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to install Python dependencies"
        exit 1
    fi
    
    print_success "Application installed successfully"
}

# Function to setup configuration files
setup_configuration() {
    print_info "Setting up configuration files..."
    
    # Create environment file
    pct exec $CONTAINER_ID -- bash -c "
        cp /opt/binance-portfolio-logger/.env.example /opt/binance-portfolio-logger/.env
        chown binance-logger:binance-logger /opt/binance-portfolio-logger/.env
        chmod 600 /opt/binance-portfolio-logger/.env
    "
    
    # Setup systemd service
    pct exec $CONTAINER_ID -- bash -c "
        cp /opt/binance-portfolio-logger/binance-portfolio-logger.service /etc/systemd/system/
        cp /opt/binance-portfolio-logger/binance-portfolio-logger.timer /etc/systemd/system/
        systemctl daemon-reload
    "
    
    # Setup logrotate
    pct exec $CONTAINER_ID -- bash -c "
        cat > /etc/logrotate.d/binance-portfolio << 'EOF'
/var/log/binance-portfolio/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 binance-logger binance-logger
    postrotate
        systemctl reload binance-portfolio-logger || true
    endscript
}
EOF
    "
    
    print_success "Configuration files setup complete"
}

# Function to setup firewall (if needed)
setup_firewall() {
    print_info "Configuring firewall..."
    
    pct exec $CONTAINER_ID -- bash -c "
        # Install ufw if not present
        apt-get install -y ufw
        
        # Configure firewall rules
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing
        
        # Allow SSH (if needed for management)
        ufw allow 22/tcp
        
        # Allow outbound HTTPS for API access
        ufw allow out 443/tcp
        
        # Enable firewall
        ufw --force enable
    "
    
    print_success "Firewall configured"
}

# Function to run validation
run_validation() {
    print_info "Running system validation..."
    
    pct exec $CONTAINER_ID -- bash -c "
        cd /opt/binance-portfolio-logger
        sudo -u binance-logger ./venv/bin/python validate_setup.py
    "
    
    local validation_result=$?
    if [[ $validation_result -eq 0 ]]; then
        print_success "System validation passed"
    else
        print_warning "System validation completed with warnings (this is normal before credential configuration)"
    fi
}

# Function to display post-installation instructions
show_post_install_instructions() {
    local container_ip
    if [[ "$CONTAINER_IP" == "dhcp" ]]; then
        container_ip=$(pct exec $CONTAINER_ID -- hostname -I | awk '{print $1}')
    else
        container_ip=$CONTAINER_IP
    fi
    
    print_header "=== Installation Complete ==="
    echo
    print_success "$APP_NAME has been successfully installed!"
    echo
    print_info "Container Details:"
    echo "  - Container ID: $CONTAINER_ID"
    echo "  - IP Address: $container_ip"
    echo "  - Username: root"
    echo "  - Application User: binance-logger"
    echo
    print_info "Next Steps:"
    echo "1. Connect to the container:"
    echo "   pct enter $CONTAINER_ID"
    echo
    echo "2. Configure your credentials:"
    echo "   nano /opt/binance-portfolio-logger/.env"
    echo
    echo "3. Add your Google Service Account JSON file:"
    echo "   # Copy your service-account.json to the container"
    echo "   # Place it in: /opt/binance-portfolio-logger/credentials/"
    echo "   chown binance-logger:binance-logger /opt/binance-portfolio-logger/credentials/service-account.json"
    echo "   chmod 600 /opt/binance-portfolio-logger/credentials/service-account.json"
    echo
    echo "4. Test the application:"
    echo "   sudo -u binance-logger /opt/binance-portfolio-logger/venv/bin/python /opt/binance-portfolio-logger/main.py"
    echo
    echo "5. Enable automatic scheduling:"
    echo "   systemctl enable binance-portfolio-logger.timer"
    echo "   systemctl start binance-portfolio-logger.timer"
    echo
    echo "6. Monitor logs:"
    echo "   tail -f /var/log/binance-portfolio/portfolio.log"
    echo
    print_info "Configuration Files:"
    echo "  - Environment: /opt/binance-portfolio-logger/.env"
    echo "  - Credentials: /opt/binance-portfolio-logger/credentials/"
    echo "  - Logs: /var/log/binance-portfolio/"
    echo "  - Service: /etc/systemd/system/binance-portfolio-logger.service"
    echo
    print_info "Management Commands:"
    echo "  - Check status: systemctl status binance-portfolio-logger.timer"
    echo "  - View logs: journalctl -u binance-portfolio-logger -f"
    echo "  - Manual run: systemctl start binance-portfolio-logger"
    echo
    print_warning "Remember to:"
    echo "  - Configure your Binance API keys (read-only permissions)"
    echo "  - Set up your Google Sheets service account"
    echo "  - Test the configuration before enabling the timer"
    echo
}

# Function to cleanup on error
cleanup_on_error() {
    if [[ -n "$CONTAINER_ID" ]] && pct status $CONTAINER_ID &>/dev/null; then
        print_warning "Cleaning up container $CONTAINER_ID due to error..."
        pct stop $CONTAINER_ID 2>/dev/null
        pct destroy $CONTAINER_ID 2>/dev/null
    fi
}

# Main installation function
main() {
    # Set error handling
    set -e
    trap cleanup_on_error ERR
    
    print_header "╔══════════════════════════════════════════════════════════════╗"
    print_header "║                 Binance Portfolio Logger                     ║"
    print_header "║                 Proxmox Installation Script                  ║"
    print_header "╚══════════════════════════════════════════════════════════════╝"
    echo
    
    # Check prerequisites
    check_proxmox
    
    # Get user configuration
    get_user_input
    
    # Start installation
    print_header "=== Starting Installation ==="
    
    # Download template
    download_template
    
    # Create container
    create_container
    
    # Install system dependencies
    install_system_dependencies
    
    # Create application user
    create_app_user
    
    # Setup directories
    setup_directories
    
    # Install application
    install_application
    
    # Setup configuration
    setup_configuration
    
    # Setup firewall
    setup_firewall
    
    # Run validation
    run_validation
    
    # Remove sudo access from application user
    pct exec $CONTAINER_ID -- deluser binance-logger sudo
    
    # Show post-installation instructions
    show_post_install_instructions
    
    print_success "Installation completed successfully!"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Binance Portfolio Logger - Proxmox Installation Script"
        echo
        echo "Usage: $0 [options]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --uninstall    Uninstall the application"
        echo
        echo "This script will create a new LXC container and install the"
        echo "Binance Portfolio Logger application with all dependencies."
        echo
        exit 0
        ;;
    --uninstall)
        print_header "=== Uninstalling Binance Portfolio Logger ==="
        read -p "Enter container ID to remove: " remove_id
        if [[ -n "$remove_id" ]] && pct status $remove_id &>/dev/null; then
            read -p "Are you sure you want to remove container $remove_id? (y/N): " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                pct stop $remove_id 2>/dev/null || true
                pct destroy $remove_id
                print_success "Container $remove_id removed successfully"
            fi
        else
            print_error "Container $remove_id not found"
        fi
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac