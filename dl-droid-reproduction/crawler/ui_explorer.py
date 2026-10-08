# import uiautomator2 as u2
# import xml.etree.ElementTree as ET
# import hashlib
# import time
# from collections import defaultdict


# PACKAGE = "com.duygiangdg.magiceraser"
# MAX_DEPTH = 5

# d = u2.connect()

# visited = set()
# graph = defaultdict(list)


# def get_state():
#     """
#     Current Android UI state-এর একটি unique signature তৈরি করে।
#     """

#     current = d.app_current()

#     if current.get("package") != PACKAGE:
#         return None, current, None

#     xml = d.dump_hierarchy()

#     # UI XML-এর কিছু dynamic attribute বাদ দিলে
#     # একই ধরনের screen-এর signature বেশি stable হয়।
#     root = ET.fromstring(xml)

#     elements = []

#     for node in root.iter():
#         resource_id = node.attrib.get("resource-id", "")
#         text = node.attrib.get("text", "")
#         cls = node.attrib.get("class", "")
#         clickable = node.attrib.get("clickable", "")
#         bounds = node.attrib.get("bounds", "")

#         if resource_id.startswith(PACKAGE):
#             elements.append(
#                 (resource_id, text, cls, clickable, bounds)
#             )

#     state_string = (
#         current.get("activity", "")
#         + repr(elements)
#     )

#     state_hash = hashlib.sha256(
#         state_string.encode("utf-8")
#     ).hexdigest()[:12]

#     return state_hash, current, elements


# def find_actions():
#     """
#     Current screen-এর app-owned clickable elements বের করে।
#     """

#     xml = d.dump_hierarchy()
#     root = ET.fromstring(xml)

#     actions = []

#     for node in root.iter():

#         resource_id = node.attrib.get("resource-id", "")
#         clickable = node.attrib.get("clickable", "")

#         if (
#             clickable == "true"
#             and resource_id.startswith(PACKAGE)
#         ):
#             actions.append({
#                 "resource_id": resource_id,
#                 "text": node.attrib.get("text", ""),
#                 "class": node.attrib.get("class", ""),
#                 "bounds": node.attrib.get("bounds", "")
#             })

#     # duplicate resource ID বাদ দিই
#     unique = {}
#     for action in actions:
#         unique[action["resource_id"]] = action

#     return list(unique.values())


# def print_state(depth, state_hash, current, actions):

#     indent = "  " * depth

#     print()
#     print(indent + "=" * 60)
#     print(indent + f"DEPTH: {depth}")
#     print(indent + f"STATE: {state_hash}")
#     print(indent + f"ACTIVITY: {current.get('activity')}")
#     print(indent + f"ACTIONS: {len(actions)}")

#     for i, action in enumerate(actions):
#         print(
#             indent
#             + f"  [{i}] "
#             + action["resource_id"]
#             + f" | text={action['text']!r}"
#             + f" | class={action['class']}"
#         )


# def explore(depth=0):

#     if depth > MAX_DEPTH:
#         print("Maximum depth reached.")
#         return

#     state_hash, current, elements = get_state()

#     if state_hash is None:
#         print("Outside target application. Stopping branch.")
#         return

#     if state_hash in visited:
#         print(
#             "  " * depth
#             + f"Already visited state {state_hash}"
#         )
#         return

#     visited.add(state_hash)

#     actions = find_actions()

#     print_state(
#         depth,
#         state_hash,
#         current,
#         actions
#     )

#     for action in actions:

#         resource_id = action["resource_id"]

#         print()
#         print(
#             "  " * depth
#             + f">>> Clicking {resource_id}"
#         )

#         before_state = state_hash

#         try:
#             d(resourceId=resource_id).click()

#         except Exception as e:
#             print(
#                 "  " * depth
#                 + f"CLICK FAILED: {e}"
#             )
#             continue

#         time.sleep(1)

#         after_state, after_current, _ = get_state()

#         print(
#             "  " * depth
#             + f">>> New state: {after_state}"
#         )

#         graph[before_state].append({
#             "action": resource_id,
#             "destination": after_state
#         })

#         if after_state is not None:
#             explore(depth + 1)

#         print(
#             "  " * depth
#             + "<<< Backtracking"
#         )

#         d.press("back")

#         time.sleep(1)


# def main():

#     print("Starting UI explorer...")
#     print(f"Target package: {PACKAGE}")
#     print(f"Maximum depth: {MAX_DEPTH}")

#     explore()

#     print()
#     print("=" * 60)
#     print("EXPLORATION FINISHED")
#     print("=" * 60)

#     print(f"Visited states: {len(visited)}")

#     print()
#     print("GRAPH:")

#     for source, transitions in graph.items():

#         for transition in transitions:

#             print(
#                 f"{source}"
#                 f" --[{transition['action']}]--> "
#                 f"{transition['destination']}"
#             )


