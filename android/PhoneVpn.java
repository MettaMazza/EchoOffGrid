package dev.echooffgrid.mobile;

import android.app.*;
import android.content.*;
import android.net.VpnService;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import hev.htproxy.TProxyService;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.regex.*;

/** The service owns the routes and the Tor process independently of the workstation Activity. */
public final class PhoneVpn extends VpnService {
    static volatile String state = "Off";
    static volatile boolean enabled;
    static final String CONNECT = "dev.echooffgrid.mobile.CONNECT_VPN";
    static final String RESTORE = "dev.echooffgrid.mobile.RESTORE_VPN";
    static final String DISCONNECT = "dev.echooffgrid.mobile.DISCONNECT_VPN";
    private static final String CHANNEL = "phone-vpn";
    private ParcelFileDescriptor tunnel;
    private TorUplink uplink;
    private Process tor;
    private File folder;
    private int generation;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private static final Pattern LISTENER = Pattern.compile("Opened Socks listener connection .* on 127\\.0\\.0\\.1:(\\d+)");
    private static final Pattern PROGRESS = Pattern.compile("Bootstrapped (\\d+)%");

    @Override public void onCreate() {
        super.onCreate();
        folder = new File(getFilesDir(), "vpn");
        folder.mkdirs();
        getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel(CHANNEL, "Phone VPN", NotificationManager.IMPORTANCE_LOW));
    }

    private Notification notification() {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, Main.class), PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL).setSmallIcon(getResources().getIdentifier("vpn_status","drawable",getPackageName())).setOnlyAlertOnce(true)
                .setContentTitle("EchoOffGrid phone VPN").setContentText(state).setContentIntent(open).setOngoing(true).build();
    }

    private void status(String text) {
        state = text;
        android.util.Log.i("EchoVpn",text);
        getSystemService(NotificationManager.class).notify(42, notification());
    }

    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent != null && DISCONNECT.equals(intent.getAction())) {
            getSharedPreferences("vpn",0).edit().putBoolean("wanted",false).commit();
            disconnect();
            return START_NOT_STICKY;
        }
        // Android can request an always-on restart after an explicit disconnect.
        // Honour the saved switch unless the user just tapped Connect in EchoOffGrid.
        if ((intent == null || !CONNECT.equals(intent.getAction())) &&
                getSharedPreferences("vpn",0).contains("wanted") && !RestoreVpn.wanted(this)) {
            stopSelf(id);
            return START_NOT_STICKY;
        }
        if (enabled) return START_STICKY;
        state = "Connecting";
        startForeground(42, notification());
        enabled = true;
        String country = intent == null ? null : intent.getStringExtra("country");
        if (country != null && country.matches("[a-z]{2}|")) getSharedPreferences("vpn",0).edit().putString("country",country).apply();
        try {
            tunnel = new Builder().setSession("EchoOffGrid · Tor").setMtu(1500)
                    .addAddress("198.18.0.1", 32).addAddress("fd19:ec40::1", 128)
                    .addRoute("0.0.0.0", 0).addRoute("::", 0).addDnsServer("198.18.0.2").establish();
            if (tunnel == null) throw new IOException("VPN permission unavailable");
            getSharedPreferences("vpn",0).edit().putBoolean("wanted",true).commit();
            uplink = new TorUplink(this);
            launchTor();
        } catch (Exception failure) { disconnect(); return START_NOT_STICKY; }
        return START_STICKY;
    }

    private void launchTor() {
        final int run = ++generation;
        try {
            File data = new File(folder, "state");
            data.mkdirs();
            File config = new File(folder, "torrc");
            String country = getSharedPreferences("vpn",0).getString("country","");
            String settings = "DataDirectory "+data+"\nSocksPort 127.0.0.1:auto\nSocksPort unix:"+new File(folder,"s")+
                    "\nHTTPSProxy 127.0.0.1:"+uplink.listener.getLocalPort()+"\nHTTPSProxyAuthenticator "+uplink.credential+
                    "\nClientRejectInternalAddresses 1\nSafeLogging 1\nLog notice stdout\n__OwningControllerProcess "+android.os.Process.myPid()+"\n";
            if (!country.isEmpty()) {
                long build = getPackageManager().getPackageInfo(getPackageName(), 0).lastUpdateTime;
                File geo = new File(getFilesDir(),"runtime-"+build+"/lib/python3.14/site-packages/vendor/private-browser/data");
                settings += "GeoIPFile "+new File(geo,"geoip")+"\nGeoIPv6File "+new File(geo,"geoip6")+"\nExitNodes {"+country+"}\nStrictNodes 1\n";
            }
            Files.write(config.toPath(),settings.getBytes(StandardCharsets.UTF_8));
            tor = new ProcessBuilder(new File(getApplicationInfo().nativeLibraryDir,"libtor.so").toString(),"-f",config.toString())
                    .redirectErrorStream(true).start();
            final Process process = tor;
            new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line=reader.readLine()) != null) {
                        Matcher listener = LISTENER.matcher(line);
                        Matcher progress = PROGRESS.matcher(line);
                        if (listener.find()) {
                            int port = Integer.parseInt(listener.group(1));
                            handler.post(() -> { if (generation==run) startForwarding(port); });
                        } else if (progress.find()) {
                            int pct = Integer.parseInt(progress.group(1));
                            handler.post(() -> { if (generation==run) status(pct==100 && TProxyService.TProxyIsRunning() ?
                                    "Connected over Tor" : "Connecting · "+pct+"%"); });
                        }
                    }
                } catch (IOException ignored) { }
                handler.post(() -> { if (generation==run) reconnect(); });
            }, "vpn-bootstrap").start();
        } catch (Exception failure) { reconnect(); }
    }

    private void startForwarding(int port) {
        try {
            File config = new File(folder,"tunnel.yml");
            String settings = "tunnel:\n  mtu: 1500\nsocks5:\n  address: 127.0.0.1\n  port: "+port+
                    "\nmapdns:\n  address: 198.18.0.2\n  port: 53\n  network: 100.64.0.0\n  netmask: 255.192.0.0\n  cache-size: 10000\n";
            Files.write(config.toPath(),settings.getBytes(StandardCharsets.UTF_8));
            if (!TProxyService.TProxyStartService(config.toString(),tunnel.getFd())) throw new IOException();
            final int run = generation;
            handler.postDelayed(new Runnable() {
                public void run() {
                    if (generation != run) return;
                    if (!TProxyService.TProxyIsRunning()) { reconnect(); return; }
                    handler.postDelayed(this, 2000);
                }
            }, 2000);
        } catch (Exception failure) { reconnect(); }
    }

    private void reconnect() {
        generation++;
        if (tor != null) tor.destroyForcibly();
        TProxyService.TProxyStopService();
        status("Reconnecting · traffic blocked");
        handler.postDelayed(this::launchTor, 3000);
    }

    @Override public void onRevoke() { handler.post(() -> {
        getSharedPreferences("vpn",0).edit().putBoolean("wanted",false).commit();
        disconnect();
    }); }
    private void disconnect() {
        releaseTunnel();
        stopSelf();
    }

    private void releaseTunnel() {
        if (!enabled) return;
        generation++;
        handler.removeCallbacksAndMessages(null);
        if (tor!=null) tor.destroyForcibly();
        if (uplink!=null) uplink.close();
        TProxyService.TProxyStopService();
        if (tunnel!=null) try { tunnel.close(); } catch(IOException ignored) { }
        enabled=false;
        state="Off";
        stopForeground(STOP_FOREGROUND_REMOVE);
    }

    @Override public void onDestroy() {
        releaseTunnel();
        super.onDestroy();
    }
}
