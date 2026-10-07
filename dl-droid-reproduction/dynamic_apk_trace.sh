#!/usr/bin/env bash

# ============================================================
# Android APK Dynamic Behavior Collection Script
# ============================================================
#
# Purpose:
#   Install an APK on an Android emulator, launch it, collect
#   runtime evidence, and save everything into a timestamped
#   directory.
#
# What this script collects:
#   1. APK/package information
#   2. Android device information
#   3. Runtime logcat
#   4. Process information
#   5. Activity/task information
#   6. Network/socket information
#   7. Package permissions
#   8. Package metadata
#   9. A final snapshot after the app is exercised
#
# Important:
#   - This does NOT provide a complete Linux syscall trace.
#   - For actual syscall-level tracing, use strace/Perfetto later.
#   - The user should manually interact with the app while logcat
#     is running to generate meaningful runtime behavior.
#
# Usage:
#   ./dynamic_apk_trace.sh /path/to/app.apk
#
# Example:
#   ./dynamic_apk_trace.sh ~/Downloads/MyApp.apk
#
# ============================================================

set -u

# -----------------------------
# Configuration
# -----------------------------

ADB="${ADB:-adb}"
SERIAL="${ANDROID_SERIAL:-}"

# Output directory
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BASE_DIR="$HOME/apk_dynamic_traces"
RUN_DIR="$BASE_DIR/run_$TIMESTAMP"

mkdir -p "$RUN_DIR"

# -----------------------------
# Helper functions
# -----------------------------

log() {
    echo "[+] $*"
}

warn() {
    echo "[!] $*" >&2
}

die() {
    echo "[ERROR] $*" >&2
    exit 1
}

run_adb() {
    if [[ -n "$SERIAL" ]]; then
        "$ADB" -s "$SERIAL" "$@"
    else
        "$ADB" "$@"
    fi
}

# -----------------------------
# Check APK argument
# -----------------------------

