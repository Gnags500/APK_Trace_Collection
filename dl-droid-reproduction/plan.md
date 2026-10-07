# DL-Droid Reproduction — Implementation Plan

## Goal

Build a local Android dynamic-analysis pipeline inspired by the methodology described in:

Mohammed K. Alzaylaee, Suleiman Y. Yerima, Sakir Sezer, “DL-Droid: Deep learning based android malware detection using real devices”, Computers & Security, 2020.

The eventual goal is to reproduce the paper's feature-generation methodology:

* 300 static Android permission features
* 120 selected dynamic features

  * 97 application-attribute features
  * 23 action/event features
* 420 binary features in total

However, implementation must proceed incrementally. Do NOT invent the missing feature vocabulary. First build and validate the raw data-collection pipeline, then reconstruct the feature vocabulary, then generate the binary feature vector.

---

# Current Environment

Operating system:

Ubuntu/Linux x86_64

User:

dhruba

Home:

/home/dhruba

Android SDK:

/home/dhruba/Android/Sdk

ADB:

/usr/bin/adb

Emulator AVD:

Pixel_4

Emulator ABI:

x86_64

Existing Frida Python environment:

/home/dhruba/frida-env

Existing Frida installation is already working.

Frida version:

17.18.0

frida-tools:

14.10.4

Python system version:

3.12.3

Project:

~/dl-droid-reproduction

The project's Python virtual environment is:

~/dl-droid-reproduction/venv

IMPORTANT:

Do NOT reinstall Frida.

Do NOT replace the existing ~/frida-env.

Do NOT install frida-tools into the project venv unless there is a specific technical reason later.

Use:

~/frida-env

for Frida-related Python/CLI operations.

Use:

~/dl-droid-reproduction/venv

for the UI crawler, data processing, JSON/CSV processing, etc.

---

# Current Project Tree

Currently the project contains approximately:

dl-droid-reproduction/
├── apk/
│   └── Magic_Eraser_v2.24.2_(273)_Mod.apk
├── crawler/
│   └── ui_explorer.py
├── frida/
│   ├── api_monitor.js
│   ├── collect_event.js
│   └── parse_events.py
├── extractor/
│   ├── permissions.py
│   └── package_info.py
├── features/
├── results/
├── logs/
└── venv/

Do not delete or overwrite the existing crawler/extractor files unless explicitly required.

---

# Important Safety / Testing Rule

The APK currently present is:

Magic_Eraser_v2.24.2_(273)_Mod.apk

The filename indicates that it is a modified APK.

Do NOT automatically install or execute it merely because it exists in the directory.

First validate the entire pipeline using a benign APK that is known to be safe and preferably controlled by the researcher.

The initial milestone is proving:

APK
→ install
→ launch
→ UI observation
→ Frida instrumentation
→ raw runtime events
→ permissions
→ JSON/CSV output

Only after that should unknown samples be introduced, and those should remain isolated in the emulator.

---

# PHASE 1 — Environment Validation

Before modifying anything, inspect:

1. ADB
2. emulator
3. frida-server
4. existing Frida Python environment
5. Android SDK build tools
6. project Python environment

Commands to validate:

```
adb devices

~/frida-env/bin/frida-ps -U | head

~/frida-env/bin/python --version

python --version

find ~/Android/Sdk/build-tools -name aapt -type f
```

Do not reinstall components that are already working.

If something fails, stop and report the exact failure before changing the environment.

---

# PHASE 2 — APK Package Identification

Before installing an APK, extract:

* package name
* versionCode
* versionName

Use Android SDK's aapt.

Example:

```
~/Android/Sdk/build-tools/<VERSION>/aapt dump badging <APK>
```

Do not assume the package name from the filename.

Store package metadata in:

```
results/package_info.txt
```

The existing:

```
extractor/package_info.py
```

may be used for installed applications, but APK metadata should also be obtainable before installation.

---

# PHASE 3 — Controlled APK Installation

Once a benign test APK has been selected:

```
adb install -r <APK>
```

Verify:

```
adb shell pm list packages
```

Then launch:

```
adb shell monkey -p <PACKAGE> 1
```

Verify the current application:

```
adb shell dumpsys activity activities
```

or through uiautomator2.

Do not proceed if installation or launch fails.

---

# PHASE 4 — Verify UI Crawler Independently

The existing crawler:

```
crawler/ui_explorer.py
```

is a stateful UI exploration component.

Run it independently first.

It should:

* connect to emulator
* identify current package/activity
* dump UI hierarchy
* explore reachable UI states
* record state transitions
* optionally save screenshots
* recover from external packages/dialogs
* avoid uncontrolled text/media input during initial testing

Initial testing should use conservative options such as:

```
--no-input
--no-pick
```

Do not assume that this crawler is already equivalent to DroidBot or the exact DL-Droid input-generation methodology.

