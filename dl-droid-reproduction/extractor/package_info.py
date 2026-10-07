
#!/usr/bin/env python3

import subprocess
import sys


def run(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main():
    if len(sys.argv) != 2:
        print("Usage: python package_info.py <package.name>")
        sys.exit(1)

    package = sys.argv[1]

    output = run([
        "adb",
        "shell",
        "dumpsys",
        "package",
        package,
    ])

    print("=" * 60)
    print(f"PACKAGE: {package}")
    print("=" * 60)

    for line in output.splitlines():
        stripped = line.strip()

        if stripped.startswith("versionName="):
            print(stripped)

        elif stripped.startswith("versionCode="):
            print(stripped)

        elif "requested permissions:" in stripped:
            print("\nRequested permissions:")

        elif stripped.startswith("android.permission."):
            print("  " + stripped.split(":")[0])


if __name__ == "__main__":
    main()

