#!/usr/bin/env python3
"""
Home Lab & IoT Service Monitor
Monitors hosts and services across subnets (New York, Wisconsin, Miyagi).
Sends metrics & service checks to Datadog, sends real-time alerting emails on state changes,
and compiles a daily summary of issues.
"""

import os
import sys
import json
import time
import socket
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Define base directory (root of overlord repository)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "lib"))

# Service and monitoring configurations
STATE_FILE = os.path.join(BASE_DIR, "data", "monitor_state.json")
TASMOTA_INVENTORY = os.path.join(BASE_DIR, "tasmota.inventory")
NON_TASMOTA_INVENTORY = os.path.join(BASE_DIR, "private-smart-home-ansible", "non_tasmota_hosts.inventory")
ANSIBLE_HOSTS = os.path.join(BASE_DIR, "private-smart-home-ansible", "hosts")

# Custom service specifications to check (Label -> Port, Name, Type)
# Some services are checked dynamically via group membership, others are static
STATIC_SERVICES = [
    {
        "name": "Node-RED",
        "host": "terraDelta",
        "port": 1880,
        "type": "tcp",
        "description": "Flow-based programming tool for IoT"
    },
    {
        "name": "Vault",
        "host": "terraOmega",
        "port": 8200,
        "type": "tcp",
        "description": "Secret and certificate storage"
    },
    {
        "name": "Homebridge Config UI",
        "host": "terraDelta",
        "port": 8581,
        "type": "tcp",
        "description": "Homebridge web administration interface"
    },
    {
        "name": "Homebridge Bridge",
        "host": "terraDelta",
        "port": 51827,
        "type": "tcp",
        "description": "Homebridge Apple HomeKit bridge service"
    },
    {
        "name": "Teleport",
        "host": "terraGamma",
        "port": 443,
        "type": "tcp",
        "description": "Secure remote access gateway"
    }
]

def load_env():
    """Loads environment variables from root .env and cert management .env"""
    for env_path in [os.path.join(BASE_DIR, ".env"), os.path.join(BASE_DIR, "internal_cert_management", ".env")]:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")

def parse_inventory_file(file_path, hosts_dict=None):
    """Parses Ansible INI-style hosts list and extracts host labels and IPs"""
    if hosts_dict is None:
        hosts_dict = {}
    if not os.path.exists(file_path):
        return hosts_dict
        
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('['):
                continue
            parts = line.split()
            if not parts:
                continue
            host_label = parts[0]
            ip = None
            for p in parts[1:]:
                if p.startswith('ansible_ssh_host='):
                    ip = p.split('=')[1]
                    break
            if ip:
                hosts_dict[host_label] = ip
    return hosts_dict

def parse_groups_from_inventory(file_path):
    """Extracts groups and their member hostnames from non-Tasmota inventory"""
    groups = defaultdict(list)
    current_group = None
    if not os.path.exists(file_path):
        return groups

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current_group = line[1:-1]
                continue
            if current_group:
                if ':children' in current_group:
                    continue
                parts = line.split()
                if parts:
                    groups[current_group].append(parts[0])
    return groups

def parse_tasmota_inventory(file_path):
    """Loads metadata for Tasmota switches/bulbs"""
    tasmota_meta = {}
    if not os.path.exists(file_path):
        return tasmota_meta
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 5:
                mac, building, kind, room, name = parts[0], parts[1], parts[2], parts[3], parts[4]
                label = f"{room}_{name}"
                tasmota_meta[label] = {
                    "mac": mac,
                    "building": building,
                    "kind": kind,
                    "room": room,
                    "name": name,
                    "friendly": parts[5] if len(parts) > 5 else label
                }
    return tasmota_meta

def ping_host(ip):
    """Pings a host using fping or fallback ping"""
    # Try fping first (faster timeout control)
    fping_path = os.environ.get("FPING_PATH", "/Users/njl/bin/fping")
    if not os.path.exists(fping_path):
        fping_path = "fping"
    
    try:
        res = subprocess.run([fping_path, '-c', '1', '-t', '500', ip], capture_output=True)
        if res.returncode == 0:
            return True, "fping succeeded"
    except FileNotFoundError:
        pass

    # Fallback to standard ping
    import sys
    cmd = ['ping', '-c', '1']
    if sys.platform == 'darwin':
        cmd.extend(['-W', '500'])  # macOS wait 500ms
    else:
        cmd.extend(['-W', '1'])    # Linux wait 1s
    cmd.append(ip)
    
    try:
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0, "ping succeeded" if res.returncode == 0 else "ping failed"
    except Exception as e:
        return False, f"ping error: {str(e)}"