# if __name__ == "__main__":
#     main()
# import uiautomator2 as u2
# import xml.etree.ElementTree as ET
# import hashlib
# import time


# # --------------------------------------------------
# # Configuration
# # --------------------------------------------------

# MAX_DEPTH = 5
# WAIT_AFTER_ACTION = 1.0
# WAIT_AFTER_BACK = 1.0


# # --------------------------------------------------
# # Connect to emulator
# # --------------------------------------------------

# d = u2.connect()


# # --------------------------------------------------
# # Detect which app is currently in foreground
# # --------------------------------------------------

# START_APP = d.app_current().get("package")

# if not START_APP:
#     raise RuntimeError("Could not detect foreground application.")

# print()
# print("=" * 60)
# print("AUTOMATIC UI EXPLORER")
# print("=" * 60)
# print(f"Target application: {START_APP}")
# print()


# # --------------------------------------------------
# # Visited states
# # --------------------------------------------------

# visited = set()
# transitions = []


# # --------------------------------------------------
# # Get current application state
# # --------------------------------------------------

# def get_state():

#     current = d.app_current()

#     package = current.get("package", "")
#     activity = current.get("activity", "")

#     # App-এর বাইরে চলে গেলে state invalid
#     if package != START_APP:
#         return None

#     xml = d.dump_hierarchy()

#     root = ET.fromstring(xml)

#     elements = []

#     for node in root.iter():

#         resource_id = node.attrib.get("resource-id", "")
#         text = node.attrib.get("text", "")
#         cls = node.attrib.get("class", "")
#         clickable = node.attrib.get("clickable", "")

#         # শুধু target application's elements রাখছি
#         if resource_id.startswith(START_APP):

#             elements.append(
#                 (
#                     resource_id,
#                     text,
#                     cls,
#                     clickable
#                 )
#             )

#     state_data = (
#         activity,
#         tuple(elements)
#     )

#     state_hash = hashlib.sha256(
#         repr(state_data).encode("utf-8")
#     ).hexdigest()[:12]

#     return {
#         "hash": state_hash,
#         "package": package,
#         "activity": activity,
#     }


# # --------------------------------------------------
# # Find clickable elements
# # --------------------------------------------------

# def find_actions():

#     xml = d.dump_hierarchy()

#     root = ET.fromstring(xml)

#     actions = []

#     for node in root.iter():

#         resource_id = node.attrib.get("resource-id", "")
#         clickable = node.attrib.get("clickable", "")

#         if (
#             clickable == "true"
#             and resource_id.startswith(START_APP)
#         ):

#             actions.append({
#                 "resource_id": resource_id,
#                 "text": node.attrib.get("text", ""),
#                 "class": node.attrib.get("class", ""),
#                 "bounds": node.attrib.get("bounds", "")
#             })

#     # Same resource-id multiple times থাকলে duplicate বাদ
#     unique = {}

#     for action in actions:
#         unique[action["resource_id"]] = action

#     return list(unique.values())


# # --------------------------------------------------
# # Make sure app is in foreground
# # --------------------------------------------------

# def app_is_foreground():

#     current = d.app_current()

#     return current.get("package") == START_APP


# # --------------------------------------------------
# # Return to application
# # --------------------------------------------------

# def recover_to_app():

#     print("  [RECOVER] Application left foreground.")

#     # App launch করার চেষ্টা
#     try:

#         d.app_start(START_APP)

#         time.sleep(WAIT_AFTER_ACTION)

#         if app_is_foreground():

#             print("  [RECOVER] Application restored.")
#             return True

#     except Exception as e:

#         print(f"  [RECOVER] Failed: {e}")

#     return False


# # --------------------------------------------------
# # Safe backtracking
# # --------------------------------------------------

# def safe_back(expected_state=None):

#     """
#     Back press করার আগে এবং পরে application state check করে।

#     যদি Back application থেকে বের করে দেয়,
#     তাহলে app আবার launch করার চেষ্টা করে।
#     """

#     print("  [BACK] Pressing Android Back...")

#     before = get_state()

#     if before is None:
#         print("  [BACK] Already outside application.")
#         return False

#     d.press("back")

#     time.sleep(WAIT_AFTER_BACK)

#     after = get_state()

#     # App থেকে বের হয়ে গেছে
#     if after is None:

#         print("  [BACK] WARNING: App left foreground!")

#         recovered = recover_to_app()

#         if not recovered:
#             return False

#         return False

#     print(
#         f"  [BACK] Returned to "
#         f"{after['activity']} "
#         f"state={after['hash']}"
#     )

#     return True


# # --------------------------------------------------
# # Print state information
# # --------------------------------------------------

# def print_state(depth, state, actions):

#     indent = "  " * depth

#     print()
#     print(indent + "-" * 55)

#     print(
#         indent
#         + f"DEPTH={depth} "
#         + f"ACTIVITY={state['activity']} "
#         + f"STATE={state['hash']}"
#     )

