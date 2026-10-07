import uiautomator2 as u2
import xml.etree.ElementTree as ET
import hashlib
import time
from collections import defaultdict


PACKAGE = "com.duygiangdg.magiceraser"
MAX_DEPTH = 5

d = u2.connect()

visited = set()
graph = defaultdict(list)


def get_state():
    """
    Current Android UI state-এর একটি unique signature তৈরি করে।
    """

    current = d.app_current()

    if current.get("package") != PACKAGE:
        return None, current, None

    xml = d.dump_hierarchy()

    # UI XML-এর কিছু dynamic attribute বাদ দিলে
    # একই ধরনের screen-এর signature বেশি stable হয়।
    root = ET.fromstring(xml)

    elements = []

    for node in root.iter():
        resource_id = node.attrib.get("resource-id", "")
        text = node.attrib.get("text", "")
        cls = node.attrib.get("class", "")
        clickable = node.attrib.get("clickable", "")
        bounds = node.attrib.get("bounds", "")

        if resource_id.startswith(PACKAGE):
            elements.append(
                (resource_id, text, cls, clickable, bounds)
            )

    state_string = (
        current.get("activity", "")
        + repr(elements)
    )

    state_hash = hashlib.sha256(
        state_string.encode("utf-8")
    ).hexdigest()[:12]

    return state_hash, current, elements


def find_actions():
    """
    Current screen-এর app-owned clickable elements বের করে।
    """

    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)

    actions = []

    for node in root.iter():

        resource_id = node.attrib.get("resource-id", "")
        clickable = node.attrib.get("clickable", "")

        if (
            clickable == "true"
            and resource_id.startswith(PACKAGE)
        ):
            actions.append({
                "resource_id": resource_id,
                "text": node.attrib.get("text", ""),
                "class": node.attrib.get("class", ""),
                "bounds": node.attrib.get("bounds", "")
            })

    # duplicate resource ID বাদ দিই
    unique = {}
    for action in actions:
        unique[action["resource_id"]] = action

    return list(unique.values())


def print_state(depth, state_hash, current, actions):

    indent = "  " * depth

    print()
    print(indent + "=" * 60)
    print(indent + f"DEPTH: {depth}")
    print(indent + f"STATE: {state_hash}")
    print(indent + f"ACTIVITY: {current.get('activity')}")
    print(indent + f"ACTIONS: {len(actions)}")

    for i, action in enumerate(actions):
        print(
            indent
            + f"  [{i}] "
            + action["resource_id"]
            + f" | text={action['text']!r}"
            + f" | class={action['class']}"
        )


def explore(depth=0):

    if depth > MAX_DEPTH:
        print("Maximum depth reached.")
        return

    state_hash, current, elements = get_state()

    if state_hash is None:
        print("Outside target application. Stopping branch.")
        return

    if state_hash in visited:
        print(
            "  " * depth
            + f"Already visited state {state_hash}"
        )
        return

    visited.add(state_hash)

    actions = find_actions()

    print_state(
        depth,
        state_hash,
        current,
        actions
    )

    for action in actions:

        resource_id = action["resource_id"]

        print()
        print(
            "  " * depth
            + f">>> Clicking {resource_id}"
        )

        before_state = state_hash

        try:
            d(resourceId=resource_id).click()

        except Exception as e:
            print(
                "  " * depth
                + f"CLICK FAILED: {e}"
            )
            continue

        time.sleep(1)

        after_state, after_current, _ = get_state()

        print(
            "  " * depth
            + f">>> New state: {after_state}"
        )

        graph[before_state].append({
            "action": resource_id,
            "destination": after_state
        })

        if after_state is not None:
            explore(depth + 1)

        print(
            "  " * depth
            + "<<< Backtracking"
        )

        d.press("back")

        time.sleep(1)


def main():

    print("Starting UI explorer...")
    print(f"Target package: {PACKAGE}")
    print(f"Maximum depth: {MAX_DEPTH}")

    explore()

    print()
    print("=" * 60)
    print("EXPLORATION FINISHED")
    print("=" * 60)

    print(f"Visited states: {len(visited)}")

    print()
    print("GRAPH:")

    for source, transitions in graph.items():

        for transition in transitions:

            print(
                f"{source}"
                f" --[{transition['action']}]--> "
                f"{transition['destination']}"
            )