def tcp_check(ip, port, timeout=1.5):
    """Checks if a TCP port is open"""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True, "Port connection succeeded"
    except socket.timeout:
        return False, "Connection timed out"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def get_building_by_host(host_label, tasmota_meta, groups):
    """Attempts to identify the building (region) of a host"""
    if host_label in tasmota_meta:
        return tasmota_meta[host_label]["building"]
    
    for region in ["newyork", "wisconsin", "miyagi"]:
        for grp_suffix in ["_linux", "_iot", "_misc", ""]:
            grp_name = f"{region}{grp_suffix}"
            if host_label in groups.get(grp_name, []):
                return region
    return "unknown"

# Datadog API Client using standard urllib (zero external dependencies)
def send_to_datadog(api_key, site, path, payload):
    if not api_key:
        return False
    url = f"https://api.{site}{path}"
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": api_key
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 202 or response.status == 200
    except urllib.error.URLError as e:
        print(f"Datadog API Error ({url}): {e}")
        return False
    except Exception as e:
        print(f"Datadog post exception: {e}")
        return False

def send_dogstatsd_service_check(host, port, check_name, status, host_name=None, message="", tags=None):
    """Sends a service check via DogStatsD UDP protocol"""
    tag_str = ""
    if tags:
        tag_str = "|#" + ",".join(tags)
    
    h_str = ""
    if host_name:
        h_str = f"|h:{host_name}"
        
    m_str = ""
    if message:
        escaped_msg = message.replace('\n', '\\n').replace('|', '\\|')
        m_str = f"|m:{escaped_msg}"
        
    payload = f"_sc|{check_name}|{status}{h_str}{tag_str}{m_str}"
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(payload.encode('utf-8'), (host, port))
    except Exception as e:
        print(f"Failed to send DogStatsD service check: {e}")

def send_dogstatsd_metric(host, port, metric_name, value, tags=None):
    """Sends a gauge metric via DogStatsD UDP protocol"""
    tag_str = ""
    if tags:
        tag_str = "|#" + ",".join(tags)
        
    payload = f"{metric_name}:{value}|g{tag_str}"
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(payload.encode('utf-8'), (host, port))
    except Exception as e:
        print(f"Failed to send DogStatsD metric: {e}")

def report_datadog_status(api_key, site, target_name, target_type, is_online, tags=None, message=""):
    """Sends service check and custom metric to Datadog (via Cloud API or Local DogStatsD Agent)"""
    dd_agent_host = os.environ.get("DD_AGENT_HOST")
    dd_agent_port = int(os.environ.get("DD_AGENT_PORT", 8125))
    
    # 1. Report via Local DogStatsD Agent (if configured)
    if dd_agent_host:
        status_code = 0 if is_online else 2
        send_dogstatsd_service_check(dd_agent_host, dd_agent_port, f"home.iot.{target_type}.status", status_code, target_name, message, tags)
        send_dogstatsd_metric(dd_agent_host, dd_agent_port, f"home.iot.{target_type}.online", 1.0 if is_online else 0.0, tags=tags)
        
    # 2. Report via Cloud API (if configured)
    if api_key:
        status = 0 if is_online else 2
        check_payload = {
            "check": f"home.iot.{target_type}.status",
            "host_name": target_name,
            "status": status,
            "timestamp": int(time.time()),
            "message": message,
            "tags": tags or []
        }
        send_to_datadog(api_key, site, "/api/v1/check_run", check_payload)

        metric_payload = {
            "series": [
                {
                    "metric": f"home.iot.{target_type}.online",
                    "points": [[int(time.time()), 1.0 if is_online else 0.0]],
                    "type": "gauge",
                    "host": target_name,
                    "tags": tags or []
                }
            ]
        }
        send_to_datadog(api_key, site, "/api/v1/series", metric_payload)

