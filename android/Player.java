package dev.echooffgrid.mobile;
import android.app.Activity;
import android.os.*;
import android.net.Uri;
import android.view.*;
import android.widget.*;
import org.videolan.libvlc.LibVLC;
import org.videolan.libvlc.MediaPlayer;
import java.io.File;

public class Player extends Activity {
    boolean fullscreen, requestedPip;
    long startAt,lastReport;
    boolean series,ended;
    void reportPosition(boolean finish){
        if(!series || player==null || ended || startAt>0 || player.getLength()<=0)return;
        ended=finish;
        Main.seriesPosition(getIntent().getData(),finish?player.getLength():player.getTime(),player.getLength(),finish);
    }
    private SurfaceView video;
    private LinearLayout layout;
    private boolean pipSupported(){return getPackageManager().hasSystemFeature(android.content.pm.PackageManager.FEATURE_PICTURE_IN_PICTURE);}
    private android.app.PictureInPictureParams pipParams(){
        android.app.PictureInPictureParams.Builder params=new android.app.PictureInPictureParams.Builder();
        if(android.os.Build.VERSION.SDK_INT>=31)params.setAutoEnterEnabled(player!=null && player.isPlaying());
        return params.build();
    }
    private void pip(){if(pipSupported() && player!=null && player.isPlaying() && !isInPictureInPictureMode())enterPictureInPictureMode(pipParams());}
    @Override protected void onUserLeaveHint(){super.onUserLeaveHint();pip();}
    @Override public void onPictureInPictureModeChanged(boolean small,android.content.res.Configuration config){
        super.onPictureInPictureModeChanged(small,config);
        for(int n=0;n<layout.getChildCount();n++)if(layout.getChildAt(n)!=video)
            layout.getChildAt(n).setVisibility(small?View.GONE:View.VISIBLE);
    }
    void setWide(boolean wide) {
        fullscreen = wide;
        getWindow().getDecorView().setSystemUiVisibility(wide ? View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY : 0);
        setRequestedOrientation(wide ? android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE :
            android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
    }
    @Override public void onBackPressed() {
        if(fullscreen){wideButton.setText("Watch in fullscreen");setWide(false);} else super.onBackPressed();
    }
    Button wideButton;
    MediaPlayer player;
    LibVLC engine;
    final Handler timer=new Handler(Looper.getMainLooper());
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try {
            series="1".equals(getIntent().getData().getQueryParameter("series"));
            requestedPip="1".equals(getIntent().getData().getQueryParameter("pip"));
            String offset=getIntent().getData().getQueryParameter("at");
            if(offset!=null && offset.matches("[0-9]{1,12}"))startAt=Long.parseLong(offset);
            File file=LocalMedia.find(this,getIntent().getData());
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            LinearLayout box=new LinearLayout(this);
            layout=box;box.setFitsSystemWindows(true);box.setOrientation(LinearLayout.VERTICAL);
            TextView title=new TextView(this);title.setText(file.getName());box.addView(title);
            SurfaceView surface=new SurfaceView(this);video=surface;
            box.addView(surface,new LinearLayout.LayoutParams(-1,0,1));
            SeekBar seek=new SeekBar(this);seek.setMax(1000);box.addView(seek);
            Button toggle=new Button(this);toggle.setText("Pause");box.addView(toggle);
            wideButton=new Button(this);wideButton.setText("Watch in fullscreen");box.addView(wideButton);
            wideButton.setOnClickListener(v->{setWide(!fullscreen);wideButton.setText(fullscreen?"Exit fullscreen":"Watch in fullscreen");});
            if(pipSupported()){
                Button small=new Button(this);small.setText("Picture in picture");small.setOnClickListener(v->pip());box.addView(small);
            }
            setContentView(box);
            engine=new LibVLC(this, new java.util.ArrayList<>(java.util.Arrays.asList("--vout=android_display","--no-video-title-show")));player=new MediaPlayer(engine);
            player.setEventListener(event -> {
                if(event.type==MediaPlayer.Event.Playing){if(startAt>0){player.setTime(startAt);startAt=0;}if(requestedPip){requestedPip=false;pip();}}
                if(series && event.type==MediaPlayer.Event.EndReached){reportPosition(true);finish();}
                if(event.type==MediaPlayer.Event.Paused)reportPosition(false);
                if(pipSupported() && (event.type==MediaPlayer.Event.Playing || event.type==MediaPlayer.Event.Paused))setPictureInPictureParams(pipParams());
                if(event.type == MediaPlayer.Event.EncounteredError || event.type == MediaPlayer.Event.Playing ||
                   event.type == MediaPlayer.Event.EndReached || event.type == MediaPlayer.Event.Paused)
                    android.util.Log.i("EchoMovie","VLC event "+event.type+" position "+player.getTime());
            });
            player.getVLCVout().setVideoView(surface);
            player.getVLCVout().addCallback(new org.videolan.libvlc.interfaces.IVLCVout.Callback(){
                public void onSurfacesCreated(org.videolan.libvlc.interfaces.IVLCVout output){if(player!=null)player.play();}
                public void onSurfacesDestroyed(org.videolan.libvlc.interfaces.IVLCVout output){}
            });
            surface.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->player.getVLCVout().setWindowSize(r-l,b-t));
            org.videolan.libvlc.Media media=new org.videolan.libvlc.Media(engine,Uri.fromFile(file));
            player.setMedia(media);media.release();
            player.getVLCVout().attachViews();
            timer.postDelayed(()->{
                if(player==null || !hasWindowFocus() || player.getPlayerState()!=org.videolan.libvlc.interfaces.IMedia.State.Opening)return;
                player.stop();
                org.videolan.libvlc.Media fallback=new org.videolan.libvlc.Media(engine,Uri.fromFile(file));
                fallback.setHWDecoderEnabled(false,false);
                player.setMedia(fallback);fallback.release();player.play();
            },6000);
            toggle.setOnClickListener(v->{if(player.isPlaying()){player.pause();toggle.setText("Play");}else{player.play();toggle.setText("Pause");}});
            seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
                public void onStartTrackingTouch(SeekBar s){}
                public void onStopTrackingTouch(SeekBar s){if(player.getLength()>0)player.setTime(player.getLength()*s.getProgress()/1000);}
                public void onProgressChanged(SeekBar s,int v,boolean user){}
            });
            timer.post(new Runnable(){public void run(){
                if(player!=null && player.getLength()>0 && !seek.isPressed())seek.setProgress((int)(player.getTime()*1000/player.getLength()));
                if(player!=null && player.isPlaying() && SystemClock.elapsedRealtime()-lastReport>3000){reportPosition(false);lastReport=SystemClock.elapsedRealtime();}
                timer.postDelayed(this,500);
            }});
        }catch(Exception error) {
            android.util.Log.e("EchoOffGrid","Opening local movie",error);
            Toast.makeText(this,"Could not open local video",Toast.LENGTH_LONG).show();
            finish();
        }
    }
    @Override protected void onStop(){if(player!=null && player.isPlaying())player.pause();super.onStop();}
    @Override protected void onDestroy(){
        reportPosition(false);timer.removeCallbacksAndMessages(null);
        if(player!=null){player.stop();player.getVLCVout().detachViews();player.release();player=null;}
        if(engine!=null)engine.release();
        super.onDestroy();
    }
}
