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
        stripped = line.strip()

        if stripped.startswith("requested permissions:"):
            collecting = True
            continue

        if collecting:
            # Empty lines do not end the section — skip them.
            if not stripped:
                continue

            # A new section header has no leading whitespace.
            # That is the reliable signal that the permissions
            # block has ended.
            if not line.startswith(" ") and not line.startswith("\t"):
                break

            # Collect every permission in the section, not just
            # android.permission.* — apps also declare third-party
            # permissions (com.google.*, com.android.vending.*, etc.)
            # and those are valid features for DL-Droid.
            permission = stripped.split(":")[0].strip()
            if permission:
                permissions.add(permission)

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