def load_state():
    """Loads local state containing history of down issues"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_checked": "",
        "statuses": {},
        "failure_history": []
    }

def save_state(state):
    """Saves local state"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def send_alert_email(subject, body_html):
    """Sends notification email using SMTP credentials from .env"""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    
    if not smtp_host or not smtp_user:
        print("SMTP credentials not fully configured. Email skipped.")
        return False
        
    to_addr = os.environ.get("ALERT_EMAIL_TO")
    from_addr = os.environ.get("ALERT_EMAIL_FROM", smtp_user)
    
    if not to_addr:
        print("ALERT_EMAIL_TO not defined. Email skipped.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))
    
    try:
        use_ssl = os.environ.get("SMTP_USE_SSL", "False").lower() == "true"
        use_tls = os.environ.get("SMTP_USE_TLS", "True").lower() == "true"
        
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, int(smtp_port), timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)
            
        if use_tls:
            server.starttls()
            
        if smtp_pass:
            server.login(smtp_user, smtp_pass)
            
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def check_home_assistant(results, state, current_time_str, dd_api_key, dd_site, dd_env, debug=False):
    """Queries Home Assistant REST API for entity status matching regex"""
    import re
    hass_url = os.environ.get("HASS_URL")
    hass_token = os.environ.get("HASS_TOKEN")
    if not hass_url or not hass_token:
        if debug:
            print("Home Assistant URL or Token not configured. HASS checks skipped.")
        return
        
    entity_regex_str = os.environ.get("HASS_ENTITY_REGEXP", ".*node_health.*|.*zigbee.*")
    try:
        entity_regex = re.compile(entity_regex_str, re.IGNORECASE)
    except Exception as e:
        print(f"Invalid HASS_ENTITY_REGEXP pattern: {e}")
        entity_regex = re.compile(".*node_health.*|.*zigbee.*", re.IGNORECASE)

    if debug:
        print(f"Querying Home Assistant at {hass_url} for entity status matching: {entity_regex_str}...")

    url = f"{hass_url.rstrip('/')}/api/states"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {hass_token}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                entities = json.loads(response.read().decode('utf-8'))
                matched_count = 0
                for ent in entities:
                    ent_id = ent.get("entity_id", "")
                    if entity_regex.match(ent_id):
                        matched_count += 1
                        state_val = ent.get("state", "unknown")
                        friendly_name = ent.get("attributes", {}).get("friendly_name", ent_id)
                        
                        is_online = state_val not in ["unavailable", "unknown"]
                        msg = f"State: {state_val}"
                        
                        target_key = f"hass:{ent_id}"
                        results[target_key] = {
                            "name": friendly_name,
                            "type": "hass",
                            "entity_id": ent_id,
                            "is_online": is_online,
                            "message": msg,
                            "building": "newyork"
                        }
                        
                        # Report to Datadog
                        tags = [
                            f"env:{dd_env}",
                            "building:newyork",
                            f"entity_id:{ent_id}",
                            "device_type:hass_sensor"
                        ]
                        report_datadog_status(dd_api_key, dd_site, ent_id, "hass", is_online, tags, msg)
                if debug:
                    print(f"Finished checking {matched_count} matching Home Assistant entities.")
    except Exception as e:
        print(f"Failed to query Home Assistant API: {e}")