if __name__ == "__main__":
    main()
import uiautomator2 as u2
import xml.etree.ElementTree as ET
import hashlib
import time


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MAX_DEPTH = 5
WAIT_AFTER_ACTION = 1.0
WAIT_AFTER_BACK = 1.0


# --------------------------------------------------
# Connect to emulator
# --------------------------------------------------

d = u2.connect()


# --------------------------------------------------
# Detect which app is currently in foreground
# --------------------------------------------------

START_APP = d.app_current().get("package")

if not START_APP:
    raise RuntimeError("Could not detect foreground application.")

print()
print("=" * 60)
print("AUTOMATIC UI EXPLORER")
print("=" * 60)
print(f"Target application: {START_APP}")
print()


# --------------------------------------------------
# Visited states
# --------------------------------------------------

visited = set()
transitions = []


# --------------------------------------------------
# Get current application state
# --------------------------------------------------

def get_state():

    current = d.app_current()

    package = current.get("package", "")
    activity = current.get("activity", "")

    # App-এর বাইরে চলে গেলে state invalid
    if package != START_APP:
        return None

    xml = d.dump_hierarchy()

    root = ET.fromstring(xml)

    elements = []

    for node in root.iter():

        resource_id = node.attrib.get("resource-id", "")
        text = node.attrib.get("text", "")
        cls = node.attrib.get("class", "")
        clickable = node.attrib.get("clickable", "")

        # শুধু target application's elements রাখছি
        if resource_id.startswith(START_APP):

            elements.append(
                (
                    resource_id,
                    text,
                    cls,
                    clickable
                )
            )

    state_data = (
        activity,
        tuple(elements)
    )

    state_hash = hashlib.sha256(
        repr(state_data).encode("utf-8")
    ).hexdigest()[:12]

    return {
        "hash": state_hash,
        "package": package,
        "activity": activity,
    }


# --------------------------------------------------
# Find clickable elements
# --------------------------------------------------

def find_actions():

    xml = d.dump_hierarchy()

    root = ET.fromstring(xml)

    actions = []

    for node in root.iter():

        resource_id = node.attrib.get("resource-id", "")
        clickable = node.attrib.get("clickable", "")

        if (
            clickable == "true"
            and resource_id.startswith(START_APP)
        ):

            actions.append({
                "resource_id": resource_id,
                "text": node.attrib.get("text", ""),
                "class": node.attrib.get("class", ""),
                "bounds": node.attrib.get("bounds", "")
            })

    # Same resource-id multiple times থাকলে duplicate বাদ
    unique = {}

    for action in actions:
        unique[action["resource_id"]] = action

    return list(unique.values())


# --------------------------------------------------
# Make sure app is in foreground
# --------------------------------------------------

def app_is_foreground():

    current = d.app_current()

    return current.get("package") == START_APP


# --------------------------------------------------
# Return to application
# --------------------------------------------------

def recover_to_app():

    print("  [RECOVER] Application left foreground.")

    # App launch করার চেষ্টা
    try:

        d.app_start(START_APP)

        time.sleep(WAIT_AFTER_ACTION)

        if app_is_foreground():

            print("  [RECOVER] Application restored.")
            return True

    except Exception as e:

        print(f"  [RECOVER] Failed: {e}")

    return False


# --------------------------------------------------
# Safe backtracking
# --------------------------------------------------

def safe_back(expected_state=None):

    """
    Back press করার আগে এবং পরে application state check করে।

    যদি Back application থেকে বের করে দেয়,
    তাহলে app আবার launch করার চেষ্টা করে।
    """

    print("  [BACK] Pressing Android Back...")

    before = get_state()

    if before is None:
        print("  [BACK] Already outside application.")
        return False

    d.press("back")

    time.sleep(WAIT_AFTER_BACK)

    after = get_state()

    # App থেকে বের হয়ে গেছে
    if after is None:

        print("  [BACK] WARNING: App left foreground!")

        recovered = recover_to_app()

        if not recovered:
            return False

        return False

    print(
        f"  [BACK] Returned to "
        f"{after['activity']} "
        f"state={after['hash']}"
    )

    return True


