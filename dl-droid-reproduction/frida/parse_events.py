
#!/usr/bin/env python3

import json
import sys
from pathlib import Path


PREFIX = "[DL_EVENT] "


def parse_file(input_file, output_file):

    events = []

    with open(input_file, "r", encoding="utf-8", errors="replace") as f:

        for line in f:

            line = line.strip()

            if not line.startswith(PREFIX):
                continue

            payload = line[len(PREFIX):]

            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                print(
                    f"[!] Could not parse event: {payload}",
                    file=sys.stderr
                )
                continue

            events.append(event)


    with open(output_file, "w", encoding="utf-8") as f:

        json.dump(
            events,
            f,
            indent=2
        )


    print("=" * 60)
    print("Frida event parser")
    print("=" * 60)
    print(f"Input : {input_file}")
    print(f"Output: {output_file}")
    print(f"Events: {len(events)}")


    api_events = [
        event
        for event in events
        if event.get("type") == "api"
    ]

    print(f"API events: {len(api_events)}")

    unique_apis = sorted({
        f"{event.get('class')}->{event.get('method')}"
        for event in api_events
    })

    print(f"Unique APIs: {len(unique_apis)}")

    for api in unique_apis:
        print(f"  {api}")


def main():

    if len(sys.argv) != 3:

        print(
            "Usage:\n"
            "  python parse_events.py <input.log> <output.json>"
        )

        sys.exit(1)


    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])


    if not input_file.exists():

        print(f"[!] Input file does not exist: {input_file}")
        sys.exit(1)


    parse_file(input_file, output_file)


if __name__ == "__main__":
    main()