It is our experimental stateful input-generation component.

---

# PHASE 5 — Verify Frida Independently

The existing Frida setup has already been validated manually.

Continue using:

```
~/frida-env/bin/frida
```

and:

```
~/frida-env/bin/frida-ps
```

The Android-side frida-server is already running.

First test the existing:

```
frida/api_monitor.js
```

against the benign application.

Then test:

```
frida/collect_event.js
```

The objective is to prove that Frida can observe Java API calls.

Do not claim complete API coverage.

The current hooks are only a prototype based on API examples discussed in the DL-Droid paper.

---

# PHASE 6 — Fix/Improve Frida Event Collection

The current collector should produce structured events rather than relying only on human-readable console output.

Desired event format:

```
{
  "timestamp": 1234567890,
  "type": "api",
  "class": "android.telephony.TelephonyManager",
  "method": "getDeviceId"
}
```

Output should eventually be captured in:

```
logs/frida_raw.log
```

and parsed into:

```
results/raw_events.json
```

The parser:

```
frida/parse_events.py
```

should convert the raw Frida output into valid JSON.

Important:

The collector must handle overloaded Java methods safely under Frida 17.x.

Test this explicitly.

If:

```
overload.apply(this, arguments)
```

is unreliable in the installed Frida version, replace it with a safe implementation that preserves the correct overload invocation.

Do not silently swallow hook failures.

Record which hooks succeeded and which failed.

---

# PHASE 7 — Correct Analysis Ordering

The final controller must NOT launch the application first and attach Frida afterward.

That can miss initialization-time API calls.

Preferred ordering:

```
Start Frida instrumentation
      ↓
spawn/attach target application
      ↓
resume application
      ↓
begin UI exploration
      ↓
collect runtime events
      ↓
stop instrumentation
      ↓
parse events
```

The exact Frida CLI/API mechanism should be selected based on what works reliably with Frida 17.18.0.

Do not implement this blindly.

First validate manually.

---

# PHASE 8 — Build the Automated Controller

Create:

```
run_analysis.py
```

The controller should eventually orchestrate:

1. environment validation
2. APK metadata extraction
3. APK installation
4. package information collection
5. permission extraction
6. Frida instrumentation
7. application launch/spawn
8. UI exploration
9. event collection
10. Frida shutdown
11. event parsing
12. result organization

It should produce:

```
results/
    package_info.txt
    permissions.txt
    ui_graph.json
    raw_events.json

logs/
    frida_raw.log
```

The controller must:

* use absolute paths where appropriate
* return non-zero exit codes on fatal failures
* clearly log every stage
* avoid deleting previous results automatically
* create timestamped experiment directories eventually
* handle Ctrl+C cleanly
* terminate Frida cleanly
* never leave uncontrolled background processes

---

# PHASE 9 — Separate Raw Data from Feature Extraction

Do NOT immediately convert everything into a 420-dimensional vector.

First preserve raw observations.

Raw layer:

```
UI graph
Frida API events
action/event observations
requested permissions
package metadata
```

Feature layer:

```
feature name
feature type
observed/not observed
0/1 value
```

This separation is important for reproducibility and debugging.

---

# PHASE 10 — Permission Extraction

The paper uses 300 Android permission features.

The existing:

```
extractor/permissions.py
```

is only a prototype.

Do NOT assume its current small list is the complete DL-Droid permission vocabulary.

First make the extractor reliably produce:

```
permission_name
present = 0/1
```

for a supplied vocabulary.

Eventually we need a canonical permission feature schema.

For example:

```
permission.READ_SMS
permission.SEND_SMS
permission.RECEIVE_SMS
...
```

But do not invent the remaining feature vocabulary.

The exact 300-feature vocabulary must be reconstructed from reliable sources/data.

---

# PHASE 11 — Dynamic Feature Extraction

The DL-Droid paper describes 178 dynamic features originally obtained from DynaLog.

These were ranked using Information Gain and the top 120 selected.

The 120 selected dynamic features consist of:

* 97 application-attribute features
* 23 actions/events features

Examples of dynamic API features reported in the paper include:

```
TelephonyManager->getDeviceId
TelephonyManager->getSubscriberId
TelephonyManager->getLine1Number
TelephonyManager->getSimSerialNumber
WifiManager->getConnectionInfo
Context->bindService
Context->unbindService
PackageManager->checkPermission
NetworkInfo->getState
FileOutputStream->write
File->exists
MessageDigest->getInstance
SmsManager->sendTextMessage
HttpPost-><init>
TimerTask-><init>
```

Examples of action/event features include:

```
action.SMS_RECEIVED
action.USER_PRESENT
action.PHONE_STATE
action.PACKAGE_ADDED
action.NEW_OUTGOING_CALL
action.MOUNT_UNMOUNT_FILESYSTEMS
```

These are examples only.

Do NOT treat them as the complete vocabulary.

---

