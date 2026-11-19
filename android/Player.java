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
    boolean fullscreen;
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
            File file=LocalMedia.find(this,getIntent().getData());
            LinearLayout box=new LinearLayout(this);
            box.setFitsSystemWindows(true);box.setOrientation(LinearLayout.VERTICAL);
            TextView title=new TextView(this);title.setText(file.getName());box.addView(title);
            SurfaceView surface=new SurfaceView(this);
            box.addView(surface,new LinearLayout.LayoutParams(-1,0,1));
            SeekBar seek=new SeekBar(this);seek.setMax(1000);box.addView(seek);
            Button toggle=new Button(this);toggle.setText("Pause");box.addView(toggle);
            wideButton=new Button(this);wideButton.setText("Watch in fullscreen");box.addView(wideButton);
            wideButton.setOnClickListener(v->{setWide(!fullscreen);wideButton.setText(fullscreen?"Exit fullscreen":"Watch in fullscreen");});
            setContentView(box);
            engine=new LibVLC(this, new java.util.ArrayList<>(java.util.Arrays.asList("--vout=android_display","--no-video-title-show")));player=new MediaPlayer(engine);
            player.setEventListener(event -> {
                if(event.type == MediaPlayer.Event.EncounteredError || event.type == MediaPlayer.Event.Playing ||
                   event.type == MediaPlayer.Event.EndReached || event.type == MediaPlayer.Event.Paused)
                    android.util.Log.i("EchoMovie","VLC event "+event.type+" position "+player.getTime());
            });
            player.getVLCVout().setVideoView(surface);
            player.getVLCVout().attachViews();
            surface.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->player.getVLCVout().setWindowSize(r-l,b-t));
            org.videolan.libvlc.Media media=new org.videolan.libvlc.Media(engine,Uri.fromFile(file));
            player.setMedia(media);media.release();
            surface.getHolder().addCallback(new SurfaceHolder.Callback() {
                public void surfaceCreated(SurfaceHolder holder){player.play();}
                public void surfaceChanged(SurfaceHolder holder,int format,int w,int h){}
                public void surfaceDestroyed(SurfaceHolder holder){}
            });
            if(surface.getHolder().getSurface().isValid()) player.play();
            toggle.setOnClickListener(v->{if(player.isPlaying()){player.pause();toggle.setText("Play");}else{player.play();toggle.setText("Pause");}});
            seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
                public void onStartTrackingTouch(SeekBar s){}
                public void onStopTrackingTouch(SeekBar s){if(player.getLength()>0)player.setTime(player.getLength()*s.getProgress()/1000);}
                public void onProgressChanged(SeekBar s,int v,boolean user){}
            });
            timer.post(new Runnable(){public void run(){
                if(player!=null && player.getLength()>0 && !seek.isPressed())seek.setProgress((int)(player.getTime()*1000/player.getLength()));
                timer.postDelayed(this,500);
            }});
        }catch(Exception error) {
            android.util.Log.e("EchoOffGrid","Opening local movie",error);
            Toast.makeText(this,"Could not open local video",Toast.LENGTH_LONG).show();
            finish();
        }
    }
    @Override protected void onPause(){if(player!=null && player.isPlaying())player.pause();super.onPause();}
    @Override protected void onDestroy(){
        timer.removeCallbacksAndMessages(null);
        if(player!=null){player.stop();player.getVLCVout().detachViews();player.release();player=null;}
        if(engine!=null)engine.release();
        super.onDestroy();
    }
}
