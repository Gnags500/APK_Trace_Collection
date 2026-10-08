
#!/usr/bin/env python3

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
SDK_DIR = Path.home() / "Android" / "Sdk"
EMULATOR_DIR = SDK_DIR / "emulator"
EMULATOR_AVD = "Pixel_4"

APK_DIR = PROJECT / "apk"
RESULTS_DIR = PROJECT / "results"
LOGS_DIR = PROJECT / "logs"

FRIDA_ENV = Path.home() / "frida-env"

COLLECTOR = PROJECT / "frida" / "collect_event.js"
PARSER = PROJECT / "frida" / "parse_events.py"

PACKAGE_INFO = PROJECT / "extractor" / "package_info.py"
PERMISSIONS = PROJECT / "extractor" / "permissions.py"


def run_command(command, check=True, capture=False):

    print()
    print("[CMD]", " ".join(map(str, command)))

    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture,
            text=True,
        )
    except FileNotFoundError as exc:
        print(f"[!] Command not found: {command[0]}")
        raise RuntimeError(f"Required command is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        print(f"[!] Command failed with exit code {exc.returncode}: {' '.join(map(str, command))}")
        if exc.stdout:
            print("[STDOUT]")
            print(exc.stdout)
        if exc.stderr:
            print("[STDERR]")
            print(exc.stderr, file=sys.stderr)
        raise

    if capture and result.stdout:
        print(result.stdout)

    if capture and result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"[!] Command returned exit code {result.returncode}: {' '.join(map(str, command))}")

    return result


def get_connected_devices():

    result = run_command(
        ["adb", "devices"],
        capture=True,
    )

    devices = []

    for line in result.stdout.splitlines():

        if line.startswith("List of devices"):
            continue

        if not line.strip():
            continue

        parts = line.split()

        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])

    return devices


