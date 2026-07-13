# TCP Tracer BPF Tool Makefile

# Check for required tools
CLANG ?= clang
LLC ?= llc
BPFTOOL ?= bpftool

# Directories
SRC_DIR = src
BUILD_DIR = build

# Source files
BPF_SRC = $(SRC_DIR)/tcp_tracer.bpf.c
USER_SRC = $(SRC_DIR)/tcp_tracer.c
SKEL_H = $(BUILD_DIR)/tcp_tracer.skel.h
BPF_OBJ = $(BUILD_DIR)/tcp_tracer.bpf.o
TARGET = $(BUILD_DIR)/tcp_tracer

# Compiler flags
CFLAGS = -O2 -g -Wall -Werror
BPF_CFLAGS = -O2 -g -target bpf -D__TARGET_ARCH_x86_64

# Libraries
LIBS = -lbpf -lelf -lz

# Default target
all: $(TARGET)

# Create build directory
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Compile BPF program
$(BPF_OBJ): $(BPF_SRC) | $(BUILD_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

# Generate BPF skeleton
$(SKEL_H): $(BPF_OBJ)
	$(BPFTOOL) gen skeleton $< > $@

# Compile userspace program
$(TARGET): $(USER_SRC) $(SKEL_H) | $(BUILD_DIR)
	$(CLANG) $(CFLAGS) -I$(BUILD_DIR) $< -o $@ $(LIBS)

# Install target (requires root)
install: $(TARGET)
	@if [ "$$(id -u)" != "0" ]; then \
		echo "Installation requires root privileges. Run: sudo make install"; \
		exit 1; \
	fi
	cp $(TARGET) /usr/local/bin/
	echo "TCP tracer installed to /usr/local/bin/tcp_tracer"

# Uninstall target (requires root)
uninstall:
	@if [ "$$(id -u)" != "0" ]; then \
		echo "Uninstallation requires root privileges. Run: sudo make uninstall"; \
		exit 1; \
	fi
	rm -f /usr/local/bin/tcp_tracer
	echo "TCP tracer removed from /usr/local/bin/"

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)

# Check dependencies
check-deps:
	@echo "Checking dependencies..."
	@which $(CLANG) >/dev/null || (echo "Error: clang not found" && exit 1)
	@which $(BPFTOOL) >/dev/null || (echo "Error: bpftool not found" && exit 1)
	@pkg-config --exists libbpf || (echo "Error: libbpf development package not found" && exit 1)
	@echo "All dependencies found!"

# Run target (requires root)
run: $(TARGET)
	@if [ "$$(id -u)" != "0" ]; then \
		echo "Running BPF programs requires root privileges. Run: sudo make run"; \
		exit 1; \
	fi
	$(TARGET)

# Help target
help:
	@echo "TCP Tracer BPF Tool"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Build the tcp_tracer binary"
	@echo "  install    - Install tcp_tracer to /usr/local/bin (requires root)"
	@echo "  uninstall  - Remove tcp_tracer from /usr/local/bin (requires root)"
	@echo "  run        - Build and run tcp_tracer (requires root)"
	@echo "  clean      - Remove build artifacts"
	@echo "  check-deps - Check for required dependencies"
	@echo "  help       - Show this help message"
	@echo ""
	@echo "Requirements:"
	@echo "  - clang compiler"
	@echo "  - bpftool utility"
	@echo "  - libbpf development package"
	@echo "  - Root privileges to run (BPF programs require CAP_BPF)"

.PHONY: all install uninstall clean check-deps run help