def check_services(debug=False):
    """Core check loop scanning all hosts and services"""
    load_env()
    
    # Parse inventories
    hosts_ip = {}
    hosts_ip = parse_inventory_file(NON_TASMOTA_INVENTORY, hosts_ip)
    hosts_ip = parse_inventory_file(ANSIBLE_HOSTS, hosts_ip)
    groups = parse_groups_from_inventory(NON_TASMOTA_INVENTORY)
    tasmota_meta = parse_tasmota_inventory(TASMOTA_INVENTORY)
    
    # State setup
    state = load_state()
    current_time_str = datetime.now(timezone.utc).isoformat()
    state["last_checked"] = current_time_str
    
    # Datadog credentials
    dd_api_key = os.environ.get("DD_API_KEY")
    dd_site = os.environ.get("DD_SITE", "datadoghq.com")
    dd_env = os.environ.get("DD_ENV", "production")
    
    results = {}
    
    # 1. Monitor Hosts (Ping) concurrently
    if debug:
        print(f"Probing {len(hosts_ip)} hosts via ICMP ping concurrently...")
    
    def check_host(host_label, ip):
        if host_label == 'localhost':
            return None
        is_online, msg = ping_host(ip)
        building = get_building_by_host(host_label, tasmota_meta, groups)
        is_tasmota = host_label in tasmota_meta
        device_type = "tasmota" if is_tasmota else "server"
        return host_label, ip, is_online, msg, building, device_type

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_host, host_label, ip): host_label for host_label, ip in hosts_ip.items()}
        for future in as_completed(futures):
            res_val = future.result()
            if res_val is None:
                continue
            host_label, ip, is_online, msg, building, device_type = res_val
            target_key = f"host:{host_label}"
            results[target_key] = {
                "name": host_label,
                "type": "host",
                "device_type": device_type,
                "ip": ip,
                "building": building,
                "is_online": is_online,
                "message": msg
            }
            
            # Report to Datadog
            tags = [
                f"env:{dd_env}",
                f"building:{building}",
                f"device_type:{device_type}",
                "check_type:ping"
            ]
            report_datadog_status(dd_api_key, dd_site, host_label, "host", is_online, tags, msg)

    # 2. Monitor Dynamic & Static Services (TCP Port Check)
    # Compile list of services to probe
    services_to_check = []
    
    # Dynamic services from groups
    # Pi-hole
    for host in groups.get("pihole", []):
        ip = hosts_ip.get(host)
        if ip:
            services_to_check.append({
                "name": f"Pi-hole DNS ({host})",
                "host": host,
                "ip": ip,
                "port": 53,
                "type": "tcp",
                "description": "DNS Server"
            })
            services_to_check.append({
                "name": f"Pi-hole Admin Portal ({host})",
                "host": host,
                "ip": ip,
                "port": 80,
                "type": "tcp",
                "description": "DNS Admin Portal"
            })
            
    # UDM / Gateways
    for host in groups.get("routers", []):
        ip = hosts_ip.get(host)
        if ip:
            services_to_check.append({
                "name": f"Gateway Web Admin ({host})",
                "host": host,
                "ip": ip,
                "port": 443,
                "type": "tcp",
                "description": "Router Gateway Interface"
            })

    # Add static definitions
    for svc in STATIC_SERVICES:
        host = svc["host"]
        ip = hosts_ip.get(host)
        if ip:
            services_to_check.append({
                "name": svc["name"],
                "host": host,
                "ip": ip,
                "port": svc["port"],
                "type": svc["type"],
                "description": svc["description"]
            })

    if debug:
        print(f"Probing {len(services_to_check)} services via TCP concurrently...")

    def check_service(svc):
        host = svc["host"]
        ip = svc["ip"]
        port = svc["port"]
        svc_name = svc["name"]
        
        host_key = f"host:{host}"
        host_online = results.get(host_key, {}).get("is_online", True)
        
        if not host_online:
            is_online, msg = False, "Host is offline"
        else:
            is_online, msg = tcp_check(ip, port)
            
        building = get_building_by_host(host, tasmota_meta, groups)
        return svc_name, host, ip, port, building, is_online, msg

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(check_service, svc): svc["name"] for svc in services_to_check}
        for future in as_completed(futures):
            svc_name, host, ip, port, building, is_online, msg = future.result()
            target_key = f"service:{svc_name}"
            
            results[target_key] = {
                "name": svc_name,
                "type": "service",
                "host": host,
                "ip": ip,
                "port": port,
                "building": building,
                "is_online": is_online,
                "message": msg
            }
            
            # Report to Datadog
            tags = [
                f"env:{dd_env}",
                f"building:{building}",
                f"service:{svc_name.lower().replace(' ', '_')}",
                "check_type:tcp"
            ]
            report_datadog_status(dd_api_key, dd_site, f"{host}-{port}", "service", is_online, tags, msg)

    # 2.5 Monitor Home Assistant Entities (Node Health, Zigbee status)
    check_home_assistant(results, state, current_time_str, dd_api_key, dd_site, dd_env, debug)

    # 3. Analyze Transitions and Trigger Real-time Alerts
    suppressed_buildings = set()
    for key, res in results.items():
        name_lower = res["name"].lower()
        is_gateway = "router" in name_lower or "gateway" in name_lower or "udm" in name_lower
        
        # Check if the gateway service itself is offline, or if the gateway host is offline
        if is_gateway:
            host_key = f"host:{res.get('host', '')}"
            host_online = results.get(host_key, {}).get("is_online", True)
            if not res["is_online"] or not host_online:
                suppressed_buildings.add(res["building"])
                if debug:
                    print(f"Site gateway down for region '{res['building']}'. Suppressing child alerts.")

    new_statuses = {}
    for key, res in results.items():
        name = res["name"]
        t_type = res["type"]
        is_online = res["is_online"]
        msg = res["message"]
        building = res["building"]
        
        # Determine if email alert should be suppressed
        is_gateway = "router" in name.lower() or "gateway" in name.lower() or "udm" in name.lower()
        should_suppress_email = (building in suppressed_buildings) and not is_gateway
        
        prev_state = state["statuses"].get(key, {})
        prev_status = prev_state.get("status", "UP")
        alerted = prev_state.get("alerted", False)
        down_since = prev_state.get("down_since")
        
        if is_online:
            # Service is online
            if prev_status == "DOWN":
                # Recovery transition!
                print(f"RECOVERY: {t_type.upper()} '{name}' is back online!")
                
                # Update failure history item if present
                for hist in state["failure_history"]:
                    if hist["target"] == key and hist["resolved_at"] is None:
                        hist["resolved_at"] = current_time_str
                
                # Send recovery email if we previously alerted and are not suppressed
                if alerted and not should_suppress_email:
                    email_subject = f"✅ RECOVERED: {t_type.capitalize()} {name} is UP"
                    body = f"""
                    <h2>Service Recovery Alert</h2>
                    <p>The following {t_type} has recovered and is now back online:</p>
                    <table border="1" cellpadding="5" style="border-collapse: collapse;">
                        <tr bgcolor="#f2f2f2"><th>Property</th><th>Value</th></tr>
                        <tr><td><b>Name</b></td><td>{name}</td></tr>
                        <tr><td><b>Type</b></td><td>{t_type.capitalize()}</td></tr>
                        <tr><td><b>Location</b></td><td>{building.upper()}</td></tr>
                        <tr><td><b>Resolved At</b></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                        <tr><td><b>Status Message</b></td><td>{msg}</td></tr>
                    </table>
                    """
                    send_alert_email(email_subject, body)
                    
                prev_status = "UP"
                down_since = None
                alerted = False
        else:
            # Service is offline
            if prev_status == "UP":
                # Outage transition!
                print(f"CRITICAL: {t_type.upper()} '{name}' has gone DOWN! Message: {msg}")
                down_since = current_time_str
                prev_status = "DOWN"
                
                # Record to failure log
                state["failure_history"].append({
                    "timestamp": current_time_str,
                    "target": key,
                    "name": name,
                    "type": t_type,
                    "building": building,
                    "error": msg,
                    "resolved_at": None
                })
                
                # Send real-time warning email if not suppressed
                if not should_suppress_email:
                    email_subject = f"🚨 ALERT: {t_type.capitalize()} {name} is DOWN"
                    body = f"""
                    <h2>Service Outage Alert</h2>
                    <p style="color: red; font-size: 16px;"><b>CRITICAL: A monitoring check has failed.</b></p>
                    <table border="1" cellpadding="5" style="border-collapse: collapse;">
                        <tr bgcolor="#f2f2f2"><th>Property</th><th>Value</th></tr>
                        <tr><td><b>Name</b></td><td>{name}</td></tr>
                        <tr><td><b>Type</b></td><td>{t_type.capitalize()}</td></tr>
                        <tr><td><b>Location</b></td><td>{building.upper()}</td></tr>
                        <tr><td><b>Outage Time</b></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                        <tr><td><b>Error Message</b></td><td>{msg}</td></tr>
                    </table>
                    <p>Please log in to your dashboard or console to troubleshoot.</p>
                    """
                    email_sent = send_alert_email(email_subject, body)
                    alerted = email_sent
                else:
                    if debug:
                        print(f"Outage alert for {t_type} '{name}' suppressed due to gateway outage in '{building}'.")
                    alerted = False
                
        new_statuses[key] = {
            "status": prev_status,
            "last_changed": current_time_str if prev_status != prev_state.get("status") else prev_state.get("last_changed", current_time_str),
            "down_since": down_since,
            "alerted": alerted
        }
        
    state["statuses"] = new_statuses
    save_state(state)
    print(f"Health check completed. {len(results)} targets evaluated.")