if [[ $# -lt 1 ]]; then
    echo
    echo "Usage:"
    echo "  $0 /path/to/app.apk"
    echo
    echo "Example:"
    echo "  $0 ~/Downloads/MyApp.apk"
    echo
    exit 1
fi

APK="$1"

if [[ ! -f "$APK" ]]; then
    die "APK file not found: $APK"
fi

log "APK: $APK"
log "Output directory: $RUN_DIR"

# -----------------------------
# Check ADB
# -----------------------------

command -v "$ADB" >/dev/null 2>&1 || \
    die "adb command not found. Install Android platform-tools first."

# -----------------------------
# Detect emulator/device
# -----------------------------

log "Checking connected Android devices..."

mapfile -t DEVICES < <(
    "$ADB" devices | awk '$2 == "device" {print $1}'
)

if [[ ${#DEVICES[@]} -eq 0 ]]; then
    die "No Android device/emulator detected."
fi

if [[ -z "$SERIAL" ]]; then
    if [[ ${#DEVICES[@]} -gt 1 ]]; then
        echo
        warn "Multiple devices detected:"
        printf '  %s\n' "${DEVICES[@]}"
        echo
        echo "Run again like:"
        echo "  ANDROID_SERIAL=${DEVICES[0]} $0 \"$APK\""
        echo
        exit 1
    fi

    SERIAL="${DEVICES[0]}"
fi

log "Using device: $SERIAL"

# -----------------------------
# Device information
# -----------------------------

log "Collecting device information..."

run_adb shell getprop > "$RUN_DIR/device_getprop.txt"

{
    echo "=== Device ==="
    echo "$SERIAL"
    echo

    echo "=== Android Version ==="
    run_adb shell getprop ro.build.version.release

    echo
    echo "=== SDK ==="
    run_adb shell getprop ro.build.version.sdk

    echo
    echo "=== CPU ABI ==="
    run_adb shell getprop ro.product.cpu.abi

    echo
    echo "=== Model ==="
    run_adb shell getprop ro.product.model

    echo
    echo "=== Manufacturer ==="
    run_adb shell getprop ro.product.manufacturer

    echo
    echo "=== ADB identity ==="
    run_adb shell id
} > "$RUN_DIR/device_summary.txt"

# -----------------------------
# APK metadata
# -----------------------------

log "Collecting APK metadata..."

if command -v aapt >/dev/null 2>&1; then
    aapt dump badging "$APK" > "$RUN_DIR/apk_badging.txt" 2>&1
else
    warn "aapt not found; APK badging will be skipped."
    echo "aapt not installed." > "$RUN_DIR/apk_badging.txt"
fi

# -----------------------------
# Install APK
# -----------------------------

log "Installing APK..."

INSTALL_OUTPUT="$(
    run_adb install -r "$APK" 2>&1
)"

echo "$INSTALL_OUTPUT" > "$RUN_DIR/install_result.txt"

if ! echo "$INSTALL_OUTPUT" | grep -q "Success"; then
    cat "$RUN_DIR/install_result.txt"
    die "APK installation failed."
fi

log "APK installed successfully."

# -----------------------------
# Find package name
# -----------------------------

log "Detecting installed package..."

APK_BASENAME="$(basename "$APK")"

PACKAGE_NAME=""

# First try aapt output
if [[ -s "$RUN_DIR/apk_badging.txt" ]]; then
    PACKAGE_NAME="$(
        grep '^package:' "$RUN_DIR/apk_badging.txt" |
        sed -n "s/.*name='\([^']*\)'.*/\1/p" |
        head -n 1
    )"
fi

# Fallback: inspect packages and search using APK filename
if [[ -z "$PACKAGE_NAME" ]]; then
    PACKAGE_NAME="$(
        run_adb shell pm list packages |
        sed 's/^package://' |
        grep -i "${APK_BASENAME%.*}" |
        head -n 1
    )"
fi

if [[ -z "$PACKAGE_NAME" ]]; then
    die "Could not determine package name."
fi

log "Package: $PACKAGE_NAME"

echo "$PACKAGE_NAME" > "$RUN_DIR/package_name.txt"

# -----------------------------
# Package information
# -----------------------------

log "Collecting package information..."

run_adb shell dumpsys package "$PACKAGE_NAME" \
    > "$RUN_DIR/package_dumpsys.txt"

run_adb shell pm path "$PACKAGE_NAME" \
    > "$RUN_DIR/package_path.txt"

run_adb shell pm list permissions -g -d \
    > "$RUN_DIR/device_permissions.txt"

# Try to get package-specific permission information
grep -A 300 -F "$PACKAGE_NAME" "$RUN_DIR/package_dumpsys.txt" \
    > "$RUN_DIR/package_permissions.txt" 2>/dev/null || true

# -----------------------------
# Determine launch activity
# -----------------------------

log "Finding launch activity..."

LAUNCH_COMPONENT="$(
    run_adb shell cmd package resolve-activity \
        --brief \
        "$PACKAGE_NAME" 2>/dev/null |
        tail -n 1
)"

if [[ -z "$LAUNCH_COMPONENT" || "$LAUNCH_COMPONENT" == "No activity found" ]]; then
    warn "Could not automatically determine launch activity."
    LAUNCH_COMPONENT=""
else
    log "Launch component: $LAUNCH_COMPONENT"
fi

echo "$LAUNCH_COMPONENT" > "$RUN_DIR/launch_component.txt"

# -----------------------------
# Clear old logcat
# -----------------------------

log "Clearing old logcat..."

run_adb logcat -c

# -----------------------------
# Initial snapshots
# -----------------------------

log "Collecting initial snapshots..."

run_adb shell ps -A \
    > "$RUN_DIR/process_before.txt"

run_adb shell dumpsys activity activities \
    > "$RUN_DIR/activity_before.txt"

run_adb shell cat /proc/net/tcp \
    > "$RUN_DIR/tcp_before.txt" 2>&1 || true

run_adb shell cat /proc/net/tcp6 \
    > "$RUN_DIR/tcp6_before.txt" 2>&1 || true

run_adb shell dumpsys netstats \
    > "$RUN_DIR/netstats_before.txt" 2>&1 || true

# -----------------------------
# Start logcat capture
# -----------------------------

LOGCAT_FILE="$RUN_DIR/logcat.txt"

log "Starting runtime logcat capture..."
log "Logcat file: $LOGCAT_FILE"

run_adb logcat -v threadtime > "$LOGCAT_FILE" 2>&1 &

LOGCAT_PID=$!

echo "$LOGCAT_PID" > "$RUN_DIR/logcat_host_pid.txt"

sleep 2

# -----------------------------
# Launch application
# -----------------------------

if [[ -n "$LAUNCH_COMPONENT" ]]; then

    log "Launching application..."

    run_adb shell am force-stop "$PACKAGE_NAME"

    sleep 1

    run_adb shell am start -W "$LAUNCH_COMPONENT" \
        > "$RUN_DIR/launch_result.txt" 2>&1

else

    warn "Automatic launch skipped."
    warn "Launch the application manually from the emulator."
fi

# -----------------------------
# Runtime interaction phase
# -----------------------------

echo
echo "============================================================"
echo " RUNTIME INTERACTION PHASE"
echo "============================================================"
echo
echo "The APK is now installed and logcat is being captured."
echo
echo "Manually use the application in the emulator now."
echo
echo "Recommended actions:"
echo "  1. Open the main screen"
echo "  2. Navigate through available screens"
echo "  3. Grant/deny permissions when appropriate"
echo "  4. Select an image/file if the app supports it"
echo "  5. Trigger important features"
echo "  6. Observe network-related features"
echo "  7. Return to the home screen"
echo "  8. Open the app again"
echo
echo "Do NOT perform actions outside the APK that you do not"
echo "intend to include in the analysis."
echo
echo "Press ENTER when you are finished interacting with the APK."
echo

read -r

# -----------------------------
# Stop logcat
# -----------------------------

log "Stopping logcat capture..."

kill "$LOGCAT_PID" 2>/dev/null || true

wait "$LOGCAT_PID" 2>/dev/null || true

# -----------------------------
# Final snapshots
# -----------------------------

log "Collecting final runtime snapshots..."

run_adb shell ps -A \
    > "$RUN_DIR/process_after.txt"

run_adb shell dumpsys activity activities \
    > "$RUN_DIR/activity_after.txt"

run_adb shell cat /proc/net/tcp \
    > "$RUN_DIR/tcp_after.txt" 2>&1 || true

run_adb shell cat /proc/net/tcp6 \
    > "$RUN_DIR/tcp6_after.txt" 2>&1 || true

run_adb shell dumpsys netstats \
    > "$RUN_DIR/netstats_after.txt" 2>&1 || true

# -----------------------------
# Filter app-specific logcat
# -----------------------------

log "Creating app-specific logcat..."

grep -iE "$PACKAGE_NAME|AndroidRuntime|FATAL EXCEPTION|SecurityException|denied|permission|network|http|https|socket|ssl|firebase|webview" \
    "$LOGCAT_FILE" \
    > "$RUN_DIR/logcat_relevant.txt" 2>/dev/null || true

# -----------------------------
# Package process filter
# -----------------------------

grep -i "$PACKAGE_NAME" \
    "$RUN_DIR/process_after.txt" \
    > "$RUN_DIR/process_app_only.txt" 2>/dev/null || true

# -----------------------------
# Activity filter
# -----------------------------

grep -i "$PACKAGE_NAME" \
    "$RUN_DIR/activity_after.txt" \
    > "$RUN_DIR/activity_app_only.txt" 2>/dev/null || true

# -----------------------------
# Create basic summary
# -----------------------------

SUMMARY="$RUN_DIR/SUMMARY.txt"

{
    echo "============================================================"
    echo " APK DYNAMIC ANALYSIS SUMMARY"
    echo "============================================================"
    echo
    echo "APK:"
    echo "$APK"
    echo
    echo "Package:"
    echo "$PACKAGE_NAME"
    echo
    echo "Device:"
    echo "$SERIAL"
    echo
    echo "Android:"
    run_adb shell getprop ro.build.version.release
    echo
    echo "SDK:"
    run_adb shell getprop ro.build.version.sdk
    echo
    echo "ABI:"
    run_adb shell getprop ro.product.cpu.abi
    echo
    echo "Launch component:"
    cat "$RUN_DIR/launch_component.txt"
    echo
    echo "Output directory:"
    echo "$RUN_DIR"
    echo
    echo "Files collected:"
    find "$RUN_DIR" -maxdepth 1 -type f -printf "  %f\n" | sort
    echo
    echo "============================================================"
    echo " IMPORTANT"
    echo "============================================================"
    echo
    echo "logcat.txt:"
    echo "  Full Android runtime log."
    echo
    echo "logcat_relevant.txt:"
    echo "  Filtered log containing package/runtime/network related lines."
    echo
    echo "process_before.txt / process_after.txt:"
    echo "  Process snapshots before and after interaction."
    echo
    echo "activity_before.txt / activity_after.txt:"
    echo "  Android Activity/Task state."
    echo
    echo "tcp_before.txt / tcp_after.txt:"
    echo "  Kernel TCP socket tables."
    echo
    echo "netstats_before.txt / netstats_after.txt:"
    echo "  Android network statistics."
    echo
    echo "package_dumpsys.txt:"
    echo "  Package metadata, activities, services, permissions and"
    echo "  other package-manager information."
    echo
    echo "NOTE:"
    echo "  These files are runtime evidence, not a complete syscall trace."
    echo "  Actual Linux syscall tracing requires a syscall tracing tool."
    echo
} > "$SUMMARY"

# -----------------------------
# Optional archive
# -----------------------------

log "Creating compressed archive..."

tar -czf "$RUN_DIR.tar.gz" -C "$BASE_DIR" "$(basename "$RUN_DIR")"

# -----------------------------
# Done
# -----------------------------

echo
echo "============================================================"
echo " ANALYSIS COMPLETE"
echo "============================================================"
echo
echo "Package: $PACKAGE_NAME"
echo
echo "Results:"
echo "  $RUN_DIR"
echo
echo "Archive:"
echo "  $RUN_DIR.tar.gz"
echo
echo "Main files:"
echo "  logcat.txt"
echo "  logcat_relevant.txt"
echo "  process_before.txt"
echo "  process_after.txt"
echo "  activity_before.txt"
echo "  activity_after.txt"
echo "  tcp_before.txt"
echo "  tcp_after.txt"
echo "  netstats_before.txt"
echo "  netstats_after.txt"
echo "  package_dumpsys.txt"
echo "  package_permissions.txt"
echo "  SUMMARY.txt"
echo
echo "============================================================"
