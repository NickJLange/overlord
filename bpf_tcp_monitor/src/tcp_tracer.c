#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <arpa/inet.h>
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include "tcp_tracer.skel.h"

#define SYSFS_PATH "/sys/tcp_tracer"
#define EVENTS_FILE SYSFS_PATH "/events"
#define STATS_FILE SYSFS_PATH "/stats"
#define MAX_EVENTS 1000

struct tcp_event {
    __u32 pid;
    __u32 src_addr;
    __u32 dst_addr;
    __u16 src_port;
    __u16 dst_port;
    __u8 proto;
    __u8 event_type;
    __u64 timestamp;
};

static struct tcp_tracer_bpf *skel;
static int running = 1;
static struct tcp_event events_buffer[MAX_EVENTS];
static int events_count = 0;
static __u64 total_events = 0;
static __u64 connect_events = 0;
static __u64 close_events = 0;

static void sig_int(int signo)
{
    running = 0;
}

static int create_sysfs_interface(void)
{
    int ret;
    
    // Create main directory
    ret = mkdir(SYSFS_PATH, 0755);
    if (ret < 0 && errno != EEXIST) {
        fprintf(stderr, "Failed to create %s: %s\n", SYSFS_PATH, strerror(errno));
        return -1;
    }

    // Create events file
    int fd = open(EVENTS_FILE, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd < 0) {
        fprintf(stderr, "Failed to create %s: %s\n", EVENTS_FILE, strerror(errno));
        return -1;
    }
    close(fd);

    // Create stats file
    fd = open(STATS_FILE, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd < 0) {
        fprintf(stderr, "Failed to create %s: %s\n", STATS_FILE, strerror(errno));
        return -1;
    }
    close(fd);

    return 0;
}

static void update_sysfs_events(void)
{
    FILE *fp = fopen(EVENTS_FILE, "w");
    if (!fp) {
        fprintf(stderr, "Failed to open %s for writing\n", EVENTS_FILE);
        return;
    }

    fprintf(fp, "# TCP Events (5-tuple format)\n");
    fprintf(fp, "# Format: timestamp,pid,event_type,src_ip,src_port,dst_ip,dst_port,proto\n");
    
    for (int i = 0; i < events_count; i++) {
        struct tcp_event *e = &events_buffer[i];
        struct in_addr src_addr = { .s_addr = e->src_addr };
        struct in_addr dst_addr = { .s_addr = e->dst_addr };
        
        fprintf(fp, "%llu,%u,%s,%s,%u,%s,%u,%u\n",
                e->timestamp,
                e->pid,
                e->event_type == 0 ? "CONNECT" : "CLOSE",
                inet_ntoa(src_addr),
                e->src_port,
                inet_ntoa(dst_addr),
                e->dst_port,
                e->proto);
    }
    
    fclose(fp);
}

static void update_sysfs_stats(void)
{
    FILE *fp = fopen(STATS_FILE, "w");
    if (!fp) {
        fprintf(stderr, "Failed to open %s for writing\n", STATS_FILE);
        return;
    }

    fprintf(fp, "total_events: %llu\n", total_events);
    fprintf(fp, "connect_events: %llu\n", connect_events);
    fprintf(fp, "close_events: %llu\n", close_events);
    fprintf(fp, "buffered_events: %d\n", events_count);
    
    fclose(fp);
}

static int handle_event(void *ctx, void *data, size_t data_sz)
{
    const struct tcp_event *e = data;
    
    if (events_count < MAX_EVENTS) {
        events_buffer[events_count++] = *e;
    } else {
        // Circular buffer - overwrite oldest
        memmove(events_buffer, events_buffer + 1, 
                (MAX_EVENTS - 1) * sizeof(struct tcp_event));
        events_buffer[MAX_EVENTS - 1] = *e;
    }

    total_events++;
    if (e->event_type == 0) {
        connect_events++;
    } else {
        close_events++;
    }

    // Update sysfs files every 10 events for performance
    if (total_events % 10 == 0) {
        update_sysfs_events();
        update_sysfs_stats();
    }

    return 0;
}

int main(int argc, char **argv)
{
    struct ring_buffer *rb = NULL;
    int err;

    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

    // Create sysfs interface
    if (create_sysfs_interface() < 0) {
        fprintf(stderr, "Failed to create sysfs interface\n");
        return 1;
    }

    // Load and verify BPF program
    skel = tcp_tracer_bpf__open();
    if (!skel) {
        fprintf(stderr, "Failed to open BPF skeleton\n");
        return 1;
    }

    err = tcp_tracer_bpf__load(skel);
    if (err) {
        fprintf(stderr, "Failed to load and verify BPF skeleton\n");
        goto cleanup;
    }

    // Attach BPF program
    err = tcp_tracer_bpf__attach(skel);
    if (err) {
        fprintf(stderr, "Failed to attach BPF skeleton\n");
        goto cleanup;
    }

    // Set up ring buffer polling
    rb = ring_buffer__new(bpf_map__fd(skel->maps.events), handle_event, NULL, NULL);
    if (!rb) {
        err = -1;
        fprintf(stderr, "Failed to create ring buffer\n");
        goto cleanup;
    }

    // Set up signal handling
    if (signal(SIGINT, sig_int) == SIG_ERR) {
        fprintf(stderr, "Can't set signal handler: %s\n", strerror(errno));
        goto cleanup;
    }

    printf("TCP tracer started. Events will be written to %s\n", EVENTS_FILE);
    printf("Statistics available at %s\n", STATS_FILE);
    printf("Press Ctrl-C to stop.\n");

    // Main event loop
    while (running) {
        err = ring_buffer__poll(rb, 100 /* timeout, ms */);
        if (err == -EINTR) {
            err = 0;
            break;
        }
        if (err < 0) {
            printf("Error polling ring buffer: %d\n", err);
            break;
        }
    }

    // Final update to sysfs
    update_sysfs_events();
    update_sysfs_stats();

cleanup:
    ring_buffer__free(rb);
    tcp_tracer_bpf__destroy(skel);
    
    // Cleanup sysfs files
    unlink(EVENTS_FILE);
    unlink(STATS_FILE);
    rmdir(SYSFS_PATH);
    
    return err < 0 ? -err : 0;
}