#     print(
#         indent
#         + f"Clickable actions: {len(actions)}"
#     )

#     for i, action in enumerate(actions):

#         print(
#             indent
#             + f"[{i}] "
#             + action["resource_id"]
#             + f" text={action['text']!r}"
#             + f" class={action['class']}"
#         )


# # --------------------------------------------------
# # Recursive DFS exploration
# # --------------------------------------------------

# def explore(depth=0):

#     if depth > MAX_DEPTH:

#         print(
#             "  " * depth
#             + "Maximum depth reached."
#         )

#         return

#     state = get_state()

#     # App-এর বাইরে
#     if state is None:

#         print(
#             "  " * depth
#             + "Outside target application."
#         )

#         return

#     # Already visited
#     if state["hash"] in visited:

#         print(
#             "  " * depth
#             + f"Already visited {state['hash']}"
#         )

#         return

#     visited.add(state["hash"])

#     actions = find_actions()

#     print_state(
#         depth,
#         state,
#         actions
#     )

#     parent_state = state["hash"]

#     # ------------------------------------------------
#     # Explore each clickable element
#     # ------------------------------------------------

#     for index, action in enumerate(actions):

#         resource_id = action["resource_id"]

#         print()
#         print(
#             "  " * depth
#             + f">>> ACTION {index}: {resource_id}"
#         )

#         # Current state confirm
#         current = get_state()

#         if current is None:

#             print(
#                 "  " * depth
#                 + "Application not in foreground."
#             )

#             if not recover_to_app():
#                 return

#             continue

#         # ------------------------------------------------
#         # Click
#         # ------------------------------------------------

#         try:

#             d(resourceId=resource_id).click()

#         except Exception as e:

#             print(
#                 "  " * depth
#                 + f"CLICK FAILED: {e}"
#             )

#             continue

#         time.sleep(WAIT_AFTER_ACTION)

#         # ------------------------------------------------
#         # Detect destination
#         # ------------------------------------------------

#         destination = get_state()

#         if destination is None:

#             print(
#                 "  " * depth
#                 + "Action caused app to leave foreground."
#             )

#             recover_to_app()

#             continue

#         print(
#             "  " * depth
#             + f">>> DESTINATION: "
#             + f"{destination['activity']} "
#             + f"[{destination['hash']}]"
#         )

#         transitions.append({
#             "source": parent_state,
#             "action": resource_id,
#             "destination": destination["hash"]
#         })

#         # ------------------------------------------------
#         # Recursive exploration
#         # ------------------------------------------------

#         if destination["hash"] not in visited:

#             explore(depth + 1)

#         # ------------------------------------------------
#         # Return to parent
#         # ------------------------------------------------

#         print(
#             "  " * depth
#             + "<<< Attempting backtrack"
#         )

#         success = safe_back()

#         if not success:

#             print(
#                 "  " * depth
#                 + "Backtracking did not return normally."
#             )

#             # app পুনরায় foreground-এ আনার চেষ্টা
#             if recover_to_app():

#                 print(
#                     "  " * depth
#                     + "Application recovered."
#                 )

#             else:

#                 print(
#                     "  " * depth
#                     + "Could not recover application."
#                 )

#                 return


# # --------------------------------------------------
# # Main
# # --------------------------------------------------

# def main():

#     print("Starting recursive exploration...")
#     print()

#     # প্রথম state
#     state = get_state()

#     if state is None:

#         print(
#             "ERROR: Target application is not currently "
#             "in the foreground."
#         )

#         return

#     explore()

#     print()
#     print("=" * 60)
#     print("EXPLORATION FINISHED")
#     print("=" * 60)

#     print(f"Visited states: {len(visited)}")
#     print(f"Transitions: {len(transitions)}")

#     print()
#     print("DISCOVERED GRAPH")
#     print("-" * 60)

#     for t in transitions:

#         print(
#             f"{t['source']}"
#             f" --[{t['action']}]--> "
#             f"{t['destination']}"
#         )


# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
"""
Automatic UI explorer (uiautomator2).

Usage:
    python ui_explorer.py                 # explore whatever app is in the foreground
    python ui_explorer.py com.some.pkg    # launch and explore this package

Design notes
- One hierarchy dump per observation (state hash and actions come from the same dump).
- State hash = activity + SET of (resource-id, class, clickable) of app-owned nodes.
  No text, no bounds, so counters/timers/list lengths don't create new states.
- Actions are clicked by coordinates, so duplicate resource-ids (list items) work.
- Backtracking is verified: after returning, the state must equal the parent state.
  If Back fails, the app is restarted and the recorded path is replayed.
- Transient waits are replaced with a "settle" poll (hash stable across two dumps).
"""
#!/usr/bin/env python3
"""
Robust recursive UI explorer for Android (uiautomator2).

    python ui_explorer_v2.py                       # explore the foreground app
    python ui_explorer_v2.py com.some.pkg          # launch + explore a package
    python ui_explorer_v2.py com.some.pkg --minutes 20 --depth 8 --shots shots

What changed, mapped to the problems you reported
--------------------------------------------------
1. "Gets out of the app"
   - A click that opens another package (share sheet, WhatsApp, browser, Play
     Store, camera...) is detected, recorded as EXTERNAL:<pkg>, and escaped via
     Back -> bring-to-front -> restart+replay. Back is never pressed blindly.
   - Permission dialogs are auto-accepted; crash/ANR dialogs are dismissed,
     logged, and recovered from.

2. "Repeats the same work after returning"
   - Every action tried in a state is remembered (TRIED), globally. Coming back
     to a state - by Back, by replay, or by another path - never re-clicks.
   - State identity is fuzzy: same activity + >= SIM_MERGE overlap of the
     widget set is the same state, so tiny UI drift does not create "new" states.
   - After returning from a child the screen is re-read; the next action is
     chosen from the FRESH hierarchy, not from a stale list with old coordinates.
   - A state that was aborted midway (a child navigated "up" past it) is not
     marked complete and gets resumed later.

3. "Hangs on unusual screens"
   - Every device call runs under a watchdog thread with a timeout.
   - Idle-wait is disabled in uiautomator so endless animations/video do not
     block hierarchy dumps.
   - Global time budget and state cap guarantee termination.

Coverage extras: scrolling, text input, long-click, checkable widgets, and a
best-effort system image picker handler (needed for photo-editor-type apps).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

import uiautomator2 as u2

# ----------------------------------------------------------------------------
# Configuration (all overridable from the command line where it makes sense)
# ----------------------------------------------------------------------------
MAX_DEPTH = 8
MAX_STATES = 300
MAX_MINUTES = 3
MAX_SWIPES = 10          # swipes per visit of a state
PER_GROUP = 3            # max actions per resource-id group per state (list rows)
SIM_MERGE = 0.9          # Jaccard similarity to treat two screens as the same state
SETTLE_TIMEOUT = 4.0
SETTLE_POLL = 0.4
POST_ACTION_DELAY = 0.6
CALL_TIMEOUT = 15        # watchdog for any single device call
DUMP_TIMEOUT = 12
OUT_JSON = "ui_graph.json"
SHOTS = None             # directory for per-state screenshots
LONG_CLICK = True
TEXT_INPUT = True
PICK_MEDIA = True

# Never click things that look destructive / billing / account related.
BLOCKLIST = re.compile(
    r"delete|uninstall|purchase|\bbuy\b|subscribe|sign.?out|log.?out|factory|erase.?all",
    re.I,
)
# Explored last in each state: they usually just go back up.
LOW_PRIORITY = re.compile(r"navigate up|\bback\b|\bclose\b|cancel|dismiss", re.I)

PERMISSION_PKGS = {
    "com.google.android.permissioncontroller",
    "com.android.permissioncontroller",
}
ALLOW_RE = r"(?i)^(allow|while using the app|only this time|ok|got it|continue)$"
CRASH_RE = r"(?i).*(has stopped|keeps stopping|isn't responding|not responding).*"
CRASH_PKGS = {"android", "com.android.systemui"}

# System file/photo pickers. Adjust to your emulator image if needed.
PICKER_PKGS = {
    "com.google.android.documentsui",
    "com.android.documentsui",
    "com.google.android.providers.media.module",
    "com.android.providers.media.module",
    "com.google.android.apps.photos",
    "com.sec.android.gallery3d",
    "com.android.gallery3d",
}
CONFIRM_RE = re.compile(r"(?i)^(done|add|select|open|choose|ok)$")
LAUNCHER_RE = re.compile(r"launcher|\.home$|nexuslauncher", re.I)

# ----------------------------------------------------------------------------
# Global state
# ----------------------------------------------------------------------------
d = None
TARGET = None
DEADLINE = 0.0

states = {}                      # sid -> metadata
known = {}                       # raw hash -> canonical sid
transitions = set()              # (src, label, dst)
TRIED = defaultdict(set)         # sid -> action keys already performed
GROUP = defaultdict(lambda: defaultdict(int))   # sid -> group -> count tried
FILLED = defaultdict(set)        # sid -> edit-field keys already filled
COMPLETE = set()                 # sids whose action list was fully exhausted
EXTERNAL = defaultdict(int)      # external package -> times reached
EVENTS = []                      # crashes, recoveries, etc.


def log(msg):
    print(msg, flush=True)


# ----------------------------------------------------------------------------
# Watchdog + device helpers
# ----------------------------------------------------------------------------
def guarded(fn, *args, timeout=None, default=None, **kwargs):
    """Run a device call in a daemon thread; give up after `timeout` seconds."""
    timeout = timeout or CALL_TIMEOUT
    box = {}

    def run():
        try:
            box["v"] = fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    name = getattr(fn, "__name__", "call")
    if t.is_alive():
        log(f"    [WATCHDOG] {name} timed out after {timeout}s")
        return default
    if "e" in box:
        log(f"    [WARN] {name}: {box['e']!r}")
        return default
    return box.get("v", default)


def current():
    c = guarded(d.app_current, default=None) or {}
    return c.get("package", ""), c.get("activity", "")


def dump():
    xml = guarded(d.dump_hierarchy, timeout=DUMP_TIMEOUT, default=None)
    if not xml:
        return None
    try:
        return ET.fromstring(xml)
    except ET.ParseError:
        return None


def parse_bounds(b):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def center_of(bt):
    return (bt[0] + bt[2]) // 2, (bt[1] + bt[3]) // 2


def start_app():
    guarded(d.app_start, TARGET, use_monkey=True, timeout=20)


def out_of_budget():
    return time.time() > DEADLINE or len(states) >= MAX_STATES


# ----------------------------------------------------------------------------
# Observation
# ----------------------------------------------------------------------------
def pick_text(label):
    s = label.lower()
    if "mail" in s:
        return "test@example.com"
    if "pass" in s or "pwd" in s:
        return "Test@12345"
    if any(k in s for k in ("otp", "code", "pin")):
        return "123456"
    if any(k in s for k in ("phone", "mobile", "number", "age", "zip", "amount")):
        return "1234567890"
    if any(k in s for k in ("url", "http", "link", "web")):
        return "https://example.com"
    return "test"


def snapshot():
    """
    One hierarchy dump -> everything we need.
    hash is None when we are not inside TARGET (or the dump failed).
    """
    pkg, act = current()
    snap = {
        "package": pkg, "activity": act, "hash": None, "sig": frozenset(),
        "actions": [], "edits": [], "scrollables": [], "fp": (),
    }
    if pkg != TARGET:
        return snap
    root = dump()
    if root is None:
        return snap

    sig = set()
    actions, edits, scrolls = [], [], []
    seen = defaultdict(int)

    for n in root.iter("node"):
        if n.get("package") != TARGET:
            continue
        rid = n.get("resource-id", "")
        cls = n.get("class", "")
        text = n.get("text", "")
        desc = n.get("content-desc", "")
        clickable = n.get("clickable") == "true"
        longc = n.get("long-clickable") == "true"
        checkable = n.get("checkable") == "true"
        bt = parse_bounds(n.get("bounds"))

        if rid or clickable:
            sig.add((rid, cls, clickable))
        if bt is None:
            continue
        if n.get("scrollable") == "true":
            scrolls.append(bt)

        label = " ".join([rid, text, desc])
        base = f"{rid or cls}|{hashlib.md5((text + '|' + desc).encode()).hexdigest()[:6]}"

        if "EditText" in cls or "AutoCompleteTextView" in cls:
            if TEXT_INPUT and n.get("enabled") != "false":
                seen[base + "#e"] += 1
                edits.append({"key": f"{base}#e{seen[base + '#e']}",
                              "xy": center_of(bt), "label": label})
            continue

        if not (clickable or checkable or longc):
            continue
        if BLOCKLIST.search(label):
            continue

        seen[base] += 1
        key = f"{base}#{seen[base]}"
        group = rid or cls
        low = bool(LOW_PRIORITY.search(label))
        xy = center_of(bt)
        if clickable or checkable:
            actions.append({"kind": "click", "key": key, "group": group,
                            "label": rid or desc or text or cls, "text": text,
                            "xy": xy, "low": low})
        if longc and LONG_CLICK:
            actions.append({"kind": "long", "key": key + ":long",
                            "group": group + ":long",
                            "label": (rid or desc or text or cls) + " (long)",
                            "text": text, "xy": xy, "low": low})

    snap["sig"] = frozenset(sig)
    snap["actions"] = actions
    snap["edits"] = edits
    snap["scrollables"] = scrolls
    snap["fp"] = tuple(sorted((a["key"], a["xy"]) for a in actions))
    snap["hash"] = hashlib.sha256(
        (act + repr(sorted(sig))).encode()).hexdigest()[:12]
    return snap


def jaccard(a, b):
    u = len(a | b)
    return 1.0 if u == 0 else len(a & b) / u


def canon(snap):
    """Canonical state id: exact hash, or the most similar known state."""
    h = snap["hash"]
    if h in known:
        return known[h]
    best, best_s = None, 0.0
    for sid, st in states.items():
        if st["activity"] != snap["activity"]:
            continue
        s = jaccard(snap["sig"], st["sig"])
        if s > best_s:
            best, best_s = sid, s
    sid = best if (best and best_s >= SIM_MERGE) else h
    known[h] = sid
    return sid


def register(sid, snap, depth):
    if sid in states:
        return False
    states[sid] = {"activity": snap["activity"], "sig": snap["sig"],
                   "n_actions": len(snap["actions"]), "depth": depth,
                   "shot": None}
    log(f"    [NEW STATE] {sid} {snap['activity']} "
        f"(actions={len(snap['actions'])}, total states={len(states)})")
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        path = os.path.join(SHOTS, f"{sid}.png")
        guarded(d.screenshot, path)
        states[sid]["shot"] = path
    return True


# ----------------------------------------------------------------------------
# System dialogs, settling
# ----------------------------------------------------------------------------
def click_allow():
    def f():
        b = d(textMatches=ALLOW_RE)
        if b.exists:
            b.click()
            return True
        return False
    return guarded(f, default=False)


def dismiss_crash():
    def f():
        if d(textMatches=CRASH_RE).exists:
            EVENTS.append({"type": "crash_or_anr", "t": time.time()})
            log("    [EVENT] crash/ANR dialog detected")
            b = d(textMatches=r"(?i)^(close app|close|ok)$")
            if b.exists:
                b.click()
            return True
        return False
    return guarded(f, default=False)


def settle():
    """
    Poll until (package, hash) is stable across two dumps.
    Auto-handles permission and crash dialogs. Returns immediately once we know
    we are in some other app (nothing to wait for there).
    """
    deadline = time.time() + SETTLE_TIMEOUT
    prev = None
    while True:
        snap = snapshot()
        pkg = snap["package"]
        key = (snap["hash"], pkg)
        if pkg in PERMISSION_PKGS and click_allow():
            prev = None
        elif pkg in CRASH_PKGS and dismiss_crash():
            prev = None
        elif pkg != TARGET and pkg not in PERMISSION_PKGS and pkg not in CRASH_PKGS:
            return snap
        elif key == prev:
            return snap
        else:
            prev = key
        if time.time() > deadline:
            return snap
        time.sleep(SETTLE_POLL)


# ----------------------------------------------------------------------------
# Leaving external apps
# ----------------------------------------------------------------------------
def try_pick_media():
    """Best-effort: choose the first image in a system picker. UI varies by image."""
    for step in range(5):
        pkg, _ = current()
        if pkg == TARGET:
            return True
        root = dump()
        if root is None:
            return False
        confirm = thumb = None
        for n in root.iter("node"):
            if n.get("package") != pkg or n.get("clickable") != "true":
                continue
            bt = parse_bounds(n.get("bounds"))
            if bt is None:
                continue
            w, h = bt[2] - bt[0], bt[3] - bt[1]
            rid, cls, text = n.get("resource-id", ""), n.get("class", ""), n.get("text", "")
            if confirm is None and CONFIRM_RE.match(text.strip()):
                confirm = center_of(bt)
            looks_thumb = ("ImageView" in cls or re.search(r"thumb|image|photo|media", rid, re.I))
            if thumb is None and looks_thumb and w > 120 and h > 120 and bt[1] > 250:
                thumb = center_of(bt)
        target = confirm or thumb
        if target is None:
            return False
        log(f"    [PICKER] step {step}: tapping {target} in {pkg}")
        guarded(d.click, *target)
        time.sleep(1.0)
    return current()[0] == TARGET


def leave_external():
    """Get back into TARGET: Back (twice) -> bring to front -> give up."""
    pkg, _ = current()
    if pkg == TARGET:
        time.sleep(1.0)      # in-app but unreadable (dump failed): just wait
        return True
    if not LAUNCHER_RE.search(pkg):
        for _ in range(2):
            guarded(d.press, "back")
            time.sleep(0.6)
            pkg, _ = current()
            if pkg == TARGET:
                return True
            if pkg in PERMISSION_PKGS:
                click_allow()
    start_app()
    time.sleep(1.0)
    return current()[0] == TARGET


def resolve_external(snap):
    """We are outside TARGET. Pick media if it is a picker, else escape. Re-settle."""
    pkg = snap["package"]
    if PICK_MEDIA and pkg in PICKER_PKGS:
        try_pick_media()
    if current()[0] != TARGET:
        leave_external()
    return settle()


# ----------------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------------
def perform(act):
    x, y = act["xy"]
    if act["kind"] == "long":
        guarded(d.long_click, x, y)
    else:
        guarded(d.click, x, y)
    time.sleep(POST_ACTION_DELAY)


def fill_inputs(sid, cur):
    """Type dummy text into any untouched EditText. Returns a fresh snapshot if used."""
    if not TEXT_INPUT:
        return cur
    todo = [e for e in cur["edits"] if e["key"] not in FILLED[sid]]
    if not todo:
        return cur
    for e in todo:
        FILLED[sid].add(e["key"])
        guarded(d.click, *e["xy"])
        time.sleep(0.3)
        guarded(lambda t=pick_text(e["label"]): d.send_keys(t, clear=True))
        log(f"    [INPUT] {e['label']!r}")
    return settle()


def pick(sid, cur, low):
    cands = [a for a in cur["actions"]
             if a["low"] == low
             and a["key"] not in TRIED[sid]
             and GROUP[sid][a["group"]] < PER_GROUP]
    if not cands:
        return None
    cands.sort(key=lambda a: (a["kind"] != "click", a["xy"][1], a["xy"][0]))
    return cands[0]


def scroll_once(cur):
    """Swipe the largest scrollable. None = nothing scrollable / end reached."""
    if not cur["scrollables"]:
        return None
    x1, y1, x2, y2 = max(cur["scrollables"],
                         key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    cx, h = (x1 + x2) // 2, y2 - y1
    guarded(d.swipe, cx, y1 + int(h * 0.8), cx, y1 + int(h * 0.2), 0.25)
    nxt = settle()
    if nxt["hash"] is not None and nxt["fp"] == cur["fp"]:
        return None
    return nxt


def find_action(snap, key):
    for a in snap["actions"]:
        if a["key"] == key:
            return a
    return None


def find_with_scroll(snap, step):
    a = find_action(snap, step["key"])
    if a:
        return snap, a
    for _ in range(step.get("swipes", 0) + 2):
        nxt = scroll_once(snap)
        if nxt is None or nxt["hash"] is None:
            break
        snap = nxt
        a = find_action(snap, step["key"])
        if a:
            return snap, a
    return snap, None


# ----------------------------------------------------------------------------
# Returning to a state
# ----------------------------------------------------------------------------
def status(snap, sid, ancestors):
    if snap is None or snap["hash"] is None:
        return "out"
    c = canon(snap)
    if c == sid:
        return "ok"
    if c in ancestors:
        return "ancestor"
    return "other"


def replay(path):
    """Restart the app and re-perform the recorded path (by action key, not coords)."""
    log(f"    [REPLAY] restart + {len(path)} step(s)")
    guarded(d.app_stop, TARGET)
    time.sleep(0.7)
    start_app()
    snap = settle()
    for step in path:
        if snap["hash"] is None:
            snap = resolve_external(snap)
            if snap["hash"] is None:
                return snap
        snap, act = find_with_scroll(snap, step)
        if act is None:
            log(f"    [REPLAY] could not find {step['label']!r}")
            return snap
        perform(act)
        snap = settle()
        if snap["hash"] is None and snap["package"] != TARGET:
            snap = resolve_external(snap)
    return snap


def return_to(sid, cur, path, ancestors):
    """
    Make the device show state `sid`.
    Returns (result, snapshot), result in:
      ok        - we are on sid
      ancestor  - we are on a state above sid (the caller should abort this level)
      lost      - could not get back
    Back is pressed only when we are on some unrelated state of the app, and at
    most twice (dialog/keyboard + one real navigation).
    """
    cur = cur or settle()
    st = status(cur, sid, ancestors)
    if st in ("ok", "ancestor"):
        return st, cur

    if st == "out":
        cur = resolve_external(cur) if cur["package"] != TARGET else settle()
        st = status(cur, sid, ancestors)
        if st in ("ok", "ancestor"):
            return st, cur

    backs = 0
    while st == "other" and backs < 2:
        guarded(d.press, "back")
        backs += 1
        cur = settle()
        if cur["hash"] is None and cur["package"] != TARGET:
            cur = resolve_external(cur)
        st = status(cur, sid, ancestors)
        if st in ("ok", "ancestor"):
            return st, cur

    for _ in range(2):
        cur = replay(path)
        st = status(cur, sid, ancestors)
        if st in ("ok", "ancestor"):
            EVENTS.append({"type": "replay_recovery", "state": sid})
            return st, cur
    return "lost", cur


# ----------------------------------------------------------------------------
# Recursive exploration
# ----------------------------------------------------------------------------
def explore(sid, snap, path, depth):
    ancestors = {p["src"] for p in path}
    log("\n" + "  " * depth + "-" * 50)
    log("  " * depth + f"DEPTH={depth} STATE={sid} ACTIVITY={snap['activity']}")

    swipes = 0
    cur = snap
    indent = "  " * depth

    while not out_of_budget():
        if cur is None:
            cur = settle()
        st = status(cur, sid, ancestors)
        if st != "ok":
            st, cur = return_to(sid, cur, path, ancestors)
            if st != "ok":
                log(f"{indent}<<< leaving {sid} ({st}); not marked complete")
                return

        cur = fill_inputs(sid, cur)
        if status(cur, sid, ancestors) != "ok":
            continue

        act = pick(sid, cur, low=False)
        if act is None:
            nxt = scroll_once(cur) if swipes < MAX_SWIPES else None
            if nxt is not None:
                swipes += 1
                cur = nxt
                continue
            act = pick(sid, cur, low=True)
            if act is None:
                COMPLETE.add(sid)
                log(f"{indent}<<< state {sid} complete "
                    f"({len(TRIED[sid])} actions tried)")
                return

        TRIED[sid].add(act["key"])
        GROUP[sid][act["group"]] += 1
        log(f"{indent}>>> {act['kind'].upper()} {act['label']} "
            f"{act['text']!r} @ {act['xy']}")

        perform(act)
        new = settle()

        if new["hash"] is None and new["package"] != TARGET:
            pkg = new["package"]
            EXTERNAL[pkg] += 1
            transitions.add((sid, act["label"], f"EXTERNAL:{pkg}"))
            log(f"{indent}    left app -> {pkg}")
            new = resolve_external(new)

        if new["hash"] is None:
            cur = new            # loop top will recover
            continue

        nsid = canon(new)
        transitions.add((sid, act["label"], nsid))
        if nsid == sid or nsid in ancestors:
            cur = new            # nothing changed, or we popped upward
            continue

        register(nsid, new, depth + 1)
        if nsid not in COMPLETE and depth + 1 <= MAX_DEPTH:
            step = {"key": act["key"], "label": act["label"],
                    "src": sid, "swipes": swipes}
            explore(nsid, new, path + [step], depth + 1)
        cur = None               # force a fresh read on return


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def configure_device():
    try:
        d.implicitly_wait(2.0)
    except Exception:  # noqa: BLE001
        pass
    try:   # don't wait for the UI to go idle: animations/video would hang dumps
        d.jsonrpc.setConfigurator({"waitForIdleTimeout": 0,
                                   "waitForSelectorTimeout": 0})
    except Exception as e:  # noqa: BLE001
        log(f"[note] could not disable idle wait: {e!r}")


def write_report():
    activities = sorted({s["activity"] for s in states.values()})
    log("\n" + "=" * 60)
    log(f"States: {len(states)}   complete: {len(COMPLETE)}   "
        f"transitions: {len(transitions)}")
    log(f"Activities reached ({len(activities)}):")
    for a in activities:
        log(f"  {a}")
    if EXTERNAL:
        log("External packages reached:")
        for p, n in sorted(EXTERNAL.items()):
            log(f"  {p} x{n}")
    log(f"Events: {len(EVENTS)} (crashes/ANRs/replay recoveries)")
    with open(OUT_JSON, "w") as f:
        json.dump({
            "target": TARGET,
            "states": {k: {kk: vv for kk, vv in v.items() if kk != "sig"}
                       for k, v in states.items()},
            "complete": sorted(COMPLETE),
            "transitions": [{"src": s, "action": a, "dst": t}
                            for s, a, t in sorted(transitions)],
            "external": dict(EXTERNAL),
            "events": EVENTS,
        }, f, indent=2)
    log(f"Saved {OUT_JSON}")


def main(argv=None):
    global d, TARGET, DEADLINE, MAX_DEPTH, MAX_STATES, MAX_MINUTES
    global OUT_JSON, SHOTS, LONG_CLICK, TEXT_INPUT, PICK_MEDIA
    print("starting uiautomator2 UI explorer...")
    ap = argparse.ArgumentParser()
    ap.add_argument("package", nargs="?")
    ap.add_argument("--depth", type=int, default=MAX_DEPTH)
    ap.add_argument("--max-states", type=int, default=MAX_STATES)
    ap.add_argument("--minutes", type=float, default=MAX_MINUTES)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--shots", default=None)
    ap.add_argument("--no-long", action="store_true")
    ap.add_argument("--no-input", action="store_true")
    ap.add_argument("--no-pick", action="store_true")
    a = ap.parse_args(argv)

    MAX_DEPTH, MAX_STATES, MAX_MINUTES = a.depth, a.max_states, a.minutes
    OUT_JSON, SHOTS = a.out, a.shots
    LONG_CLICK, TEXT_INPUT, PICK_MEDIA = not a.no_long, not a.no_input, not a.no_pick

    d = u2.connect()
    configure_device()
    TARGET = a.package or current()[0]
    if not TARGET:
        raise RuntimeError("Could not determine the target package.")
    if a.package:
        guarded(d.app_stop, TARGET)
        time.sleep(0.7)
        start_app()

    DEADLINE = time.time() + MAX_MINUTES * 60
    log("=" * 60)
    log(f"TARGET={TARGET} depth<={MAX_DEPTH} states<={MAX_STATES} "
        f"budget={MAX_MINUTES}min")
    log("=" * 60)

    root = settle()
    if root["hash"] is None:
        log("Target app is not in the foreground; open it and retry.")
        return
    rsid = canon(root)
    register(rsid, root, 0)

    try:
        for round_no in range(4):          # restart + resume if the root is lost
            explore(rsid, root, [], 0)
            if rsid in COMPLETE or out_of_budget():
                break
            log(f"[root round {round_no + 1}] not complete; restarting app")
            guarded(d.app_stop, TARGET)
            time.sleep(0.7)
            start_app()
            root = settle()
            if root["hash"] is None:
                break
    except KeyboardInterrupt:
        log("\nInterrupted; saving results.")
    finally:
        write_report()


if __name__ == "__main__":
    main()