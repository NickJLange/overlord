#!/bin/bash

# NFTables TCP Logging Setup Script
# Sets up logging rules and rsyslog configuration for TCP connection monitoring

set -e

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

echo "Setting up NFTables TCP logging..."

# Load the nftables rules
nft -f nftables_tcp_logging.nft

echo "NFTables rules loaded successfully"

# Configure rsyslog for structured logging
cat > /etc/rsyslog.d/50-tcp-logger.conf << 'EOF'
# TCP Logger - NFTables log parsing
:msg, contains, "TCP_SYN_OUT" /var/log/tcp_connections.log
:msg, contains, "TCP_SYN_IN" /var/log/tcp_connections.log
:msg, contains, "TCP_FIN_OUT" /var/log/tcp_connections.log
:msg, contains, "TCP_FIN_IN" /var/log/tcp_connections.log
:msg, contains, "TCP_RST_OUT" /var/log/tcp_connections.log
:msg, contains, "TCP_RST_IN" /var/log/tcp_connections.log
:msg, contains, "TCP_SYN_OWNER" /var/log/tcp_owners.log
:msg, contains, "TCP_FIN_OWNER" /var/log/tcp_owners.log
:msg, contains, "TCP_RST_OWNER" /var/log/tcp_owners.log
:msg, contains, "HTTP_SYN" /var/log/tcp_services.log
:msg, contains, "SSH_SYN" /var/log/tcp_services.log
:msg, contains, "DB_SYN" /var/log/tcp_services.log
:msg, contains, "APP_SYN" /var/log/tcp_services.log

# Stop processing these messages
:msg, contains, "TCP_" stop
EOF

# Restart rsyslog to apply configuration
systemctl restart rsyslog

# Create log parsing script
cat > /usr/local/bin/parse_tcp_logs.sh << 'EOF'
#!/bin/bash

# Parse TCP connection logs and extract 5-tuple with user info
# Usage: parse_tcp_logs.sh [logfile]

LOGFILE=${1:-/var/log/tcp_owners.log}

if [[ ! -f "$LOGFILE" ]]; then
    echo "Log file $LOGFILE not found"
    exit 1
fi

echo "Parsing TCP connections from $LOGFILE"
echo "Format: timestamp,event_type,uid,src_ip,src_port,dst_ip,dst_port,protocol"

# Parse log entries and extract structured data
tail -f "$LOGFILE" | while read line; do
    if [[ $line =~ TCP_(SYN|FIN|RST)_OWNER ]]; then
        # Extract timestamp
        timestamp=$(echo "$line" | awk '{print $1 " " $2 " " $3}')
        
        # Extract event type
        event_type=$(echo "$line" | grep -o 'TCP_[A-Z]*_OWNER' | sed 's/TCP_\(.*\)_OWNER/\1/')
        
        # Extract UID (requires kernel support for skuid logging)
        uid=$(echo "$line" | grep -o 'UID=[0-9]*' | cut -d= -f2)
        
        # Extract IP addresses and ports
        src_ip=$(echo "$line" | grep -o 'SRC=[0-9.]*' | cut -d= -f2)
        src_port=$(echo "$line" | grep -o 'SPT=[0-9]*' | cut -d= -f2)
        dst_ip=$(echo "$line" | grep -o 'DST=[0-9.]*' | cut -d= -f2)
        dst_port=$(echo "$line" | grep -o 'DPT=[0-9]*' | cut -d= -f2)
        
        # Protocol is always TCP (6)
        protocol=6
        
        echo "$timestamp,$event_type,$uid,$src_ip,$src_port,$dst_ip,$dst_port,$protocol"
    fi
done
EOF

chmod +x /usr/local/bin/parse_tcp_logs.sh

# Create monitoring script
cat > /usr/local/bin/tcp_monitor.sh << 'EOF'
#!/bin/bash

# TCP Connection Monitor
# Provides real-time view of TCP connections with user information

echo "TCP Connection Monitor - Press Ctrl+C to stop"
echo "==================================================="

# Monitor different log streams
{
    echo "=== Connection Events ==="
    tail -f /var/log/tcp_connections.log | while read line; do
        echo "[CONN] $line"
    done &

    echo "=== Owner Information ==="
    /usr/local/bin/parse_tcp_logs.sh /var/log/tcp_owners.log | while read line; do
        echo "[OWNER] $line"
    done &

    echo "=== Service Connections ==="
    tail -f /var/log/tcp_services.log | while read line; do
        echo "[SERVICE] $line"
    done &

    wait
}
EOF

chmod +x /usr/local/bin/tcp_monitor.sh

echo "Setup complete!"
echo ""
echo "Usage:"
echo "  sudo tcp_monitor.sh           # Real-time monitoring"
echo "  sudo parse_tcp_logs.sh        # Parse owner logs"
echo "  tail -f /var/log/tcp_*.log    # View raw logs"
echo ""
echo "To remove rules: sudo nft delete table inet tcp_logger"
echo "                 sudo nft delete table inet tcp_service_logger"