package dev.echooffgrid.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.VpnService;

/** Restore only a previously enabled tunnel with an existing Android grant. */
public final class RestoreVpn extends BroadcastReceiver {
    static boolean wanted(Context context) {
        return context.getSharedPreferences("vpn", Context.MODE_PRIVATE).getBoolean("wanted", false);
    }

    static void restore(Context context) {
        if (PhoneVpn.enabled || !wanted(context) || VpnService.prepare(context) != null) return;
        try {
            context.startForegroundService(new Intent(context, PhoneVpn.class).setAction(PhoneVpn.RESTORE));
        } catch (IllegalStateException | SecurityException unavailable) {
            android.util.Log.w("EchoVpn", "Android deferred VPN restoration until the next app launch");
        }
    }

    @Override public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()) ||
                Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) restore(context);
    }
}