def send_daily_summary(debug=False):
    """Compiles a summary of all issues from state file and sends a daily digest email"""
    load_env()
    state = load_state()
    
    history = state.get("failure_history", [])
    statuses = state.get("statuses", {})
    
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    
    # Outages occurring in the last 24h
    recent_outages = []
    currently_down = []
    
    # Find currently down items
    for key, info in statuses.items():
        if info.get("status") == "DOWN":
            currently_down.append(key)
            
    for item in history:
        ts = datetime.fromisoformat(item["timestamp"])
        if ts > one_day_ago or item["resolved_at"] is None:
            recent_outages.append(item)
            
    if not recent_outages and not currently_down:
        print("No issues logged in the last 24 hours. Daily digest email skipped.")
        return
        
    # Format email body
    summary_html = f"""
    <h2>Daily Home Lab Status Summary</h2>
    <p>Daily report compiled on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.</p>
    """
    
    # 1. Currently Down Section
    if currently_down:
        summary_html += """
        <h3 style="color: red;">🚨 Services Currently Offline</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <tr bgcolor="#ffcccc">
                <th>Target Name</th>
                <th>Type</th>
                <th>Location</th>
                <th>Down Since</th>
            </tr>
        """
        for key in currently_down:
            parts = key.split(":", 1)
            t_type = parts[0]
            name = parts[1]
            info = statuses[key]
            down_since_str = "Unknown"
            if info.get("down_since"):
                ds_dt = datetime.fromisoformat(info["down_since"]).replace(tzinfo=timezone.utc)
                down_since_str = ds_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
            
            summary_html += f"""
            <tr>
                <td><b>{name}</b></td>
                <td>{t_type.capitalize()}</td>
                <td>{info.get("building", "unknown").upper()}</td>
                <td>{down_since_str}</td>
            </tr>
            """
        summary_html += "</table><br/>"
    else:
        summary_html += '<p style="color: green; font-size: 14px;"><b>✅ All services are currently online.</b></p><br/>'
        
    # 2. Outage History Section
    if recent_outages:
        summary_html += """
        <h3>📋 Outage & Incident Log (Last 24 Hours)</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <tr bgcolor="#f2f2f2">
                <th>Target Name</th>
                <th>Type</th>
                <th>Location</th>
                <th>Triggered At</th>
                <th>Duration</th>
                <th>Status / Error</th>
            </tr>
        """
        for item in recent_outages:
            start_dt = datetime.fromisoformat(item["timestamp"]).replace(tzinfo=timezone.utc)
            start_str = start_dt.astimezone().strftime('%H:%M:%S')
            
            if item["resolved_at"]:
                end_dt = datetime.fromisoformat(item["resolved_at"]).replace(tzinfo=timezone.utc)
                duration = end_dt - start_dt
                duration_str = str(duration).split('.')[0] # HH:MM:SS
                status_str = "Resolved"
                row_style = ""
            else:
                duration = now - start_dt
                duration_str = str(duration).split('.')[0] + " (ongoing)"
                status_str = f"Still Down: {item['error']}"
                row_style = 'style="background-color: #ffe6e6;"'
                
            summary_html += f"""
            <tr {row_style}>
                <td><b>{item['name']}</b></td>
                <td>{item['type'].capitalize()}</td>
                <td>{item.get('building', 'unknown').upper()}</td>
                <td>{start_str}</td>
                <td>{duration_str}</td>
                <td>{status_str}</td>
            </tr>
            """
        summary_html += "</table>"
    else:
        summary_html += "<p>No service disruptions occurred in the last 24 hours.</p>"

    # Add some footer design
    summary_html += """
    <hr/>
    <p style="font-size: 11px; color: #777;">Home Network Overlord Monitoring Service</p>
    """
    
    subject = f"📊 Daily Home Lab Digest: {len(currently_down)} down / {len(recent_outages)} incidents"
    sent = send_alert_email(subject, summary_html)
    
    if sent:
        print("Daily summary email sent successfully.")
        # Clean up history: remove resolved issues, keep active ones
        state["failure_history"] = [item for item in state["failure_history"] if item["resolved_at"] is None]
        save_state(state)
    else:
        print("Failed to send daily summary email.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Home Lab & IoT Services Monitor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Run active probes and update Datadog/send alerts")
    group.add_argument("--daily-summary", action="store_true", help="Send daily digest email of issues")
    parser.add_argument("--debug", action="store_true", help="Enable debug print statements")
    
    args = parser.parse_args()
    
    if args.check:
        check_services(args.debug)
    elif args.daily_summary:
        send_daily_summary(args.debug)
