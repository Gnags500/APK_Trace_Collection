#!/usr/bin/env python3
"""
DL-Droid event parser — API call features.

Reads a Frida logcat file, extracts [DL_EVENT] lines, parses the JSON,
maps each (class, method) pair to its DL-Droid feature name, and writes:
  - <output>.json   : raw event list
  - <output>_vector.json : binary feature vector (1 = observed, 0 = not)

Usage:
    python parse_events.py <input.log> <output_stem>

Example:
    python parse_events.py frida.log results
    -> results.json, results_vector.json
"""

import json
import sys
from pathlib import Path


PREFIX = "[DL_EVENT] "

# -----------------------------------------------------------------------
# DL-Droid API feature map
#
# Maps (class, method) -> canonical DL-Droid feature name.
# The feature name matches the terminology used in DynaLog / DL-Droid
# papers (Table V and the DynaLog paper).
#
# One (class, method) pair maps to exactly one feature name so that the
# binary feature vector stays aligned with the paper's vocabulary.
# -----------------------------------------------------------------------

API_FEATURE_MAP = {

    # ------------------------------------------------------------------
    # Telephony — device identity
    # ------------------------------------------------------------------
    ("android.telephony.TelephonyManager", "getDeviceId"):
        "deviceId",
    ("android.telephony.TelephonyManager", "getSubscriberId"):
        "SubscriberId",
    ("android.telephony.TelephonyManager", "getLine1Number"):
        "lineNumber",
    ("android.telephony.TelephonyManager", "getSimSerialNumber"):
        "SimSerialNumber",

    # ------------------------------------------------------------------
    # Telephony — device identity (modern, API 26+)
    # getDeviceId() deprecated API 26, removed API 29; apps now use
    # getImei()/getMeid() or Build.getSerial(). Same DL-Droid feature.
    # ------------------------------------------------------------------
    ("android.telephony.TelephonyManager", "getImei"):
        "deviceId",
    ("android.telephony.TelephonyManager", "getMeid"):
        "deviceId",
    ("android.telephony.TelephonyManager", "createForSubscriptionId"):
        "deviceId",
    ("android.os.Build", "getSerial"):
        "deviceId",

    # ------------------------------------------------------------------
    # Telephony — operator / SIM info
    # ------------------------------------------------------------------
    ("android.telephony.TelephonyManager", "getNetworkOperatorName"):
        "NetworkOperator",
    ("android.telephony.TelephonyManager", "getSimOperator"):
        "SimOperator",
    ("android.telephony.TelephonyManager", "getSimOperatorName"):
        "SimOperatorNumber",
    ("android.telephony.TelephonyManager", "getSimCountryIso"):
        "SimCountryIso",

    # ------------------------------------------------------------------
    # Network / Wi-Fi
    # ------------------------------------------------------------------
    ("android.net.wifi.WifiManager", "getConnectionInfo"):
        "getConnectionInfo",
    ("android.net.NetworkInfo", "getState"):
        "getState",

    # ------------------------------------------------------------------
    # Network — modern ConnectivityManager (API 29+)
    # NetworkInfo.getState() deprecated API 29; same DL-Droid feature.
    # ------------------------------------------------------------------
    ("android.net.ConnectivityManager", "getNetworkCapabilities"):
        "getState",
    ("android.net.ConnectivityManager", "registerNetworkCallback"):
        "getState",
    ("android.net.ConnectivityManager", "getActiveNetworkInfo"):
        "getState",

    # ------------------------------------------------------------------
    # Network — connection / URI
    # ------------------------------------------------------------------
    ("java.net.URL", "openConnection"):
        "connect",
    ("java.net.HttpURLConnection", "connect"):
        "connect",
    ("android.net.Uri", "parse"):
        "parse",

    # ------------------------------------------------------------------
    # Package manager
    # ------------------------------------------------------------------
    ("android.content.pm.PackageManager", "checkPermission"):
        "checkPermission",
    ("android.content.pm.PackageManager", "getApplicationInfo"):
        "getApplicationInfo",

    # ------------------------------------------------------------------
    # Permission checks — modern path
    # Many apps use Context.checkSelfPermission() rather than
    # PackageManager.checkPermission(). Same DL-Droid feature.
    # ------------------------------------------------------------------
    ("android.content.Context", "checkSelfPermission"):
        "checkPermission",
    ("android.content.Context", "checkCallingPermission"):
        "checkPermission",
    ("android.content.ContextWrapper", "checkSelfPermission"):
        "checkPermission",

    # ------------------------------------------------------------------
    # Context — service binding
    # ------------------------------------------------------------------
    ("android.content.ContextWrapper", "bindService"):
        "bindService",
    ("android.content.ContextWrapper", "unbindService"):
        "unbindService",

    # ------------------------------------------------------------------
    # Process execution
    # ------------------------------------------------------------------
    ("java.lang.Runtime", "exec"):
        "runtime.exec",
    ("java.lang.ProcessBuilder", "start"):
        "Process",

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------
    ("java.lang.Class", "getMethod"):
        "getMethod",
    ("java.lang.Class", "getDeclaredMethod"):
        "getMethod",        # same DL-Droid feature
    ("java.lang.Object", "getClass"):
        "getClass",

    # ------------------------------------------------------------------
    # Cryptography
    # ------------------------------------------------------------------
    ("java.security.MessageDigest", "getInstance"):
        "getInstance",
    ("java.security.MessageDigest", "digest"):
        "digest",
    ("javax.crypto.Cipher", "getInstance"):
        "getInstance",      # same DL-Droid feature as MessageDigest.getInstance
    ("javax.crypto.Cipher", "init"):
        "initCipher",
    ("javax.crypto.KeyGenerator", "getInstance"):
        "getInstance",
    ("javax.crypto.KeyGenerator", "generateKey"):
        "SecretKey",

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    ("java.io.FileOutputStream", "write"):
        "fileWrite",
    ("java.io.File", "exists"):
        "fileExists",

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    ("android.database.sqlite.SQLiteDatabase", "openOrCreateDatabase"):
        "openOrCreateDatabase",

    # ------------------------------------------------------------------
    # Content provider
    # ------------------------------------------------------------------
    ("android.content.ContentResolver", "query"):
        "ContentResolver",
    ("android.content.ContentResolver", "insert"):
        "ContentResolver",
    ("android.content.ContentResolver", "update"):
        "ContentResolver",
    ("android.content.ContentResolver", "delete"):
        "ContentResolver",

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------
    ("android.location.LocationManager", "getLastKnownLocation"):
        "getLastKnownLocation",

    # ------------------------------------------------------------------
    # Native library loading
    # ------------------------------------------------------------------
    ("java.lang.System", "loadLibrary"):
        "LoadLibrary",
    ("java.lang.System", "load"):
        "LoadLibrary",

    # ------------------------------------------------------------------
    # SMS
    # ------------------------------------------------------------------
    ("android.telephony.SmsManager", "sendTextMessage"):
        "sendsms",
    ("android.telephony.SmsManager", "sendMultipartTextMessage"):
        "sendsms",
}

