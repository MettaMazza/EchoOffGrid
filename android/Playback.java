package dev.echooffgrid.mobile;

import android.app.*;
import android.content.*;
import android.media.*;
import android.media.session.*;
import android.net.Uri;
import android.os.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Owns both chapter and narration playback independently of the dashboard WebView. */
public final class Playback extends Service {
    static final class Queue {
        final String kind, title, page, token;
        final ArrayList<String> parts=new ArrayList<>();
        final float speed;
        Queue(JSONObject data) {
            kind=data.optString("kind");title=data.optString("title","EchoOffGrid");
            page=data.optString("page");token=data.optString("token");
            speed=rate(data.optDouble("speed",1));
        }
    }
    static Playback current;
    static Queue pending;
    static String error="";
    static float rate(double value){return (float)Math.max(.5,Math.min(2,value));}
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService renderer=Executors.newSingleThreadExecutor();
    private MediaPlayer player;
    private MediaSession session;
    private AudioManager sound;
    private AudioFocusRequest focus;
    private PowerManager.WakeLock wake;
    private Queue queue;
    private int index,generation;
    private long[] lengths;
    private float speed;
    private boolean paused,prepared,resumeAfterFocus;
    private long pendingPosition;
    private final BroadcastReceiver unplug=new BroadcastReceiver(){
        public void onReceive(Context c,Intent i){pause();}
    };
    private static final int NOTICE=51;

