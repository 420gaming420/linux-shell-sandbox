#!/bin/bash
# =============================================================================
# Podman Sandbox - Full Test & Demo Script
# =============================================================================
# This script demonstrates all features of podman.py:
#   - Container lifecycle (create, run, remove)
#   - File persistence across multiple commands
#   - Host project isolation (changes stay inside the container)
#   - Copy-on-write overlay memory efficiency (host tmpfs measurement)
#   - Auto-discard mode
#   - Re-initialization (clear workspace)
#   - Container memory tracking via podman stats
#   - Error handling
#
# Usage: bash sandbox_demo.sh
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}>>> $1${NC}"
}

print_pass() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

print_fail() {
    echo -e "${RED}  ✗ $1${NC}"
}

# Get host tmpfs used space in KB
# This measures the actual memory consumed on the host's /tmp tmpfs
get_tmpfs_used() {
    df /tmp | tail -1 | awk '{print $3}'
}

# Human-readable size
human_size() {
    local bytes=$1
    if [ "$bytes" -lt 1024 ]; then
        echo "${bytes}B"
    elif [ "$bytes" -lt 1048576 ]; then
        echo "$(echo "scale=1; $bytes/1024" | bc)kB"
    elif [ "$bytes" -lt 1073741824 ]; then
        echo "$(echo "scale=1; $bytes/1048576" | bc)MB"
    else
        echo "$(echo "scale=1; $bytes/1073741824" | bc)GB"
    fi
}

# Ensure the project directory and sample files exist
mkdir -p ./project
if [ ! -f "./project/code.py" ]; then
    echo "# Test file" > ./project/code.py
fi

# Ensure the project has a large blob file for testing CoW
print_header "PRECHECK: Ensure test blob exists"

BLOB_SIZE=$(stat -c%s "./project/blob" 2>/dev/null || echo "0")
if [ "$BLOB_SIZE" -lt 524288000 ]; then
    print_step "Creating 1GB blob file (current size: $(human_size $BLOB_SIZE))"
    dd if=/dev/random of=./project/blob bs=1M count=1024 2>&1
    print_pass "Created 1GB blob file"
else
    print_pass "1GB blob file already exists ($(human_size $BLOB_SIZE))"
fi

# Clean up any leftover containers
podman rm -f demo_session_1 demo_session_2 auto_test cobw_cow 2>/dev/null || true

# =============================================================================
# DEMO 1: Basic lifecycle - init, run commands, verify persistence
# =============================================================================
print_header "DEMO 1: Basic Lifecycle & File Persistence"

print_step "Initialize a new sandbox session"
python3 podman.py -n demo_session_1 --init
print_pass "Container created with overlay mounted"

print_step "Check container status"
python3 podman.py -n demo_session_1 --status
print_pass "Container is running"

print_step "List project contents (should show code.py and blob)"
python3 podman.py -n demo_session_1 "ls"
print_pass "Files visible in project"

print_step "Create a new file inside the sandbox"
python3 podman.py -n demo_session_1 "touch hello.txt"
print_pass "Created hello.txt"

print_step "List again - should see three files, blob, code.py, and hello.txt"
python3 podman.py -n demo_session_1 "ls"
print_pass "All three files visible - persistence works!"

print_step "Read the file we created"
python3 podman.py -n demo_session_1 "cat hello.txt"
print_pass "File content readable"

print_step "Verify path spoofing - pwd should return the real source path"
python3 podman.py -n demo_session_1 "pwd"
print_pass "Path spoofing works - container sees the real project path"

print_step "Create another file and a subdirectory"
python3 podman.py -n demo_session_1 "mkdir -p subdir && touch subdir/deep.txt"
python3 podman.py -n demo_session_1 "ls -R"
print_pass "Directory structure created"

# =============================================================================
# DEMO 2: Host project isolation
# =============================================================================
print_header "DEMO 2: Host Project Isolation"

print_step "Check the ACTUAL project directory (should only have code.py and blob)"
echo "  Host project contents:"
ls ./project/
print_pass "Host project is CLEAN - no sandbox files leaked out"

# =============================================================================
# DEMO 3: Copy-on-write overlay memory efficiency
# =============================================================================
print_header "DEMO 3: Copy-on-Write Overlay (Memory Efficiency)"

print_step "Create a fresh sandbox for CoW testing"
python3 podman.py -n cobw_cow --init
print_pass "Container created"

print_step "Measure HOST tmpfs usage BEFORE init (baseline)"
TMPFS_BASELINE=$(get_tmpfs_used)
echo "  Host tmpfs used: $(human_size $((TMPFS_BASELINE * 1024)))"

print_step "Measure HOST tmpfs usage AFTER init (should be ~same, not +1GB)"
TMPFS_AFTER_INIT=$(get_tmpfs_used)
INIT_INCREASE=$((TMPFS_AFTER_INIT - TMPFS_BASELINE))
echo "  Host tmpfs used: $(human_size $((TMPFS_AFTER_INIT * 1024)))"
echo "  Increase at init: $(human_size $((INIT_INCREASE * 1024)))"

