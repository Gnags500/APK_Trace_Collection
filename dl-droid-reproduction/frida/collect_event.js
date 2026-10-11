'use strict';

/*
 * DL-Droid API event collector — full API call feature set.
 *
 * Covers every API-call feature from DynaLog / DL-Droid:
 *   - Telephony (device identity — legacy + modern API 26+ paths)
 *   - Network / Wi-Fi (legacy NetworkInfo + modern ConnectivityManager)
 *   - Package manager + Context permission checks
 *   - Context (service binding)
 *   - Process execution (Runtime.exec, ProcessBuilder)
 *   - Reflection (Class.getMethod, Object.getClass)
 *   - Cryptography (MessageDigest, Cipher, KeyGenerator)
 *   - File I/O
 *   - Database (SQLiteDatabase)
 *   - Content provider (ContentResolver)
 *   - Location (LocationManager)
 *   - Native library loading (System.loadLibrary)
 *   - Network connection (URL.openConnection, HttpURLConnection)
 *   - URI parsing (Uri.parse)
 *   - SMS (SmsManager)
 *
 * Each hook emits a JSON event on stdout with the prefix [DL_EVENT].
 * parse_events.py reads that prefix to build the feature vector.
 *
 * Intent/broadcast events are NOT handled here — those are captured
 * separately via the broadcast-receiver monitor.
 */

