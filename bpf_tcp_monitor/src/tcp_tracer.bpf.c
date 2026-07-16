#include <linux/bpf.h>
#include <linux/ptrace.h>
#include <linux/socket.h>
#include <linux/in.h>
#include <linux/in6.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

struct tcp_event {
    __u32 pid;
    __u32 src_addr;
    __u32 dst_addr;
    __u16 src_port;
    __u16 dst_port;
    __u8 proto;
    __u8 event_type; // 0 = connect, 1 = close
    __u64 timestamp;
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} events SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, __u64);
    __type(value, struct tcp_event);
} tcp_connections SEC(".maps");

SEC("kprobe/tcp_v4_connect")
int BPF_KPROBE(trace_tcp_v4_connect, struct sock *sk)
{
    struct tcp_event *event;
    struct inet_sock *inet;
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    
    event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event)
        return 0;

    __builtin_memset(event, 0, sizeof(*event));

    inet = (struct inet_sock *)sk;

    event->pid = pid;
    event->src_addr = BPF_CORE_READ(inet, inet_saddr);
    event->dst_addr = BPF_CORE_READ(inet, inet_daddr);
    event->src_port = bpf_ntohs(BPF_CORE_READ(inet, inet_sport));
    event->dst_port = bpf_ntohs(BPF_CORE_READ(inet, inet_dport));
    event->proto = IPPROTO_TCP;
    event->event_type = 0; // connect
    event->timestamp = bpf_ktime_get_ns();

    // Store connection for later close tracking
    __u64 sk_ptr = (__u64)(unsigned long)sk;
    bpf_map_update_elem(&tcp_connections, &sk_ptr, event, BPF_ANY);

    bpf_ringbuf_submit(event, 0);
    return 0;
}

SEC("kprobe/tcp_close")
int BPF_KPROBE(trace_tcp_close, struct sock *sk)
{
    struct tcp_event *stored_event, event = {};
    struct inet_sock *inet;
    __u32 sk_ptr = (__u32)(unsigned long)sk;
    __u32 pid = bpf_get_current_pid_tgid() >> 32;

    // Try to find the stored connection info
    stored_event = bpf_map_lookup_elem(&tcp_connections, &sk_ptr);
    if (stored_event) {
        event = *stored_event;
        bpf_map_delete_elem(&tcp_connections, &sk_ptr);
    } else {
        // If not found, extract what we can from the socket
        inet = (struct inet_sock *)sk;
        event.src_addr = BPF_CORE_READ(inet, inet_saddr);
        event.dst_addr = BPF_CORE_READ(inet, inet_daddr);
        event.src_port = bpf_ntohs(BPF_CORE_READ(inet, inet_sport));
        event.dst_port = bpf_ntohs(BPF_CORE_READ(inet, inet_dport));
        event.proto = IPPROTO_TCP;
    }

    event.pid = pid;
    event.event_type = 1; // close
    event.timestamp = bpf_ktime_get_ns();

    struct tcp_event *ring_event = bpf_ringbuf_reserve(&events, sizeof(*ring_event), 0);
    if (!ring_event)
        return 0;

    *ring_event = event;
    bpf_ringbuf_submit(ring_event, 0);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";