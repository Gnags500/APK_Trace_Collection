'use strict';

/*
 * DL-Droid API event collector — full API call feature set.
 *
 * Covers every API-call feature from DynaLog / DL-Droid:
 *   - Telephony (device identity + operator info)
 *   - Network / Wi-Fi
 *   - Package manager
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
    hookMethod('java.lang.Object',  'getClass');

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

    console.log('[+] DL-Droid full API collector initialisation complete');
});