# PHASE 12 — Action/Event Monitoring

Frida Java method hooks alone cannot provide all Android broadcast/action events.

Implement a separate mechanism for detecting relevant Android actions/events.

Possible approaches:

* Frida hooks around broadcast-related APIs
* application/broadcast receiver observation
* logcat monitoring where appropriate
* Android instrumentation

The implementation should distinguish:

```
API call
intent/action
UI action
system event
```

Do not collapse all of these into one category.

---

# PHASE 13 — Stateful Input Generation

The paper compares stateful DroidBot with stateless Monkey.

Our existing:

```
crawler/ui_explorer.py
```

will serve as the initial stateful exploration engine.

Record:

* UI state
* action taken
* resulting state
* package/activity
* timestamp
* optionally screenshot

Eventually create a normalized event representation such as:

```
{
  "timestamp": ...,
  "type": "ui_action",
  "action": "click",
  "resource_id": "...",
  "text": "...",
  "activity": "..."
}
```

Do not claim that this is identical to DroidBot unless experimentally demonstrated.

---

# PHASE 14 — Experiment Directory Structure

Eventually each experiment should have its own directory.

Preferred structure:

```
results/
    <sample_id>/
        metadata.json
        package_info.txt
        permissions.json
        ui_graph.json
        runtime_events.json
        feature_vector.csv

logs/
    <sample_id>/
        frida.log
        adb.log
        crawler.log
```

This prevents different APK runs from overwriting each other.

---

# PHASE 15 — Feature Schema

Create a formal schema file eventually:

```
features/dl_droid_schema.csv
```

Suggested columns:

```
feature_id
feature_name
feature_type
source
description
```

Example:

```
1,api:TelephonyManager->getDeviceId,api,paper,...
...
permission:android.permission.SEND_SMS,permission,paper,...
```

The schema is the authoritative vocabulary.

Feature vectors must always be generated from the schema.

Never generate columns dynamically based only on what happened during a particular run.

---

# PHASE 16 — Binary Feature Vector

For every sample:

```
feature present → 1
feature absent  → 0
```

Example:

```
api:TelephonyManager->getDeviceId = 1
api:SmsManager->sendTextMessage = 0
permission:SEND_SMS = 1
```

Output:

```
feature_vector.csv
```

with a fixed column order.

Every sample must have exactly the same columns.

Eventually:

```
420 columns
```

but only after the schema has been correctly reconstructed.

---

# PHASE 17 — Validate Feature Extraction

For each experiment generate a report:

```
number of permissions observed
number of unique API calls observed
number of action/events observed
number of dynamic schema features activated
number of permission schema features activated
total active features
```

Also produce:

```
feature_vector.csv
```

and verify:

```
number of columns == schema size
```

and:

```
every feature value ∈ {0,1}
```

---

# PHASE 18 — Reproduce Paper-Style Experiments

Only after the pipeline is stable:

Compare different input-generation strategies.

At minimum:

```
Stateful UI exploration
Stateless Monkey
```

Record:

```
execution time
number of UI states
number of actions
number of unique API features
number of action/event features
feature activation count
```

The paper reports stateful input generation as producing better coverage for some important dynamic features.

Do not assume our crawler will reproduce the exact paper numbers; measure and report our own results.

---

# PHASE 19 — Machine Learning Stage

Only after feature extraction is correct should we implement the classifier.

Separate:

```
data collection
feature extraction
dataset construction
model training
evaluation
```

Do not train a model on the prototype feature vocabulary.

The first ML milestone should be:

```
fixed 420-dimensional feature matrix
```

Then implement the model architecture described in the DL-Droid paper.

---

# Development Rules

1. Work incrementally.

2. After each major phase, run a test.

3. Do not make large untested changes.

4. Do not overwrite raw experiment data.

5. Do not invent missing DL-Droid feature names.

6. Keep raw observations separate from processed features.

7. Use the existing Frida environment:

   ```
   /home/dhruba/frida-env
   ```

8. Do not reinstall Android SDK or Frida because they are already functional.

9. Do not automatically execute unknown APKs.

10. Prefer benign APKs for initial development.

11. Every automated command should have clear logging.

12. Every failure should report the exact command/component that failed.

13. Use Python for orchestration and data processing.

14. Use JavaScript for Frida instrumentation.

15. Keep UI exploration and runtime instrumentation as separate modules.

16. The final controller should be reproducible from a single command.

---

# Immediate Task

Do NOT implement the complete pipeline yet.

First perform:

```
PHASE 1 — Environment Validation
```

Then:

```
PHASE 2 — APK Package Identification
```

Do not install the current modified APK until the package identity is known and the researcher explicitly decides to use it.

After these checks, implement the next phase only.

The agent should report:

* what it checked
* what succeeded
* what failed
* exact files changed
* exact commands used
* expected next step

Do not silently proceed through multiple phases.
