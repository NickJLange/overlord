# TCP Tracer BPF Tool

A high-performance BPF-based TCP connection tracer that logs all TCP open/close events and exposes the 5-tuple (src_ip, src_port, dst_ip, dst_port, protocol) via `/var/run/tcp_tracer/` for minimal performance overhead.

## Features

- **Low Overhead**: Uses eBPF for kernel-space tracing with minimal performance impact
- **Complete 5-Tuple Logging**: Captures source IP, source port, destination IP, destination port, and protocol
- **Runtime Interface**: Exposes events and statistics through `/var/run/tcp_tracer/` for easy monitoring
- **Event Types**: Tracks both TCP connection establishment (CONNECT) and termination (CLOSE)
- **Process Tracking**: Associates connections with process IDs
- **Ring Buffer**: Efficient event delivery from kernel to userspace

## Architecture

The tool consists of two main components:

1. **BPF Program** (`tcp_tracer.bpf.c`): Kernel-space component that hooks into TCP connect/close syscalls
2. **Userspace Loader** (`tcp_tracer.c`): Loads the BPF program and manages the `/var/run/tcp_tracer/` interface

## Output Format

### Events File (`/var/run/tcp_tracer/events`)
```
# TCP Events (5-tuple format)
# Format: timestamp,pid,event_type,src_ip,src_port,dst_ip,dst_port,proto
1640995200000000000,1234,CONNECT,192.168.1.100,45678,93.184.216.34,80,6
1640995201000000000,1234,CLOSE,192.168.1.100,45678,93.184.216.34,80,6
```

### Statistics File (`/var/run/tcp_tracer/stats`)
```
total_events: 1024
connect_events: 512
close_events: 512
buffered_events: 100
```

## Requirements

- Linux kernel >= 5.8 (BPF ring buffers require 5.8+; kprobe support requires 4.15+ but ring buffers are the binding constraint)
- clang compiler
- bpftool utility
- libbpf development package
- Root privileges (CAP_BPF capability)

### Installation of Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install clang llvm bpftool libbpf-dev
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install clang llvm bpftool libbpf-devel
```

## Building

1. Check dependencies:
```bash
make check-deps
```

2. Build the tool:
```bash
make
```

## Running

The tool requires root privileges to load BPF programs:

```bash
sudo make run
```

Or build and run manually:
```bash
make
sudo ./build/tcp_tracer
```

## Installation

Install to system path:
```bash
sudo make install
```

Then run from anywhere:
```bash
sudo tcp_tracer
```

## Monitoring

While the tool is running, monitor events in real-time:

```bash
# Watch events
sudo tail -f /var/run/tcp_tracer/events

# Check statistics
cat /var/run/tcp_tracer/stats
```

## Performance Considerations

- **Ring Buffer**: Uses a 256KB ring buffer for efficient event delivery
- **Batch Updates**: Updates sysfs files every 10 events to reduce I/O overhead
- **Circular Buffering**: Maintains last 1000 events in memory to prevent unbounded growth
- **Minimal Kernel Impact**: BPF programs are optimized for minimal execution time

## Customization

Key parameters that can be modified in the source:

- `MAX_EVENTS`: Number of events to buffer (default: 1000)
- Ring buffer size: Defined in BPF program (default: 256KB)
- Update frequency: Events per sysfs update (default: 10)

## Troubleshooting

1. **Permission Denied**: Ensure running with root privileges
2. **BPF Load Failed**: Check kernel BPF support and libbpf version
3. **No Events**: Verify TCP traffic is occurring and kprobes are attached
4. **Build Errors**: Run `make check-deps` to verify all dependencies

## Security Considerations

- Requires CAP_BPF capability (root privileges)
- Only logs connection metadata, not payload data
- Minimal attack surface through sysfs read-only interface
- No sensitive data exposure (only network 5-tuples and PIDs)

## Known Limitations

- **Pre-connect 5-tuple**: CONNECT events are captured at `kprobe/tcp_v4_connect` entry, before the kernel assigns a source port. Source port may be 0 for outbound connections; use CLOSE events for the complete 5-tuple.
- **IPv4 only**: The BPF program reads `inet_saddr`/`inet_daddr` (IPv4). IPv6 connections are not traced.

## Cleanup

Stop the tool with Ctrl+C. The `/var/run/tcp_tracer/` files are automatically cleaned up on exit.

To remove installed binary:
```bash
sudo make uninstall
```