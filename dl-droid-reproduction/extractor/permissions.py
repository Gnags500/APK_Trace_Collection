
#!/usr/bin/env python3

import subprocess
import sys


# Initial prototype schema.
#
# This is NOT yet the complete 300-permission DL-Droid vocabulary.
# We will reconstruct that vocabulary in a later step.

FEATURES = [
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.INTERNET",
    "android.permission.READ_PHONE_STATE",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.SEND_SMS",
    "android.permission.WRITE_SMS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.GET_ACCOUNTS",
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
]


def get_package_dump(package):
    result = subprocess.run(
        [
            "adb",
            "shell",
            "dumpsys",
            "package",
            package,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def extract_requested_permissions(package):
    output = get_package_dump(package)

    permissions = set()

    collecting = False

    for line in output.splitlines():
        line = line.strip()

        if line.startswith("requested permissions:"):
            collecting = True
            continue

        if collecting:
            if not line:
                continue

            if line.startswith("android.permission."):
                permission = line.split(":", 1)[0]
                permissions.add(permission)

            elif not line.startswith("android.permission."):
                # The requested-permissions section has ended.
                if permissions:
                    break

    return permissions


def build_vector(package):
    permissions = extract_requested_permissions(package)

    vector = {}

    for feature in FEATURES:
        vector[f"permission:{feature}"] = int(feature in permissions)

    return vector


def main():
    if len(sys.argv) != 2:
        print("Usage: python permissions.py <package.name>")
        sys.exit(1)

    package = sys.argv[1]

    permissions = extract_requested_permissions(package)

    print("=" * 60)
    print("REQUESTED PERMISSIONS")
    print("=" * 60)

    for permission in sorted(permissions):
        print(permission)

    print("\n" + "=" * 60)
    print("FEATURE VECTOR")
    print("=" * 60)

    vector = build_vector(package)

    for name, value in vector.items():
        print(f"{name}={value}")


if __name__ == "__main__":
    main()

