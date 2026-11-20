package dev.echooffgrid.mobile;

import android.app.*;
import android.content.*;
import android.os.*;
import java.io.*;
import java.net.HttpURLConnection;

/** Keeps the existing durable download worker alive while the user has active transfers. */
public final class Transfers extends Service {
    private PowerManager.WakeLock wake;
    private volatile boolean closed;
    private volatile int startId;
    private Thread monitor;
    @Override public void onCreate(){
        super.onCreate();
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("transfers","Downloads",NotificationManager.IMPORTANCE_LOW));
        wake=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"EchoOffGrid:downloads");
    }
    @Override public int onStartCommand(Intent intent,int flags,int id){
        startId=id;
        startForeground(52,new Notification.Builder(this,"transfers").setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("EchoOffGrid downloads").setContentText("Saving to your offline library")
            .setContentIntent(PendingIntent.getActivity(this,0,new Intent(this,Main.class),PendingIntent.FLAG_IMMUTABLE)).setOngoing(true).build());
        if(monitor==null){wake.acquire();monitor=new Thread(this::watch,"download-monitor");monitor.start();}
        return START_STICKY;
    }
    private void watch(){
        while(!closed){
            int id=startId;
            try{
                Thread.sleep(5000);
                HttpURLConnection c=Main.connection(this,"/mobile-transfer-count");
                try(BufferedReader in=new BufferedReader(new InputStreamReader(c.getInputStream()))){
                    if(Integer.parseInt(in.readLine())==0 && stopSelfResult(id))return;
                }finally{c.disconnect();}
            }catch(InterruptedException stop){return;}catch(Exception e){android.util.Log.w("EchoTransfers","Checking download worker",e);if(stopSelfResult(id))return;}
        }
    }
    @Override public void onTimeout(int id,int type){stopSelf(id);}
    @Override public void onDestroy(){closed=true;if(monitor!=null)monitor.interrupt();if(wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