# --------------------------------------------------
# Print state information
# --------------------------------------------------

def print_state(depth, state, actions):

    indent = "  " * depth

    print()
    print(indent + "-" * 55)

    print(
        indent
        + f"DEPTH={depth} "
        + f"ACTIVITY={state['activity']} "
        + f"STATE={state['hash']}"
    )

    print(
        indent
        + f"Clickable actions: {len(actions)}"
    )

    for i, action in enumerate(actions):

        print(
            indent
            + f"[{i}] "
            + action["resource_id"]
            + f" text={action['text']!r}"
            + f" class={action['class']}"
        )


# --------------------------------------------------
# Recursive DFS exploration
# --------------------------------------------------

def explore(depth=0):

    if depth > MAX_DEPTH:

        print(
            "  " * depth
            + "Maximum depth reached."
        )

        return

    state = get_state()

    # App-এর বাইরে
    if state is None:

        print(
            "  " * depth
            + "Outside target application."
        )

        return

    # Already visited
    if state["hash"] in visited:

        print(
            "  " * depth
            + f"Already visited {state['hash']}"
        )

        return

    visited.add(state["hash"])

    actions = find_actions()

    print_state(
        depth,
        state,
        actions
    )

    parent_state = state["hash"]

    # ------------------------------------------------
    # Explore each clickable element
    # ------------------------------------------------

    for index, action in enumerate(actions):

        resource_id = action["resource_id"]

        print()
        print(
            "  " * depth
            + f">>> ACTION {index}: {resource_id}"
        )

        # Current state confirm
        current = get_state()

        if current is None:

            print(
                "  " * depth
                + "Application not in foreground."
            )

            if not recover_to_app():
                return

            continue

        # ------------------------------------------------
        # Click
        # ------------------------------------------------

        try:

            d(resourceId=resource_id).click()

        except Exception as e:

            print(
                "  " * depth
                + f"CLICK FAILED: {e}"
            )

            continue

        time.sleep(WAIT_AFTER_ACTION)

        # ------------------------------------------------
        # Detect destination
        # ------------------------------------------------

        destination = get_state()

        if destination is None:

            print(
                "  " * depth
                + "Action caused app to leave foreground."
            )

            recover_to_app()

            continue

        print(
            "  " * depth
            + f">>> DESTINATION: "
            + f"{destination['activity']} "
            + f"[{destination['hash']}]"
        )

        transitions.append({
            "source": parent_state,
            "action": resource_id,
            "destination": destination["hash"]
        })

        # ------------------------------------------------
        # Recursive exploration
        # ------------------------------------------------

        if destination["hash"] not in visited:

            explore(depth + 1)

        # ------------------------------------------------
        # Return to parent
        # ------------------------------------------------

        print(
            "  " * depth
            + "<<< Attempting backtrack"
        )

        success = safe_back()

        if not success:

            print(
                "  " * depth
                + "Backtracking did not return normally."
            )

            # app পুনরায় foreground-এ আনার চেষ্টা
            if recover_to_app():

                print(
                    "  " * depth
                    + "Application recovered."
                )

            else:

                print(
                    "  " * depth
                    + "Could not recover application."
                )

                return


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Starting recursive exploration...")
    print()

    # প্রথম state
    state = get_state()

    if state is None:

        print(
            "ERROR: Target application is not currently "
            "in the foreground."
        )

        return

    explore()

    print()
    print("=" * 60)
    print("EXPLORATION FINISHED")
    print("=" * 60)

    print(f"Visited states: {len(visited)}")
    print(f"Transitions: {len(transitions)}")

    print()
    print("DISCOVERED GRAPH")
    print("-" * 60)

    for t in transitions:

        print(
            f"{t['source']}"
            f" --[{t['action']}]--> "
            f"{t['destination']}"
        )


if __name__ == "__main__":
    main()