Java.perform(function () {

    console.log('[+] DL-Droid full API collector started');

    // ----------------------------------------------------------------
    // Emit helper — keeps every event in the same shape.
    // ----------------------------------------------------------------

    function emit(type, data) {
        var event = { timestamp: Date.now(), type: type };
        for (var key in data) { event[key] = data[key]; }
        console.log('[DL_EVENT] ' + JSON.stringify(event));
    }

    // ----------------------------------------------------------------
    // hookMethod — hooks every overload of className->methodName.
    // On invocation it emits one 'api' event and then calls through.
    // ----------------------------------------------------------------

    function hookMethod(className, methodName) {
        try {
            var Cls = Java.use(className);
            var method = Cls[methodName];

            if (typeof method === 'undefined') {
                console.log('[-] Not found: ' + className + '->' + methodName);
                return;
            }

            var overloads = method.overloads;

            for (var i = 0; i < overloads.length; i++) {
                (function (overload) {
                    overload.implementation = function () {
                        emit('api', { class: className, method: methodName });
                        return overload.call(this, ...arguments);
                    };
                })(overloads[i]);
            }

            console.log('[+] Hooked ' + className + '->' + methodName
                + ' (' + overloads.length + ' overloads)');

        } catch (e) {
            console.log('[-] Could not hook ' + className + '->' + methodName + ': ' + e);
        }
    }


    // ================================================================
    // TELEPHONY — device identity
    // DL-Droid features: deviceId, SubscriberId, lineNumber,
    //                    SimSerialNumber
    // ================================================================

    hookMethod('android.telephony.TelephonyManager', 'getDeviceId');
    hookMethod('android.telephony.TelephonyManager', 'getSubscriberId');
    hookMethod('android.telephony.TelephonyManager', 'getLine1Number');
    hookMethod('android.telephony.TelephonyManager', 'getSimSerialNumber');

    // ================================================================
    // TELEPHONY — device identity (modern, API 26+)
    //
    // getDeviceId() was deprecated in API 26 and removed in API 29.
    // Apps targeting Android 10+ use getImei()/getMeid() instead, or
    // go through Build.getSerial() / createForSubscriptionId().
    // All four map to the same DL-Droid 'deviceId' feature.
    // ================================================================

    hookMethod('android.telephony.TelephonyManager', 'getImei');
    hookMethod('android.telephony.TelephonyManager', 'getMeid');
    hookMethod('android.telephony.TelephonyManager', 'createForSubscriptionId');
    hookMethod('android.os.Build',                   'getSerial');

    // ================================================================
    // TELEPHONY — operator / SIM info
    // DL-Droid features: NetworkOperator, SimOperator,
    //                    SimCountryIso, SimOperatorNumber
    // ================================================================

    hookMethod('android.telephony.TelephonyManager', 'getNetworkOperatorName');
    hookMethod('android.telephony.TelephonyManager', 'getSimOperator');
    hookMethod('android.telephony.TelephonyManager', 'getSimOperatorName');
    hookMethod('android.telephony.TelephonyManager', 'getSimCountryIso');

    // ================================================================
    // NETWORK / WI-FI
    // DL-Droid features: getConnectionInfo, getState
    // ================================================================

    hookMethod('android.net.wifi.WifiManager',  'getConnectionInfo');
    hookMethod('android.net.NetworkInfo',       'getState');

    // ================================================================
    // NETWORK — modern connectivity (API 29+)
    //
    // NetworkInfo.getState() is deprecated since API 29. Apps now use
    // ConnectivityManager. All three map to the 'getState' feature.
    // ================================================================

    hookMethod('android.net.ConnectivityManager', 'getNetworkCapabilities');
    hookMethod('android.net.ConnectivityManager', 'registerNetworkCallback');
    hookMethod('android.net.ConnectivityManager', 'getActiveNetworkInfo');

    // ================================================================
    // NETWORK — connection / URL
    // DL-Droid features: connect, parse (Uri)
    // ================================================================

    hookMethod('java.net.URL',                      'openConnection');
    hookMethod('java.net.HttpURLConnection',        'connect');
    hookMethod('android.net.Uri',                   'parse');

    // ================================================================
    // PACKAGE MANAGER
    // DL-Droid features: checkPermission, getApplicationInfo
    // ================================================================

    hookMethod('android.content.pm.PackageManager', 'checkPermission');
    hookMethod('android.content.pm.PackageManager', 'getApplicationInfo');

    // ================================================================
    // PERMISSION CHECKS — modern path
    //
    // Many apps call Context.checkSelfPermission() or
    // ContextCompat.checkSelfPermission() rather than
    // PackageManager.checkPermission() directly. All map to
    // the 'checkPermission' feature.
    // ================================================================

    hookMethod('android.content.Context',        'checkSelfPermission');
    hookMethod('android.content.Context',        'checkCallingPermission');
    hookMethod('android.content.ContextWrapper', 'checkSelfPermission');

    // ================================================================
    // CONTEXT — service binding
    // DL-Droid features: bindService, unbindService
    // ================================================================

    hookMethod('android.content.ContextWrapper', 'bindService');
    hookMethod('android.content.ContextWrapper', 'unbindService');

    // ================================================================
    // PROCESS EXECUTION
    // DL-Droid features: runtime.exec, Process (start)
    //
    // These are among the highest-discriminating API features in the
    // DynaLog paper (Table IV shows large before/after sandbox delta).
    // ================================================================

    hookMethod('java.lang.Runtime',         'exec');
    hookMethod('java.lang.ProcessBuilder',  'start');

    // ================================================================
    // REFLECTION
    // DL-Droid features: getMethod (#12 by frequency), getClass (#16)
    //
    // Reflection is heavily used by obfuscated malware to hide API
    // calls from static analysis. Both features have high malware
    // prevalence in DynaLog Table V.
    // ================================================================

    hookMethod('java.lang.Class',   'getMethod');
    hookMethod('java.lang.Class',   'getDeclaredMethod');
    // java.lang.Object->getClass is intentionally NOT hooked.
    // It is called by the JVM itself on virtually every operation,
    // flooding the log with 98%+ noise and making output unusable.

    // ================================================================
    // CRYPTOGRAPHY
    // DL-Droid features: getInstance (#10), digest, initCipher,
    //                    SecretKey
    // ================================================================

    hookMethod('java.security.MessageDigest',    'getInstance');
    hookMethod('java.security.MessageDigest',    'digest');
    hookMethod('javax.crypto.Cipher',            'getInstance');
    hookMethod('javax.crypto.Cipher',            'init');
    hookMethod('javax.crypto.KeyGenerator',      'getInstance');
    hookMethod('javax.crypto.KeyGenerator',      'generateKey');

    // ================================================================
    // FILE I/O
    // DL-Droid features: file write, file exists
    // ================================================================

    hookMethod('java.io.FileOutputStream',  'write');
    hookMethod('java.io.File',              'exists');

    // ================================================================
    // DATABASE
    // DL-Droid feature: openOrCreateDatabase
    // ================================================================

    hookMethod(
        'android.database.sqlite.SQLiteDatabase',
        'openOrCreateDatabase'
    );

    // ================================================================
    // CONTENT PROVIDER
    // DL-Droid feature: ContentResolver (query is the primary method;
    // insert/update/delete round out the picture)
    // ================================================================

    hookMethod('android.content.ContentResolver', 'query');
    hookMethod('android.content.ContentResolver', 'insert');
    hookMethod('android.content.ContentResolver', 'update');
    hookMethod('android.content.ContentResolver', 'delete');

    // ================================================================
    // LOCATION
    // DL-Droid feature: getLastKnownLocation
    // ================================================================

    hookMethod(
        'android.location.LocationManager',
        'getLastKnownLocation'
    );

    // ================================================================
    // NATIVE LIBRARY LOADING
    // DL-Droid feature: LoadLibrary
    //
    // Indicates native code execution — often used to hide malicious
    // behaviour from Java-level analysis.
    // ================================================================

    hookMethod('java.lang.System',  'loadLibrary');
    hookMethod('java.lang.System',  'load');

    // ================================================================
    // SMS
    // DL-Droid feature: sendsms
    // ================================================================

    hookMethod('android.telephony.SmsManager', 'sendTextMessage');
    hookMethod('android.telephony.SmsManager', 'sendMultipartTextMessage');

    // ================================================================
    // INTENT / BROADCAST EVENTS
    // DL-Droid features: 23 broadcast intent actions
    //
    // Hook 1 — registerReceiver: catches what the app REGISTERS to
    //           listen for, even if the broadcast never fires.
    // Hook 2 — onReceive: catches what was actually DELIVERED.
    // Both are needed — registration alone proves intent, delivery
    // proves execution.
    // ================================================================

    // The 23 DL-Droid intent actions we care about.
    var TRACKED_ACTIONS = [
        'android.provider.Telephony.SMS_RECEIVED',
        'android.intent.action.NEW_OUTGOING_CALL',
        'android.intent.action.PHONE_STATE',
        'android.intent.action.BOOT_COMPLETED',
        'android.intent.action.USER_PRESENT',
        'android.net.conn.CONNECTIVITY_CHANGE',
        'android.intent.action.PACKAGE_ADDED',
        'android.intent.action.PACKAGE_REMOVED',
        'android.intent.action.PACKAGE_REPLACED',
        'android.intent.action.PACKAGE_CHANGED',
        'android.intent.action.PACKAGE_RESTARTED',
        'android.intent.action.PACKAGE_INSTALL',
        'android.intent.action.ACTION_POWER_CONNECTED',
        'android.intent.action.ACTION_POWER_DISCONNECTED',
        'android.intent.action.BATTERY_LOW',
        'android.intent.action.BATTERY_OKAY',
        'android.intent.action.BATTERY_CHANGED',
        'android.intent.action.UMS_CONNECTED',
        'android.intent.action.UMS_DISCONNECTED',
        'android.intent.action.SIM_FULL',
        'android.intent.action.SIG_STR',
        'android.intent.action.INPUT_METHOD_CHANGED',
        'android.intent.action.MAIN',
    ];

    var ACTION_SET = {};
    for (var i = 0; i < TRACKED_ACTIONS.length; i++) {
        ACTION_SET[TRACKED_ACTIONS[i]] = true;
    }

    // ----------------------------------------------------------------
    // Hook 1 — Context.registerReceiver()
    // Fires when the app registers a broadcast receiver at runtime.
    // Extract each action from the IntentFilter argument.
    // ----------------------------------------------------------------
    try {
        var ContextWrapper = Java.use('android.content.ContextWrapper');
        var registerOverloads = ContextWrapper.registerReceiver.overloads;

        for (var r = 0; r < registerOverloads.length; r++) {
            (function (overload) {
                overload.implementation = function () {
                    // IntentFilter is always the second argument
                    var filter = arguments[1];
                    if (filter !== null) {
                        try {
                            var count = filter.countActions();
                            for (var a = 0; a < count; a++) {
                                var action = filter.getAction(a);
                                if (action && ACTION_SET[action]) {
                                    emit('intent_registered', { action: action });
                                }
                            }
                        } catch (ex) {
                            // filter iteration failed — skip
                        }
                    }
                    return overload.call(this, ...arguments);
                };
            })(registerOverloads[r]);
        }
        console.log('[+] Hooked ContextWrapper->registerReceiver');
    } catch (e) {
        console.log('[-] Could not hook registerReceiver: ' + e);
    }

    // ----------------------------------------------------------------
    // Hook 2 — BroadcastReceiver.onReceive()
    // Fires when a broadcast is actually delivered to the app.
    // Extract the action from the Intent argument.
    // ----------------------------------------------------------------
    try {
        var BroadcastReceiver = Java.use('android.content.BroadcastReceiver');

        BroadcastReceiver.onReceive.implementation = function (context, intent) {
            if (intent !== null) {
                try {
                    var action = intent.getAction();
                    if (action && ACTION_SET[action]) {
                        emit('intent_received', { action: action });
                    }
                } catch (ex) {
                    // intent.getAction() failed — skip
                }
            }
            return this.onReceive(context, intent);
        };
        console.log('[+] Hooked BroadcastReceiver->onReceive');
    } catch (e) {
        console.log('[-] Could not hook BroadcastReceiver->onReceive: ' + e);
    }

    console.log('[+] DL-Droid full API collector initialisation complete');
});