def start_emulator():
    print()
    print("=" * 70)
    print("Starting Android emulator")
    print("=" * 70)

    emulator = SDK_DIR / "emulator" / "emulator"

    subprocess.Popen(
        [
            str(emulator),
            "-avd",
            EMULATOR_AVD,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("[DEBUG] Waiting for ADB device...")

    deadline = time.monotonic() + 120

    # Step 1: wait until ADB sees the emulator as "device"
    while time.monotonic() < deadline:
        devices = get_connected_devices()

        if devices:
            print(f"[+] ADB device connected: {devices}")
            break

        time.sleep(3)
    else:
        print("[!] Emulator did not connect within 120 seconds.")
        sys.exit(1)

    # Step 2: wait until Android itself reports boot completed
    print("[DEBUG] Waiting for Android boot to complete...")

    boot_deadline = time.monotonic() + 180

    while time.monotonic() < boot_deadline:
        result = subprocess.run(
            ["adb", "shell", "getprop", "sys.boot_completed"],
            capture_output=True,
            text=True,
        )

        boot_completed = result.stdout.strip()

        if boot_completed == "1":
            print("[+] Android boot completed.")
            break

        print(
            f"[DEBUG] Android not fully booted yet "
            f"(sys.boot_completed={boot_completed!r})"
        )

        time.sleep(3)
    else:
        print("[!] Android did not finish booting within 180 seconds.")
        sys.exit(1)

    # Step 3: small stabilization delay
    print("[DEBUG] Giving Android services a few seconds to stabilize...")
    time.sleep(5)

    print("[+] Emulator is ready.")

def check_adb(start_emulator_requested=False):

    print("=" * 70)
    print("Checking ADB")
    print("=" * 70)

    devices = get_connected_devices()

    if not devices:

        if not start_emulator_requested:
            print("[!] No Android device/emulator detected.")
            print("[!] Start your emulator and run this script again.")
            sys.exit(1)

        start_emulator()
        devices = get_connected_devices()

        if not devices:
            print("[!] ADB did not detect the emulator after startup.")
            sys.exit(1)

    print(f"[+] Connected device(s): {', '.join(devices)}")
    wait_for_android_ready()


def check_frida():
    frida = FRIDA_ENV / "bin" / "frida-ps"

    result = subprocess.run(
        [str(frida), "-U"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Frida client cannot connect to frida-server")

    print("[+] Frida connection OK")

def setup_adb_root():
    print("[*] Requesting ADB root...")
    result = subprocess.run(
        ["adb", "root"],
        capture_output=True,
        text=True
    )

    print(result.stdout.strip())

    # adb restarts after root, so wait for it
    subprocess.run(["adb", "wait-for-device"], check=True)

    result = subprocess.run(
        ["adb", "shell", "id"],
        capture_output=True,
        text=True,
        check=True
    )

    if "uid=0(root)" not in result.stdout:
        raise RuntimeError(
            f"ADB is not running as root:\n{result.stdout}"
        )

    print("[+] ADB root access confirmed")


def start_frida(package, raw_log, app_pid):
    frida = FRIDA_ENV / "bin" / "frida"

    log_file = open(raw_log, "w", encoding="utf-8")

    command = [
        str(frida),
        "-U",
        "-p",
        str(app_pid),
        "-l",
        str(COLLECTOR),
    ]

    print("[CMD]", " ".join(command))

    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    time.sleep(3)

    if process.poll() is not None:
        log_file.close()
        raise RuntimeError(
            f"Frida collector exited immediately "
            f"with code {process.returncode}"
        )

    print(f"[+] Frida collector attached to PID {app_pid}")

    return process, log_file


def start_frida_server():
    server = "/data/local/tmp/frida-server"

    print()
    print("=" * 70)
    print("Starting Frida server")
    print("=" * 70)

    # Check that frida-server exists and is executable
    print("[*] Checking frida-server binary...")

    result = subprocess.run(
        ["adb", "shell", "test", "-x", server],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"frida-server not found or not executable: {server}"
        )

    print("[+] frida-server binary found.")

    # Stop an old instance if one exists
    print("[*] Stopping any existing frida-server...")

    subprocess.run(
        ["adb", "shell", "pkill", "frida-server"],
        capture_output=True,
        text=True,
    )

    time.sleep(1)

    # Start server in Android background
    print("[*] Starting frida-server...")

    subprocess.run(
        [
            "adb",
            "shell",
            "sh",
            "-c",
            f"'{server}' >/dev/null 2>&1 &",
        ],
        check=True,
    )

    time.sleep(2)

    # Verify process
    result = subprocess.run(
        ["adb", "shell", "pidof", "frida-server"],
        capture_output=True,
        text=True,
    )

    pid = result.stdout.strip()

    if not pid:
        raise RuntimeError("frida-server failed to start.")

    print(f"[+] frida-server running. PID: {pid}")

    # Verify actual Frida connection
    print("[*] Testing Frida client connection...")

    frida_ps = FRIDA_ENV / "bin" / "frida-ps"

    result = subprocess.run(
        [str(frida_ps), "-U"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "frida-server is running, but Frida client "
            "cannot connect:\n"
            + result.stderr
        )

    print("[+] Frida connection successful.")

def setup_selinux():
    print("[*] Checking SELinux...")

    result = subprocess.run(
        ["adb", "shell", "getenforce"],
        capture_output=True,
        text=True,
        check=True
    )

    mode = result.stdout.strip()
    print(f"[*] SELinux: {mode}")

    if mode == "Enforcing":
        print("[*] Setting SELinux to permissive...")

        subprocess.run(
            ["adb", "shell", "setenforce", "0"],
            check=True
        )

        result = subprocess.run(
            ["adb", "shell", "getenforce"],
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout.strip() != "Permissive":
            raise RuntimeError("Could not set SELinux to permissive")

        print("[+] SELinux is now permissive")

        
          
def get_package_from_apk(apk):

    print()
    print("=" * 70)
    print("Reading APK package name")
    print("=" * 70)

    # aapt is not guaranteed to be on PATH.
    # Try common Android SDK locations.

    sdk = Path.home() / "Android" / "Sdk"

    candidates = [
        sdk / "build-tools" / "35.0.0" / "aapt",
        sdk / "build-tools" / "34.0.0" / "aapt",
        sdk / "build-tools" / "33.0.0" / "aapt",
    ]

    aapt = None

    for candidate in candidates:

        if candidate.exists():
            aapt = candidate
            break

    if aapt is None:

        from shutil import which

        path = which("aapt")

        if path:
            aapt = Path(path)

    if aapt is None:

        print("[!] Could not find aapt.")
        print("[!] For now, provide --package manually.")
        sys.exit(1)

    result = subprocess.run(
        [
            str(aapt),
            "dump",
            "badging",
            str(apk),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:

        print("[!] aapt could not read the APK.")
        print(result.stderr)
        sys.exit(1)

    for line in result.stdout.splitlines():

        if line.startswith("package:"):

            for item in line.split():

                if item.startswith("name="):

                    package = item.split("=", 1)[1].strip("'\"")

                    print(f"[+] Package: {package}")

                    return package

    print("[!] Could not determine package name.")
    sys.exit(1)


def install_apk(apk, retries=3, retry_delay=5):
    print()
    print("=" * 70)
    print("Installing APK")
    print("=" * 70)

    for attempt in range(1, retries + 1):
        print(f"[DEBUG] APK install attempt {attempt}/{retries}")

        result = subprocess.run(
            ["adb", "install", "-r", str(apk)],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode == 0:
            print("[+] APK installed.")
            return

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if attempt < retries:
            print(
                f"[DEBUG] APK installation failed. "
                f"Retrying in {retry_delay} seconds..."
            )
            time.sleep(retry_delay)

    print("[!] APK installation failed after all retries.")
    sys.exit(1)

def launch_app(package):

    print()
    print("=" * 70)
    print("Launching application")
    print("=" * 70)

    run_command([
        "adb",
        "shell",
        "monkey",
        "-p",
        package,
        "1",
    ])

    print("[DEBUG] Waiting for application process...")

    deadline = time.monotonic() + 30

    while time.monotonic() < deadline:

        result = subprocess.run(
            ["adb", "shell", "pidof", package],
            capture_output=True,
            text=True,
        )

        pid = result.stdout.strip()

        if pid:
            print(f"[+] Application is running. PID: {pid}")
            return pid

        print("[DEBUG] Application process not ready yet...")
        time.sleep(2)

    print("[!] Application did not start within 30 seconds.")
    sys.exit(1)


def wait_for_android_ready(timeout=180):
    print("[DEBUG] Waiting for Android to be fully ready...")

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        result = subprocess.run(
            ["adb", "shell", "getprop", "sys.boot_completed"],
            capture_output=True,
            text=True,
        )

        if result.stdout.strip() == "1":
            print("[+] Android is fully booted.")
            time.sleep(5)
            return

        time.sleep(3)

    print("[!] Android did not become ready.")
    sys.exit(1)


def start_frida_server():
    print("[*] Setting SELinux to permissive...")
    subprocess.run(
        ["adb", "shell", "setenforce", "0"],
        check=True
    )

    print("[*] Checking for frida-server...")
    check = subprocess.run(
        ["adb", "shell", "pidof", "frida-server"],
        capture_output=True,
        text=True
    )

    if check.stdout.strip():
        print(f"[+] frida-server already running: PID {check.stdout.strip()}")
        return

    print("[*] Starting frida-server...")

    subprocess.Popen(
        [
            "adb", "shell",
            "/data/local/tmp/frida-server"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    check = subprocess.run(
        ["adb", "shell", "pidof", "frida-server"],
        capture_output=True,
        text=True
    )

    if not check.stdout.strip():
        raise RuntimeError("frida-server failed to start")

    print(f"[+] frida-server started: PID {check.stdout.strip()}")

def stop_process(process, log_file):

    print()
    print("[+] Stopping Frida...")

    if process is None:
        print("[DEBUG] No Frida process was started; nothing to stop.")
        return

    if process.poll() is None:

        try:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=5)
            print(f"[DEBUG] Frida exited cleanly with code {process.returncode}.")

        except subprocess.TimeoutExpired:

            print("[!] Frida did not exit after SIGINT; force-killing it.")
            process.kill()
            process.wait()
            print(f"[DEBUG] Frida was force-killed with code {process.returncode}.")
    else:
        print(f"[DEBUG] Frida had already exited with code {process.returncode}.")

    log_file.close()
    print("[DEBUG] Frida log file closed.")


def run_ui_explorer(package):

    explorer = PROJECT / "crawler" / "ui_explorer.py"

    if not explorer.exists():

        print("[!] UI explorer not found.")
        return

    print()
    print("=" * 70)
    print("Starting UI explorer")
    print("=" * 70)

    # We intentionally use conservative options.
    #
    # No text input and no media picking during the initial
    # measurement stage.

    command = [
        sys.executable,
        str(explorer),
        package,
        "--depth",
        "3",
        "--max-states",
        "50",
        "--minutes",
        "2",
        "--out",
        str(RESULTS_DIR / "ui_graph.json"),
        "--no-input",
        "--no-pick",
    ]

    print("[CMD]", " ".join(command))

    result = subprocess.run(command)

    if result.returncode != 0:

        print("[!] UI explorer returned an error.")

    else:

        print("[+] UI exploration finished.")


def parse_frida_log(raw_log, events_json):

    print()
    print("=" * 70)
    print("Parsing Frida events")
    print("=" * 70)

    if not PARSER.exists():

        print(f"[!] Parser not found: {PARSER}")
        return

    result = subprocess.run(
        [
            sys.executable,
            str(PARSER),
            str(raw_log),
            str(events_json),
        ],
        text=True,
    )

    if result.returncode != 0:

        print(f"[!] Event parsing failed with exit code {result.returncode}.")

    else:

        print("[+] Event parsing completed.")


def collect_package_info(package):

    print()
    print("=" * 70)
    print("Collecting package information")
    print("=" * 70)

    output_file = RESULTS_DIR / "package_info.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(PACKAGE_INFO),
            package,
        ],
        capture_output=True,
        text=True,
    )

    output_file.write_text(
        result.stdout + result.stderr,
        encoding="utf-8"
    )

    print(result.stdout)

    print(f"[+] Saved: {output_file}")


def collect_permissions(package):

    print()
    print("=" * 70)
    print("Collecting permissions")
    print("=" * 70)

    output_file = RESULTS_DIR / "permissions.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(PERMISSIONS),
            package,
        ],
        capture_output=True,
        text=True,
    )

    output_file.write_text(
        result.stdout + result.stderr,
        encoding="utf-8"
    )

    print(result.stdout)

    print(f"[+] Saved: {output_file}")


def main():

    parser = argparse.ArgumentParser(
        description="DL-Droid reproduction analysis controller"
    )

    parser.add_argument(
        "--apk",
        required=True,
        help="Path to APK"
    )

    parser.add_argument(
        "--package",
        default=None,
        help="Android package name. If omitted, try to extract it from APK."
    )

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Run UI explorer"
    )

    parser.add_argument(
        "--frida-time",
        type=int,
        default=60,
        help="Frida collection time in seconds"
    )

    parser.add_argument(
        "--start-emulator",
        action="store_true",
        help="Start the existing Pixel_4 AVD when no device is connected"
    )

    args = parser.parse_args()

    frida_process = None
    log_file = None

    try:
        apk = Path(args.apk).expanduser().resolve()

        if not apk.exists():
            print(f"[!] APK does not exist: {apk}")
            sys.exit(1)

        RESULTS_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(exist_ok=True)

        print()
        print("=" * 70)
        print("DL-Droid reproduction pipeline")
        print("=" * 70)
        print(f"Project : {PROJECT}")
        print(f"APK     : {apk}")
        print()

        print("[DEBUG] Starting environment validation.")
        check_adb(start_emulator_requested=args.start_emulator)

        wait_for_android_ready()

        #check_frida()
        setup_adb_root()
        setup_selinux()
        start_frida_server()


        package = args.package

        if package is None:
            package = get_package_from_apk(apk)

        print()
        print(f"[+] Target package: {package}")

        print("[DEBUG] Checking Android readiness before APK installation.")
        wait_for_android_ready()

        print("[DEBUG] Installing APK.")
        install_apk(apk)
        print("[DEBUG] Collecting package information.")
        collect_package_info(package)

        print("[DEBUG] Collecting requested permissions.")
        collect_permissions(package)

        print("[DEBUG] Launching application.")
        app_pid = launch_app(package)

        raw_log = LOGS_DIR / "frida_raw.log"
        events_json = RESULTS_DIR / "raw_events.json"

        print("[DEBUG] Starting Frida event collection.")
        frida_process, log_file = start_frida(package, raw_log, app_pid)

        print()
        print("=" * 70)
        print(f"Collecting runtime events for {args.frida_time} seconds")
        print("=" * 70)

        if args.ui:
            print("[DEBUG] Running UI explorer.")
            run_ui_explorer(package)
        else:
            print("[DEBUG] UI exploration is disabled.")
            print("[+] Interact with the application manually if desired.")
            time.sleep(args.frida_time)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
    except Exception as exc:
        print(f"\n[!] Fatal error: {exc}")
        print("[DEBUG] Full traceback:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        if frida_process is not None:
            stop_process(frida_process, log_file)
        else:
            print("[DEBUG] No Frida process was started; cleanup is unnecessary.")

    print("[DEBUG] Parsing collected Frida events.")
    parse_frida_log(raw_log, events_json)

    print()
    print("=" * 70)
    print("Analysis finished")
    print("=" * 70)

    print(f"Results directory: {RESULTS_DIR}")
    print(f"Logs directory   : {LOGS_DIR}")
    print()


if __name__ == "__main__":
    main()

