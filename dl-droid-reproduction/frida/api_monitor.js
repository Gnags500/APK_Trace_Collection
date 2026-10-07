```javascript
'use strict';

/*
 * Initial DL-Droid-style API monitor.
 *
 * This is intentionally small.
 * We are first proving that our pipeline can observe
 * selected Android Java API calls.
 */

Java.perform(function () {

    console.log('[+] Frida Java instrumentation started');

    function hookMethod(className, methodName) {

        try {
            const Cls = Java.use(className);
            const overloads = Cls[methodName].overloads;

            console.log(
                '[+] Found ' +
                className +
                '->' +
                methodName +
                ' (' +
                overloads.length +
                ' overloads)'
            );

            overloads.forEach(function (overload) {

                overload.implementation = function () {

                    console.log(
                        '[API] ' +
                        className +
                        '->' +
                        methodName
                    );

                    return overload.apply(this, arguments);
                };
            });

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

    hookMethod(
        'android.net.wifi.WifiManager',
        'getConnectionInfo'
    );

    hookMethod(
        'android.content.ContextWrapper',
        'bindService'
    );

    hookMethod(
        'android.content.ContextWrapper',
        'unbindService'
    );

    hookMethod(
        'android.content.pm.PackageManager',
        'checkPermission'
    );

    hookMethod(
        'android.net.NetworkInfo',
        'getState'
    );

    hookMethod(
        'java.security.MessageDigest',
        'getInstance'
    );

    hookMethod(
        'android.telephony.SmsManager',
        'sendTextMessage'
    );

});
```