# All unique DL-Droid API feature names (the columns of our vector).
ALL_API_FEATURES = sorted(set(API_FEATURE_MAP.values()))

# -----------------------------------------------------------------------
# DL-Droid Intent feature map
#
# Maps broadcast action string -> canonical DL-Droid feature name.
# Covers both intent_registered and intent_received event types.
# A feature is marked 1 if the app either registered for the action
# OR actually received it during the analysis window.
# -----------------------------------------------------------------------

INTENT_FEATURE_MAP = {
    'android.provider.Telephony.SMS_RECEIVED':          'action.SMS_RECEIVED',
    'android.intent.action.NEW_OUTGOING_CALL':          'action.NEW_OUTGOING_CALL',
    'android.intent.action.PHONE_STATE':                'action.PHONE_STATE',
    'android.intent.action.BOOT_COMPLETED':             'action.BOOT_COMPLETED',
    'android.intent.action.USER_PRESENT':               'action.USER_PRESENT',
    'android.net.conn.CONNECTIVITY_CHANGE':             'action.CONNECTIVITY_CHANGE',
    'android.intent.action.PACKAGE_ADDED':              'action.PACKAGE_ADDED',
    'android.intent.action.PACKAGE_REMOVED':            'action.PACKAGE_REMOVED',
    'android.intent.action.PACKAGE_REPLACED':           'action.PACKAGE_REPLACED',
    'android.intent.action.PACKAGE_CHANGED':            'action.PACKAGE_CHANGED',
    'android.intent.action.PACKAGE_RESTARTED':          'action.PACKAGE_RESTARTED',
    'android.intent.action.PACKAGE_INSTALL':            'action.PACKAGE_INSTALL',
    'android.intent.action.ACTION_POWER_CONNECTED':     'action.POWER_CONNECTED',
    'android.intent.action.ACTION_POWER_DISCONNECTED':  'action.POWER_DISCONNECTED',
    'android.intent.action.BATTERY_LOW':                'action.BATTERY_LOW',
    'android.intent.action.BATTERY_OKAY':               'action.BATTERY_OKAY',
    'android.intent.action.BATTERY_CHANGED':            'action.BATTERY_CHANGED',
    'android.intent.action.UMS_CONNECTED':              'action.UMS_CONNECTED',
    'android.intent.action.UMS_DISCONNECTED':           'action.UMS_DISCONNECTED',
    'android.intent.action.SIM_FULL':                   'action.SIM_FULL',
    'android.intent.action.SIG_STR':                    'action.SIG_STR',
    'android.intent.action.INPUT_METHOD_CHANGED':       'action.INPUT_METHOD_CHANGED',
    'android.intent.action.MAIN':                       'action.ACTION_MAIN',
}

ALL_INTENT_FEATURES = sorted(set(INTENT_FEATURE_MAP.values()))


