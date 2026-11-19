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
    @Override public void onDestroy() { web.destroy(); super.onDestroy(); }
}
