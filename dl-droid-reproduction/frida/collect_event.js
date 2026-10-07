'use strict';

Java.perform(function () {

    console.log('[+] DL-Droid event collector started');

    function emit(type, data) {
        const event = {
            timestamp: Date.now(),
            type: type
        };

        for (const key in data) {
            event[key] = data[key];
        }

        console.log('[DL_EVENT] ' + JSON.stringify(event));
    }

    function hookMethod(className, methodName) {

        try {
            const Cls = Java.use(className);
            const method = Cls[methodName];

            if (typeof method === 'undefined') {
                console.log(
                    '[-] Method not found: ' +
                    className + '->' + methodName
                );
                return;
            }

            const overloads = method.overloads;

            console.log(
                '[+] Found ' +
                className +
                '->' +
                methodName +
                ' (' +
                overloads.length +
                ' overloads)'
            );

            for (let i = 0; i < overloads.length; i++) {

                const overload = overloads[i];

                overload.implementation = function () {

                    console.log(
                        '[+] Called ' +
                        className +
                        '->' +
                        methodName
                    );

                    emit('api', {
                        class: className,
                        method: methodName
                    });

                    return overload.call(this, ...arguments);
                };
            }

            console.log(
                '[+] Successfully hooked ' +
                className +
                '->' +
                methodName
            );

        } catch (e) {

            console.log(
                '[-] Could not hook ' +
                className +
                '->' +
                methodName +
                ': ' +
                e
            );
        }
    }


    // ============================================================
    // Telephony
    // ============================================================

    hookMethod(
        'android.telephony.TelephonyManager',
        'getDeviceId'
    );

    hookMethod(
        'android.telephony.TelephonyManager',
        'getSubscriberId'
    );

    hookMethod(
        'android.telephony.TelephonyManager',
        'getLine1Number'
    );

    hookMethod(
        'android.telephony.TelephonyManager',
        'getSimSerialNumber'
    );


    // ============================================================
    // Network / Wi-Fi
    // ============================================================

    hookMethod(
        'android.net.wifi.WifiManager',
        'getConnectionInfo'
    );

    hookMethod(
        'android.net.NetworkInfo',
        'getState'
    );


    // ============================================================
    // Package manager
    // ============================================================

    hookMethod(
        'android.content.pm.PackageManager',
        'checkPermission'
    );


    // ============================================================
    // Context
    // ============================================================

    hookMethod(
        'android.content.ContextWrapper',
        'bindService'
    );

    hookMethod(
        'android.content.ContextWrapper',
        'unbindService'
    );


    // ============================================================
    // File / cryptography
    // ============================================================

    hookMethod(
        'java.security.MessageDigest',
        'getInstance'
    );

    hookMethod(
        'java.io.FileOutputStream',
        'write'
    );

    hookMethod(
        'java.io.File',
        'exists'
    );


    // ============================================================
    // SMS
    // ============================================================

    hookMethod(
        'android.telephony.SmsManager',
        'sendTextMessage'
    );

    console.log('[+] DL-Droid event collector initialization complete');
});