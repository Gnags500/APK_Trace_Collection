```bash
#!/usr/bin/env bash

set -u
set -o pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SDK_DIR="${HOME}/Android/Sdk"
EMULATOR_DIR="${SDK_DIR}/emulator"
EMULATOR_AVD="Pixel_4"

APK_DIR="${PROJECT}/apk"
RESULTS_DIR="${PROJECT}/results"
LOGS_DIR="${PROJECT}/logs"

ADB="${ADB:-adb}"
SERIAL="${ANDROID_SERIAL:-}"

FRIDA_ENV="${HOME}/frida-env"

COLLECTOR="${PROJECT}/frida/collect_event.js"
PARSER="${PROJECT}/frida/parse_events.py"

PACKAGE_INFO="${PROJECT}/extractor/package_info.py"
PERMISSIONS="${PROJECT}/extractor/permissions.py"
EXPLORER="${PROJECT}/crawler/ui_explorer.py"

FRIDA_PROCESS=""
FRIDA_LOG_FD=""
RAW_LOG=""
EVENTS_JSON=""

APK=""
PACKAGE=""
UI=false
FRIDA_TIME=60
START_EMULATOR=false


# ============================================================
# Utility functions
# ============================================================

die() {
    echo
    echo "[!] $*" >&2
    exit 1
}


command_exists() {
    command -v "$1" >/dev/null 2>&1
}


run_command() {
    echo
    echo "[CMD] $*"

    "$@"
    local rc=$?

    if [[ $rc -ne 0 ]]; then
        echo "[!] Command failed with exit code $rc: $*"
        return "$rc"
    fi

    return 0
}


print_header() {
    echo
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}


# ============================================================
# Argument parsing
# ============================================================

usage() {
    cat <<EOF
DL-Droid reproduction analysis controller

Usage:
  $0 --apk PATH [OPTIONS]

Required:
  --apk PATH              Path to APK

Optional:
  --package NAME          Android package name
  --ui                    Run UI explorer
  --frida-time SECONDS    Frida collection time (default: 60)
  --start-emulator        Start existing Pixel_4 AVD when no device exists
  -h, --help              Show this help

Examples:
  $0 --apk ./apk/app.apk

  $0 --apk ./apk/app.apk \\
     --package com.example.app

  $0 --apk ./apk/app.apk \\
     --ui \\
     --frida-time 120

  $0 --apk ./apk/app.apk \\
     --start-emulator
EOF
}


while [[ $# -gt 0 ]]; do

    case "$1" in

        --apk)
            [[ $# -ge 2 ]] || die "--apk requires a value"
            APK="$2"
            shift 2
            ;;

        --package)
            [[ $# -ge 2 ]] || die "--package requires a value"
            PACKAGE="$2"
            shift 2
            ;;

        --ui)
            UI=true
            shift
            ;;

        --frida-time)
            [[ $# -ge 2 ]] || die "--frida-time requires a value"

            if ! [[ "$2" =~ ^[0-9]+$ ]]; then
                die "--frida-time must be an integer"
            fi

            FRIDA_TIME="$2"
            shift 2
            ;;

        --start-emulator)
            START_EMULATOR=true
            shift
            ;;

        -h|--help)
            usage
            exit 0
            ;;

        *)
            echo "[!] Unknown argument: $1"
            echo
            usage
            exit 1
            ;;

    esac

done


[[ -n "$APK" ]] || {
    echo "[!] --apk is required."
    echo
    usage
    exit 1
}


# ============================================================
# Resolve APK path
# ============================================================

if [[ "$APK" != /* ]]; then
    APK="$(cd "$(dirname "$APK")" 2>/dev/null && pwd)/$(basename "$APK")" \
        || die "Could not resolve APK path."
fi

[[ -f "$APK" ]] || die "APK does not exist: $APK"


# ============================================================
# ADB
# ============================================================

run_adb() {
    if [[ -n "$SERIAL" ]]; then
        "$ADB" -s "$SERIAL" "$@"
    else
        "$ADB" "$@"
    fi
}


get_connected_devices() {

    command_exists "$ADB" || die "Required command is unavailable: $ADB"

    "$ADB" devices 2>/dev/null |
        awk '
            NR > 1 && NF >= 2 && $2 == "device" {
                print $1
            }
        '
}


start_emulator() {

    print_header "Starting Android emulator"

    local emulator="${EMULATOR_DIR}/emulator"

    if [[ ! -x "$emulator" ]]; then
        echo "[!] Emulator executable not found: $emulator"
        exit 1
    fi

    echo "[+] Starting AVD: ${EMULATOR_AVD}"

    "$emulator" \
        -avd "$EMULATOR_AVD" \
        >/dev/null 2>&1 &

    local emulator_pid=$!

    local timeout=120
    local start_time
    start_time=$(date +%s)

    while true; do

        if ! kill -0 "$emulator_pid" 2>/dev/null; then
            wait "$emulator_pid" 2>/dev/null
            local rc=$?

            echo "[!] Emulator process exited unexpectedly with code $rc."
            exit 1
        fi

        local devices
        devices="$(get_connected_devices)"

        if [[ -n "$devices" ]]; then
            echo "[+] Emulator is ready: ${EMULATOR_AVD}"
            return 0
        fi

        local now
        now=$(date +%s)

        local elapsed=$((now - start_time))

        if (( elapsed >= timeout )); then
            echo "[!] Timeout waiting for ${EMULATOR_AVD} to appear in ADB."

            kill "$emulator_pid" 2>/dev/null || true

            sleep 2

            if kill -0 "$emulator_pid" 2>/dev/null; then
                kill -9 "$emulator_pid" 2>/dev/null || true
            fi

            exit 1
        fi

        local remaining=$((timeout - elapsed))

        echo "[DEBUG] Waiting for ADB to detect ${EMULATOR_AVD} (${remaining}s remaining)"

        sleep 2

    done
}


check_adb() {

    print_header "Checking ADB"

    command_exists adb || die "Required command is unavailable: adb"

    local devices
    devices="$(get_connected_devices)"

    if [[ -z "$devices" ]]; then

        if [[ "$START_EMULATOR" != true ]]; then
            echo "[!] No Android device/emulator detected."
            echo "[!] Start your emulator and run this script again."
            exit 1
        fi

        start_emulator

        devices="$(get_connected_devices)"

        if [[ -z "$devices" ]]; then
            echo "[!] ADB did not detect the emulator after startup."
            exit 1
        fi
    fi

    mapfile -t device_list < <(printf '%s\n' "$devices")

    if [[ -z "$SERIAL" ]]; then
        if (( ${#device_list[@]} > 1 )); then
            echo "[!] Multiple Android devices are connected:"
            printf '    %s\n' "${device_list[@]}"
            echo "[!] Set ANDROID_SERIAL to select one."
            exit 1
        fi

        SERIAL="${device_list[0]}"
    fi

    if ! "$ADB" devices 2>/dev/null | awk -v serial="$SERIAL" '$1 == serial && $2 == "device" {found=1} END {exit found ? 0 : 1}'; then
        echo "[!] ADB device not available: ${SERIAL}"
        exit 1
    fi

    echo "[+] Selected device: ${SERIAL}"
}


# ============================================================
# Frida
# ============================================================

check_frida() {

    print_header "Checking Frida environment"

    local frida_ps="${FRIDA_ENV}/bin/frida-ps"

    if [[ ! -x "$frida_ps" ]]; then
        echo "[!] Could not find: $frida_ps"
        echo "[!] Your existing Frida environment was expected here."
        exit 1
    fi

    local output

    if ! output="$("$frida_ps" -U 2>&1)"; then
        echo "[!] frida-ps -U failed:"
        echo "$output"
        exit 1
    fi

    echo "[+] Frida USB connection works."
}


# ============================================================
# APK package extraction
# ============================================================

get_package_from_apk() {

    print_header "Reading APK package name"

    local candidates=(
        "${SDK_DIR}/build-tools/35.0.0/aapt"
        "${SDK_DIR}/build-tools/34.0.0/aapt"
        "${SDK_DIR}/build-tools/33.0.0/aapt"
    )

    local aapt=""

    for candidate in "${candidates[@]}"; do
        if [[ -x "$candidate" ]]; then
            aapt="$candidate"
            break
        fi
    done

    if [[ -z "$aapt" ]]; then
        if command_exists aapt; then
            aapt="$(command -v aapt)"
        fi
    fi

    if [[ -z "$aapt" ]]; then
        echo "[!] Could not find aapt."
        echo "[!] For now, provide --package manually."
        exit 1
    fi

    local output

    if ! output="$("$aapt" dump badging "$APK" 2>&1)"; then
        echo "[!] aapt could not read the APK."
        echo "$output"
        exit 1
    fi

    PACKAGE="$(
        echo "$output" |
            sed -n "s/^package:.*name='\([^']*\)'.*/\1/p" |
            head -n 1
    )"

    if [[ -z "$PACKAGE" ]]; then
        PACKAGE="$(
            echo "$output" |
                sed -n 's/^package:.*name="\([^"]*\)".*/\1/p' |
                head -n 1
        )"
    fi

    if [[ -z "$PACKAGE" ]]; then
        echo "[!] Could not determine package name."
        exit 1
    fi

    echo "[+] Package: ${PACKAGE}"
}


# ============================================================
# APK installation
# ============================================================

install_apk() {

    print_header "Installing APK"

    local output
    local rc

    output="$(run_adb install -r "$APK" 2>&1)"
    rc=$?

    echo "$output"

    if [[ $rc -ne 0 ]]; then
        echo "[!] APK installation failed."
        exit 1
    fi

    if ! grep -Fq "Success" <<<"$output"; then
        echo "[!] APK installation did not report success."
        exit 1
    fi

    echo "[+] APK installed."
}


# ============================================================
# Launch application
# ============================================================

launch_app() {

    print_header "Launching application"

    local launch_component
    launch_component="$({
        run_adb shell cmd package resolve-activity --brief "$PACKAGE" 2>/dev/null
    } | tail -n 1)"

    if [[ -z "$launch_component" || "$launch_component" == "No activity found" ]]; then
        echo "[!] Could not determine launch activity; falling back to monkey launcher."
        run_command \
            run_adb shell monkey \
            -p "$PACKAGE" \
            1 || exit 1
    else
        echo "[+] Launch component: ${launch_component}"
        run_command \
            run_adb shell am start -W "$launch_component" || exit 1
    fi

    sleep 3

    echo "[+] Launch requested for ${PACKAGE}"
}


# ============================================================
# Package information
# ============================================================

collect_package_info() {

    print_header "Collecting package information"

    local output_file="${RESULTS_DIR}/package_info.txt"

    if [[ ! -f "$PACKAGE_INFO" ]]; then
        echo "[!] Package info script not found: $PACKAGE_INFO"
        return 0
    fi

    python3 "$PACKAGE_INFO" "$PACKAGE" \
        >"$output_file" 2>&1

    local rc=$?

    cat "$output_file"

    if [[ $rc -ne 0 ]]; then
        echo "[!] Package information collection failed with exit code $rc."
    fi

    echo "[+] Saved: ${output_file}"
}


# ============================================================
# Permissions
# ============================================================

collect_permissions() {

    print_header "Collecting permissions"

    local output_file="${RESULTS_DIR}/permissions.txt"

    if [[ ! -f "$PERMISSIONS" ]]; then
        echo "[!] Permissions script not found: $PERMISSIONS"
        return 0
    fi

    python3 "$PERMISSIONS" "$PACKAGE" \
        >"$output_file" 2>&1

    local rc=$?

    cat "$output_file"

    if [[ $rc -ne 0 ]]; then
        echo "[!] Permission collection failed with exit code $rc."
    fi

    echo "[+] Saved: ${output_file}"
}


# ============================================================
# Frida collector
# ============================================================

start_frida() {

    print_header "Starting Frida collector"

    if [[ ! -f "$COLLECTOR" ]]; then
        echo "[!] Collector not found: $COLLECTOR"
        exit 1
    fi

    local frida="${FRIDA_ENV}/bin/frida"

    if [[ ! -x "$frida" ]]; then
        echo "[!] Frida executable not found: $frida"
        exit 1
    fi

    RAW_LOG="${LOGS_DIR}/frida_raw.log"

    local command=(
        "$frida"
        "-U"
        "-f"
        "$PACKAGE"
        "-l"
        "$COLLECTOR"
    )

    echo "[CMD] ${command[*]}"

    # Open the log file on a dedicated file descriptor.
    exec 3>"$RAW_LOG"
    FRIDA_LOG_FD=3

    "${command[@]}" >&3 2>&1 &

    FRIDA_PROCESS=$!

    echo "[+] Frida PID: ${FRIDA_PROCESS}"
    echo "[+] Raw log: ${RAW_LOG}"

    sleep 2

    if ! kill -0 "$FRIDA_PROCESS" 2>/dev/null; then

        wait "$FRIDA_PROCESS" 2>/dev/null
        local rc=$?

        echo "[!] Frida exited before collection began with code ${rc}."
        echo "[DEBUG] Inspect the raw log for the startup failure:"
        echo "${RAW_LOG}"

        exec 3>&-

        FRIDA_PROCESS=""

        exit 1
    fi

    echo "[DEBUG] Frida is running and has started collecting events."
}


# ============================================================
# Stop Frida
# ============================================================

stop_process() {

    if [[ -z "$FRIDA_PROCESS" ]]; then
        echo "[DEBUG] No Frida process was started; nothing to stop."
        return
    fi

    echo
    echo "[+] Stopping Frida..."

    if kill -0 "$FRIDA_PROCESS" 2>/dev/null; then

        kill -INT "$FRIDA_PROCESS" 2>/dev/null || true

        local waited=0

        while kill -0 "$FRIDA_PROCESS" 2>/dev/null && (( waited < 5 )); do
            sleep 1
            ((waited++))
        done

        if kill -0 "$FRIDA_PROCESS" 2>/dev/null; then

            echo "[!] Frida did not exit after SIGINT; force-killing it."

            kill -KILL "$FRIDA_PROCESS" 2>/dev/null || true

            wait "$FRIDA_PROCESS" 2>/dev/null || true

            echo "[DEBUG] Frida was force-killed."

        else

            wait "$FRIDA_PROCESS" 2>/dev/null || true

            echo "[DEBUG] Frida exited cleanly."

        fi

    else

        wait "$FRIDA_PROCESS" 2>/dev/null || true
        echo "[DEBUG] Frida had already exited."

    fi

    if [[ -n "$FRIDA_LOG_FD" ]]; then
        exec 3>&-
        FRIDA_LOG_FD=""
    fi

    FRIDA_PROCESS=""
    echo "[DEBUG] Frida log file closed."
}


# ============================================================
# UI Explorer
# ============================================================

run_ui_explorer() {

    if [[ ! -f "$EXPLORER" ]]; then
        echo "[!] UI explorer not found."
        return 0
    fi

    print_header "Starting UI explorer"

    local command=(
        python3
        "$EXPLORER"
        "$PACKAGE"
        "--depth"
        "3"
        "--max-states"
        "50"
        "--minutes"
        "2"
        "--out"
        "${RESULTS_DIR}/ui_graph.json"
        "--no-input"
        "--no-pick"
    )

    echo "[CMD] ${command[*]}"

    "${command[@]}"

    local rc=$?

    if [[ $rc -ne 0 ]]; then
        echo "[!] UI explorer returned an error."
    else
        echo "[+] UI exploration finished."
    fi
}


# ============================================================
# Parse Frida log
# ============================================================

parse_frida_log() {

    print_header "Parsing Frida events"

    if [[ ! -f "$PARSER" ]]; then
        echo "[!] Parser not found: $PARSER"
        return 0
    fi

    python3 \
        "$PARSER" \
        "$RAW_LOG" \
        "$EVENTS_JSON"

    local rc=$?

    if [[ $rc -ne 0 ]]; then
        echo "[!] Event parsing failed with exit code ${rc}."
    else
        echo "[+] Event parsing completed."
    fi
}


# ============================================================
# Cleanup handler
# ============================================================

cleanup() {

    local rc=$?

    echo
    echo "[DEBUG] Cleanup requested."

    if [[ -n "$FRIDA_PROCESS" ]]; then
        stop_process
    else
        echo "[DEBUG] No Frida process was started; cleanup is unnecessary."
    fi

    exit "$rc"
}


trap cleanup INT TERM


# ============================================================
# Main
# ============================================================

mkdir -p "$RESULTS_DIR"
mkdir -p "$LOGS_DIR"

RAW_LOG="${LOGS_DIR}/frida_raw.log"
EVENTS_JSON="${RESULTS_DIR}/raw_events.json"


echo
echo "======================================================================"
echo "DL-Droid reproduction pipeline"
echo "======================================================================"
echo "Project : ${PROJECT}"
echo "APK     : ${APK}"
echo


echo "[DEBUG] Starting environment validation."

check_adb
check_frida


# ------------------------------------------------------------
# Package
# ------------------------------------------------------------

if [[ -z "$PACKAGE" ]]; then

    echo "[DEBUG] No package name was provided; extracting it from the APK."

    get_package_from_apk

fi

echo
echo "[+] Target package: ${PACKAGE}"


# ------------------------------------------------------------
# Install
# ------------------------------------------------------------

echo "[DEBUG] Installing APK."

install_apk


# ------------------------------------------------------------
# Package information
# ------------------------------------------------------------

echo "[DEBUG] Collecting package information."

collect_package_info


# ------------------------------------------------------------
# Permissions
# ------------------------------------------------------------

echo "[DEBUG] Collecting requested permissions."

collect_permissions


# ------------------------------------------------------------
# Launch
# ------------------------------------------------------------

echo "[DEBUG] Launching application."

launch_app


# ------------------------------------------------------------
# Frida
# ------------------------------------------------------------

echo "[DEBUG] Starting Frida event collection."

start_frida


echo
echo "======================================================================"
echo "Collecting runtime events for ${FRIDA_TIME} seconds"
echo "======================================================================"


# ------------------------------------------------------------
# UI explorer / manual interaction
# ------------------------------------------------------------

if [[ "$UI" == true ]]; then

    echo "[DEBUG] Running UI explorer."

    run_ui_explorer

else

    echo "[DEBUG] UI exploration is disabled."
    echo "[+] Interact with the application manually if desired."

    sleep "$FRIDA_TIME"

fi


# ------------------------------------------------------------
# Stop Frida
# ------------------------------------------------------------

stop_process


# ------------------------------------------------------------
# Parse events
# ------------------------------------------------------------

echo "[DEBUG] Parsing collected Frida events."

parse_frida_log


# ------------------------------------------------------------
# Finished
# ------------------------------------------------------------

echo
echo "======================================================================"
echo "Analysis finished"
echo "======================================================================"

echo "Results directory: ${RESULTS_DIR}"
echo "Logs directory   : ${LOGS_DIR}"
echo
```