def parse_file(input_file: Path, output_stem: Path):

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
                print(f"[!] Could not parse: {payload}", file=sys.stderr)
                continue
            events.append(event)

    # Save raw events
    raw_out = output_stem.with_suffix(".json")
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    # ----------------------------------------------------------------
    # Build binary feature vector
    # ----------------------------------------------------------------
    api_events = [e for e in events if e.get("type") == "api"]

    observed_features: set[str] = set()
    unknown_apis: set[tuple] = set()

    for e in api_events:
        cls = e.get("class", "")
        mth = e.get("method", "")
        key = (cls, mth)
        if key in API_FEATURE_MAP:
            observed_features.add(API_FEATURE_MAP[key])
        else:
            unknown_apis.add(key)

    vector = {feature: int(feature in observed_features)
              for feature in ALL_API_FEATURES}

    # ----------------------------------------------------------------
    # Build intent feature vector
    # ----------------------------------------------------------------
    intent_events = [
        e for e in events
        if e.get("type") in ("intent_registered", "intent_received")
    ]

    observed_intents: set[str] = set()

    for e in intent_events:
        action = e.get("action", "")
        if action in INTENT_FEATURE_MAP:
            observed_intents.add(INTENT_FEATURE_MAP[action])

    intent_vector = {feature: int(feature in observed_intents)
                     for feature in ALL_INTENT_FEATURES}

    # Merge API + intent into one combined vector
    combined_vector = {**vector, **intent_vector}

    vec_out = Path(str(output_stem) + "_vector.json")
    with open(vec_out, "w", encoding="utf-8") as f:
        json.dump(combined_vector, f, indent=2)

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    print("=" * 60)
    print("DL-Droid event parser — API features")
    print("=" * 60)
    print(f"Input        : {input_file}")
    print(f"Raw events   : {raw_out}  ({len(events)} events)")
    print(f"Feature vec  : {vec_out}")
    print()
    print(f"Total events   : {len(events)}")
    print(f"API events     : {len(api_events)}")
    print(f"Intent events  : {len(intent_events)}")
    print(f"API features   : {len(observed_features)} / {len(ALL_API_FEATURES)}")
    print(f"Intent features: {len(observed_intents)} / {len(ALL_INTENT_FEATURES)}")
    print()

    print("API FEATURE VECTOR")
    print("-" * 40)
    for feature, value in sorted(vector.items()):
        mark = "✓" if value else " "
        print(f"  [{mark}] {feature}")

    print()
    print("INTENT FEATURE VECTOR")
    print("-" * 40)
    for feature, value in sorted(intent_vector.items()):
        mark = "✓" if value else " "
        print(f"  [{mark}] {feature}")

    if unknown_apis:
        print()
        print("UNKNOWN API CALLS (not in DL-Droid map)")
        print("-" * 40)
        for cls, mth in sorted(unknown_apis):
            print(f"  {cls}->{mth}")

    # ----------------------------------------------------------------
    # Write full unique API call list to file
    # ----------------------------------------------------------------
    apis_out = Path(str(output_stem) + "_apis.txt")

    all_unique_apis = sorted({
        f"{e.get('class', '')}->{e.get('method', '')}"
        for e in api_events
    })

    with open(apis_out, "w", encoding="utf-8") as f:
        f.write(f"Total unique API calls: {len(all_unique_apis)}\n")
        f.write("-" * 60 + "\n\n")
        for api in all_unique_apis:
            key = tuple(api.split("->", 1))
            feature = API_FEATURE_MAP.get(key, "not in DL-Droid map")
            f.write(f"{api}  [{feature}]\n")

    print(f"API list     : {apis_out}")

    # ----------------------------------------------------------------
    # Write intent event list to file
    # ----------------------------------------------------------------
    intents_out = Path(str(output_stem) + "_intents.txt")

    all_unique_intents = sorted({
        e.get("action", "")
        for e in intent_events
        if e.get("action", "")
    })

    with open(intents_out, "w", encoding="utf-8") as f:
        f.write(f"Total unique intent actions: {len(all_unique_intents)}\n")
        f.write("-" * 60 + "\n\n")
        for action in all_unique_intents:
            feature  = INTENT_FEATURE_MAP.get(action, "not in DL-Droid map")
            # show which events fired for this action
            reg  = sum(1 for e in intent_events
                       if e.get("action") == action
                       and e.get("type") == "intent_registered")
            recv = sum(1 for e in intent_events
                       if e.get("action") == action
                       and e.get("type") == "intent_received")
            f.write(f"{action}\n")
            f.write(f"  feature   : {feature}\n")
            f.write(f"  registered: {reg}  received: {recv}\n\n")

    print(f"Intent list  : {intents_out}")


def main():
    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "  python parse_events.py <input.log> <output_stem>\n\n"
            "Example:\n"
            "  python parse_events.py frida.log results\n"
            "  -> results.json, results_vector.json"
        )
        sys.exit(1)

    input_file  = Path(sys.argv[1])
    output_stem = Path(sys.argv[2])

    if not input_file.exists():
        print(f"[!] Input file does not exist: {input_file}")
        sys.exit(1)

    parse_file(input_file, output_stem)


if __name__ == "__main__":
    main()