    @Override public void onCreate(){
        super.onCreate(); current=this;
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("playback","Audiobooks and read aloud",NotificationManager.IMPORTANCE_LOW));
        sound=getSystemService(AudioManager.class);
        AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
        focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs).setWillPauseWhenDucked(true)
            .setOnAudioFocusChangeListener(change->{
                if(change==AudioManager.AUDIOFOCUS_GAIN && resumeAfterFocus)resume();
                else if(change<0){boolean wasPlaying=!paused;pause();resumeAfterFocus=wasPlaying && change!=AudioManager.AUDIOFOCUS_LOSS;}
            },main).build();
        session=new MediaSession(this,"EchoOffGrid audio");
        session.setCallback(new MediaSession.Callback(){
            public void onPlay(){resume();}
            public void onPause(){pause();}
            public void onStop(){end("");}
            public void onSeekTo(long position){seek(position);}
        });
        session.setActive(true);
        wake=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"EchoOffGrid:playback");
        wake.setReferenceCounted(false);
        registerReceiver(unplug,new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY));
    }
    @Override public int onStartCommand(Intent i,int flags,int id){
        String action=i==null?"":i.getAction();
        if("pause".equals(action)){pause();return START_NOT_STICKY;}
        if("resume".equals(action)){resume();return START_NOT_STICKY;}
        if("stop".equals(action)){end("");return START_NOT_STICKY;}
        Queue next=pending;pending=null;
        if(next==null || next.parts.isEmpty()){end("");return START_NOT_STICKY;}
        queue=next;index=0;paused=false;resumeAfterFocus=false;speed=next.speed;error="";
        lengths=new long[next.parts.size()];
        if(reading())for(int n=0;n<lengths.length;n++)lengths[n]=Math.max(500,next.parts.get(n).length()*70L);
        startForeground(NOTICE,notice());
        if(sound.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED){end("Audio focus unavailable");return START_NOT_STICKY;}
        wake.acquire();load(0,0);
        return START_NOT_STICKY;
    }
    private boolean reading(){return queue!=null && "read".equals(queue.kind);}
    private long offset(){long t=0;if(reading())for(int n=0;n<index;n++)t+=lengths[n];return t;}
    private long duration(){if(!reading())return lengths[index];long t=0;for(long v:lengths)t+=v;return t;}
    private long position(){return offset()+(prepared?player.getCurrentPosition():pendingPosition);}
    private void releasePlayer(){prepared=false;if(player!=null){player.release();player=null;}}
    private void load(int n,long at){
        int run=++generation;releasePlayer();index=n;pendingPosition=at;
        if(!reading()){
            try{prepare(LocalMedia.find(this,Uri.parse(queue.parts.get(n))),run);}
            catch(Exception e){end("Could not open this audiobook chapter");}
        }else{
            String text=queue.parts.get(n),token=queue.token;
            renderer.execute(()->{
                File wav=null;
                try{
                    wav=render(text,token);
                    File ready=wav;
                    main.post(()->{try{if(run==generation)prepare(ready,run);}
                        catch(Exception e){if(run==generation)end("Could not play the offline voice");}finally{ready.delete();}});
                }catch(Exception e){if(wav!=null)wav.delete(); main.post(()->{if(run==generation)end("Could not prepare the offline voice");});}
            });
        }
        publish();
    }
    private File render(String text,String token)throws Exception {
        HttpURLConnection c=Main.connection(this,"/narrate"); c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/x-www-form-urlencoded");
        File file=File.createTempFile("reading-",".wav",getCacheDir());
        try{
            try(OutputStream out=c.getOutputStream()){out.write(("token="+URLEncoder.encode(token,"UTF-8")+"&text="+URLEncoder.encode(text,"UTF-8")).getBytes(StandardCharsets.UTF_8));}
            try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(file)){byte[] b=new byte[16384];int k;while((k=in.read(b))!=-1)out.write(b,0,k);}
            return file;
        }catch(Exception e){file.delete();throw e;}finally{c.disconnect();}
    }
    private void prepare(File f,int run)throws IOException{
        player=new MediaPlayer();
        player.setAudioAttributes(focus.getAudioAttributes());
        try(FileInputStream in=new FileInputStream(f)){player.setDataSource(in.getFD());}
        player.setOnPreparedListener(p->{
            if(run!=generation)return;
            prepared=true;lengths[index]=p.getDuration();
            if(pendingPosition>0)p.seekTo(Math.min(pendingPosition,lengths[index]-1),MediaPlayer.SEEK_CLOSEST);
            if(!paused){p.setPlaybackParams(p.getPlaybackParams().setSpeed(speed));p.start();}
            publish();
        });
        player.setOnCompletionListener(p->{if(run==generation){if(index+1<lengths.length)load(index+1,0);else end("");}});
        player.setOnErrorListener((p,what,extra)->{if(run==generation)end("Playback failed");return true;});
        player.prepareAsync();
    }
    void seek(long ms){
        if(queue==null)return;
        ms=Math.max(0,Math.min(ms,Math.max(0,duration()-1)));int n=0;
        if(reading())while(n+1<lengths.length && ms>=lengths[n])ms-=lengths[n++];
        if(reading() && n!=index){load(n,ms);return;}
        pendingPosition=ms;if(prepared)player.seekTo(ms,MediaPlayer.SEEK_CLOSEST);publish();
    }
    void setSpeed(double value){speed=rate(value);if(prepared && !paused)player.setPlaybackParams(player.getPlaybackParams().setSpeed(speed));publish();}
    void pause(){if(queue==null)return;resumeAfterFocus=false;paused=true;if(prepared)player.pause();if(wake.isHeld())wake.release();publish();}
    void resume(){if(queue==null || sound.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED)return;
        resumeAfterFocus=false;paused=false;if(!wake.isHeld())wake.acquire();if(prepared){player.setPlaybackParams(player.getPlaybackParams().setSpeed(speed));player.start();}publish();}
    private PendingIntent command(String action){return PendingIntent.getService(this,0,new Intent(this,Playback.class).setAction(action),PendingIntent.FLAG_IMMUTABLE);}
    private Notification notice(){
        return new Notification.Builder(this,"playback").setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle(queue.title).setContentText(reading()?"Read aloud":"Audiobook")
            .setContentIntent(PendingIntent.getActivity(this,0,new Intent(this,Main.class),PendingIntent.FLAG_IMMUTABLE))
            .addAction(paused?android.R.drawable.ic_media_play:android.R.drawable.ic_media_pause,paused?"Resume":"Pause",command(paused?"resume":"pause"))
            .addAction(android.R.drawable.ic_menu_close_clear_cancel,"Stop",command("stop"))
            .setStyle(new Notification.MediaStyle().setMediaSession(session.getSessionToken()).setShowActionsInCompactView(0,1)).setOnlyAlertOnce(true).setOngoing(!paused).build();
    }
    private void publish(){
        if(queue==null)return;
        long actions=PlaybackState.ACTION_PLAY|PlaybackState.ACTION_PAUSE|PlaybackState.ACTION_PLAY_PAUSE|PlaybackState.ACTION_STOP|PlaybackState.ACTION_SEEK_TO;
        session.setPlaybackState(new PlaybackState.Builder().setActions(actions).setState(paused?PlaybackState.STATE_PAUSED:
            prepared?PlaybackState.STATE_PLAYING:PlaybackState.STATE_BUFFERING,position(),paused?0:speed).build());
        session.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,queue.title)
            .putLong(MediaMetadata.METADATA_KEY_DURATION,duration()).build());
        getSystemService(NotificationManager.class).notify(NOTICE,notice());
    }
    static JSONObject snapshot()throws JSONException{
        JSONObject s=new JSONObject().put("error",error);Playback p=current;
        if(p==null || p.queue==null)return s;
        return s.put("kind",p.queue.kind).put("page",p.queue.page).put("paused",p.paused).put("ready",p.prepared)
            .put("position",p.position()).put("duration",p.duration()).put("part",p.index);
    }
    void end(String message){error=message;generation++;releasePlayer();queue=null;stopSelf();}
    @Override public void onDestroy(){
        generation++;releasePlayer();queue=null;current=null;renderer.shutdownNow();
        if(wake.isHeld())wake.release();sound.abandonAudioFocusRequest(focus);
        unregisterReceiver(unplug);session.release();stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();
    }
    @Override public IBinder onBind(Intent i){return null;}
}
