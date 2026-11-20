package dev.echooffgrid.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.net.Uri;
import android.webkit.*;
import java.io.ByteArrayInputStream;
import java.util.Arrays;
import java.util.Collections;

/** Isolated publisher player. It never receives workstation cookies or a native bridge. */
public class IntelCamera extends Activity {
    private WebView web;
    private static boolean initialized;
    public void onCreate(Bundle state) {
        super.onCreate(state);
        String stream=getIntent().getStringExtra("stream");
        if(stream!=null){
            Uri uri=Uri.parse(stream);
            boolean clip="s3-eu-west-1.amazonaws.com".equals(uri.getHost()) && uri.getPath()!=null && uri.getPath().matches("/jamcams\\.tfl\\.gov\\.uk/[0-9.]+\\.mp4");
            boolean live="wzmedia.dot.ca.gov".equals(uri.getHost()) && uri.getPath()!=null && uri.getPath().endsWith(".m3u8");
            if(!"https".equals(uri.getScheme()) || (!clip && !live)){finish();return;}
            android.widget.FrameLayout stage=new android.widget.FrameLayout(this);
            android.widget.VideoView video=new android.widget.VideoView(this);
            stage.addView(video,new android.widget.FrameLayout.LayoutParams(-1,-2,android.view.Gravity.CENTER));
            setContentView(stage);
            android.widget.MediaController controls=new android.widget.MediaController(this);
            controls.setAnchorView(video);video.setMediaController(controls);
            video.setVideoURI(uri);video.start();
            return;
        }
        if(!initialized){ WebView.setDataDirectorySuffix("openintel-camera"); initialized=true; }
        web = new WebView(this);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setCacheMode(WebSettings.LOAD_NO_CACHE);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req) {
                return req.isForMainFrame() || !allowed(req.getUrl());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest req) {
                if(allowed(req.getUrl())) return null;
                return new WebResourceResponse("text/plain","UTF-8",403,"Unavailable",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
            }
        });
        setContentView(web);
        web.loadUrl("https://www.mauirealestate.net/live/embed.html");
    }
    private boolean allowed(Uri uri) {
        String host=uri.getHost();
        if(!"https".equals(uri.getScheme()) || host==null)return false;
        return host.endsWith(".brownrice.com") || Arrays.asList("www.mauirealestate.net","cdn.jsdelivr.net","unpkg.com","code.jquery.com").contains(host);
    }
    @Override public void onDestroy() { if(web!=null)web.destroy(); super.onDestroy(); }
}