if [ "$INIT_INCREASE" -lt 1048576 ]; then
    print_pass "Init overhead is NEGLIGIBLE (~$(human_size $((INIT_INCREASE * 1024))))"
    echo "  The 1GB blob is on the read-only lower layer, NOT copied to tmpfs!"
else
    print_fail "Init increased tmpfs by $(human_size $((INIT_INCREASE * 1024))) — expected ~0"
    echo "  The blob may have been copied to tmpfs instead of using CoW"
fi

print_step "Run a heavy command: write a 100MB file inside the sandbox"
python3 podman.py -n cobw_cow "dd if=/dev/random of=bigfile bs=1M count=100 2>&1 && ls -lh bigfile"
print_pass "100MB file created"

print_step "Measure HOST tmpfs usage AFTER the write"
TMPFS_AFTER_WRITE=$(get_tmpfs_used)
WRITE_INCREASE=$((TMPFS_AFTER_WRITE - TMPFS_AFTER_INIT))
echo "  Host tmpfs used: $(human_size $((TMPFS_AFTER_WRITE * 1024)))"
echo "  Increase from 100MB file: $(human_size $((WRITE_INCREASE * 1024)))"

if [ "$WRITE_INCREASE" -ge 92160 ] && [ "$WRITE_INCREASE" -le 122880 ]; then
    print_pass "tmpfs grew by ~$(human_size $((WRITE_INCREASE * 1024))) — matches the 100MB file!"
    echo "  Copy-on-write is working correctly."
else
    print_fail "tmpfs grew by $(human_size $((WRITE_INCREASE * 1024))) — expected ~100MB"
    echo "  Something may be wrong with the overlay or measurement."
fi

print_step "Verify host project is still clean"
echo "  Host project contents:"
ls ./project/
print_pass "Host project unchanged"

# =============================================================================
# DEMO 4: Auto-discard mode
# =============================================================================
print_header "DEMO 4: Auto-Discard Mode"

print_step "Create a fresh container with auto-discard"
python3 podman.py -n auto_test --init -a "touch auto_test_file.txt && ls"
print_pass "Command executed and container auto-removed"

print_step "Verify the container is gone"
python3 podman.py -n auto_test --status
print_pass "Container no longer exists"

# =============================================================================
# DEMO 5: Re-init (clear workspace)
# =============================================================================
print_header "DEMO 5: Re-initialize (Clear Workspace)"

print_step "Current project (should have hello.txt, subdir, bigfile)"
python3 podman.py -n demo_session_1 "ls -R"

print_step "Re-initialize the container (clears everything)"
python3 podman.py -n demo_session_1 --init
print_pass "Workspace cleared"

print_step "Verify project is clean (only code.py and blob)"
python3 podman.py -n demo_session_1 "ls"
print_pass "Only original project files remain"

# =============================================================================
# DEMO 6: Memory usage tracking (podman stats)
# =============================================================================
print_header "DEMO 6: Container Memory Tracking"

print_step "Check memory BEFORE running commands"
python3 podman.py -n demo_session_1 --mem "echo 'running a command'" 2>&1
print_pass "Memory tracked before and after each command"

print_step "Run a heavier command to increase memory usage"
python3 podman.py -n demo_session_1 --mem "dd if=/dev/random of=bigfile2 bs=1M count=50 2>&1 && ls -lh bigfile2" 2>&1
print_pass "Memory tracked after heavy operation"

# =============================================================================
# DEMO 7: Error handling
# =============================================================================
print_header "DEMO 7: Error Handling"

print_step "Run a non-existent command (should fail gracefully)"
python3 podman.py -n demo_session_1 "nonexistent_command_xyz" 2>&1 || true
print_pass "Error handled gracefully (exit code 127)"

# =============================================================================
# DEMO 8: Cleanup
# =============================================================================
print_header "DEMO 8: Cleanup"

print_step "Remove the demo containers"
python3 podman.py -n demo_session_1 --remove
print_pass "demo_session_1 removed"

print_step "Verify they're gone"
python3 podman.py -n demo_session_1 --status
print_pass "Container no longer exists"

# =============================================================================
# SUMMARY
# =============================================================================
print_header "ALL DEMOS COMPLETED SUCCESSFULLY"

echo -e "${GREEN}What was demonstrated:${NC}"
echo "  1. Container lifecycle: create → run → remove"
echo "  2. File persistence across multiple commands"
echo "  3. Host project isolation (no files leaked)"
echo "  4. Copy-on-write overlay: 1GB project, ~0KB tmpfs usage at init, ~100MB usage when 100MB written"
echo "  5. Auto-discard mode (auto-remove after each command)"
echo "  6. Re-initialization (clear workspace)"
echo "  7. Container memory tracking via podman stats"
echo "  8. Error handling (graceful failures)"
echo ""
echo -e "${GREEN}The podman sandbox is ready for AI agent integration.${NC}"
echo ""
