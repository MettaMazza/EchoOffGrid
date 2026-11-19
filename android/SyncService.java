package dev.echooffgrid.mobile;

import android.app.*;
import android.content.Intent;
import android.os.IBinder;

public class SyncService extends Service {
    private static final String CHANNEL = "paired-library";
    private android.net.nsd.NsdManager.RegistrationListener discovery;
    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL,
                "Paired device sync",NotificationManager.IMPORTANCE_LOW));
        Intent open = new Intent(this,Main.class);
        PendingIntent tap = PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this,CHANNEL)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("EchoOffGrid")
                .setContentText("Ready to sync with your paired Mac")
                .setContentIntent(tap).setOngoing(true).build();
        startForeground(1,notice);
        discovery=Bonjour.advertise(this);
    }
    @Override public int onStartCommand(Intent intent,int flags,int id) {
        new Thread(() -> {
            try {Main.launch(getApplicationContext());}
            catch(Exception error) {
                android.util.Log.e("EchoOffGrid","Could not start paired sync",error);
                stopSelf(id);
            }
        }).start();
        return START_STICKY;
    }
    @Override public void onDestroy(){
        if(discovery!=null)try{getSystemService(android.net.nsd.NsdManager.class).unregisterService(discovery);}catch(IllegalArgumentException ignored){}
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) {return null;}
}
