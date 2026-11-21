package dev.echooffgrid.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.net.Uri;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.webkit.*;
import android.widget.*;
import androidx.webkit.*;
import java.io.File;

public final class PrivateBrowser extends Activity {
    private WebView browser;
    private EditText address;
    private TextView status;
    private File profile;
    private boolean ready;
    private static final String BLOCK_RTC="for(const n of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport']){try{Object.defineProperty(globalThis,n,{value:undefined,configurable:false})}catch{}}";
    private static void remove(File f){
        File[] children=f.listFiles();
        if(children!=null)for(File child:children) remove(child);
        f.delete();
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        File[] old=getDataDir().listFiles(f->f.isDirectory() && f.getName().matches("app_webview_echo_private_[0-9]+"));
        if(old!=null)for(File dir:old)remove(dir);
        String suffix="echo_private_"+android.os.SystemClock.elapsedRealtime();
        WebView.setDataDirectorySuffix(suffix);
        profile=new File(getDataDir(),"app_webview_"+suffix);
        LinearLayout pane=new LinearLayout(this);pane.setOrientation(LinearLayout.VERTICAL);
        pane.setBackgroundColor(0xff14181c);pane.setFitsSystemWindows(true);
        LinearLayout controls=new LinearLayout(this);
        Button back=new Button(this);back.setText("‹ Back");back.setOnClickListener(v->onBackPressed());
        Button done=new Button(this);done.setText("Done");done.setOnClickListener(v->finish());
        address=new EditText(this);address.setSingleLine();address.setHint("HTTPS address");
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        address.setImeOptions(EditorInfo.IME_ACTION_GO);
        address.setSelectAllOnFocus(true);
        address.setOnEditorActionListener((v,action,event)->{open();return true;});
        Button go=new Button(this);go.setText("Go");go.setOnClickListener(v->open());
        controls.addView(back);controls.addView(address,new LinearLayout.LayoutParams(0,-2,1));controls.addView(go);controls.addView(done);
        pane.addView(controls);status=new TextView(this);pane.addView(status);setContentView(pane);
        Button capture=new Button(this);capture.setText("Capture page to case");
        capture.setOnClickListener(v->capturePage());pane.addView(capture);
        int port=getIntent().getIntExtra("port",0);
        if(port<1024||port>65535||!WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)){
            status.setText("Private browsing needs an up-to-date Android System WebView.");return;
        }
        browser=new WebView(this);pane.addView(browser,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings prefs=browser.getSettings();
        prefs.setAllowContentAccess(false);prefs.setAllowFileAccess(false);prefs.setGeolocationEnabled(false);
        prefs.setSafeBrowsingEnabled(false);prefs.setCacheMode(WebSettings.LOAD_NO_CACHE);
        prefs.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if(WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)){
            WebViewCompat.addDocumentStartJavaScript(browser,BLOCK_RTC,java.util.Collections.singleton("*"));
            prefs.setJavaScriptEnabled(true);
        }
        CookieManager.getInstance().setAcceptThirdPartyCookies(browser,false);
        browser.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return !"https".equals(r.getUrl().getScheme());}
            @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap image){address.setText(url);status.setText("Loading over Tor…");}
            @Override public void onPageFinished(WebView v,String url){status.setText(v.getTitle());}
            @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame())status.setText("Could not load this page over Tor.");}
        });
        status.setText("Connecting browser to Tor…");
        ProxyConfig proxy=new ProxyConfig.Builder().addProxyRule("http://127.0.0.1:"+port).removeImplicitRules().build();
        ProxyController.getInstance().setProxyOverride(proxy,getMainExecutor(),()->{
            if(isFinishing()||isDestroyed())return;
            String destination=getIntent().getStringExtra("url");
            ready=true;address.setText(destination==null ? "https://duckduckgo.com/" : destination);open();
        });
    }
    private void capturePage(){
        if(!ready || browser.getUrl()==null || !browser.getUrl().startsWith("https://"))return;
        final String url=browser.getUrl(),title=browser.getTitle();
        final String captured=java.time.Instant.now().toString();
        browser.evaluateJavascript("(function(){const html=document.documentElement.outerHTML,text=document.body?.innerText||'';"+
                "return html.length+text.length<=8000000?{html,text}:null})()",raw->{
            try{
                if(!url.equals(browser.getUrl()))throw new java.io.IOException("Page changed. Capture it again.");
                if(raw==null || raw.equals("null"))throw new java.io.IOException("Page too large or unavailable.");
                org.json.JSONObject page=new org.json.JSONObject(raw);
                int w=browser.getWidth(),h=browser.getHeight();
                if(w<=0 || h<=0)throw new java.io.IOException("No visible browser area.");
                float scale=Math.min(1f,1600f/Math.max(w,h));
                android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(Math.max(1,Math.round(w*scale)),
                    Math.max(1,Math.round(h*scale)),android.graphics.Bitmap.Config.ARGB_8888);
                try{
                    android.graphics.Canvas canvas=new android.graphics.Canvas(bitmap);
                    canvas.scale(scale,scale);canvas.translate(-browser.getScrollX(),-browser.getScrollY());
                    browser.draw(canvas);
                    java.io.ByteArrayOutputStream jpg=new java.io.ByteArrayOutputStream();
                    bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG,88,jpg);
                    page.put("viewport",android.util.Base64.encodeToString(jpg.toByteArray(),android.util.Base64.NO_WRAP));
                }finally{bitmap.recycle();}
                page.put("url",url).put("title",title==null?"":title).put("captured",captured);
                byte[] bytes=page.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
                if(bytes.length>15*1024*1024)throw new java.io.IOException("Page exceeds the capture limit.");
                File file=new File(getCacheDir(),"pending-browser-capture.json");
                android.util.AtomicFile target=new android.util.AtomicFile(file);
                java.io.FileOutputStream output=target.startWrite();
                try{output.write(bytes);target.finishWrite(output);}
                catch(java.io.IOException err){target.failWrite(output);throw err;}
                setResult(RESULT_OK);finish();
            }catch(Exception err){status.setText("Capture unavailable. "+err.getMessage());}
        });
    }
    private void open(){
        if(!ready)return;
        String raw=address.getText().toString().trim();Uri url=Uri.parse(raw.contains("://")?raw:"https://"+raw);
        if(!"https".equals(url.getScheme())||url.getHost()==null){status.setText("Enter an HTTPS address.");return;}
        browser.loadUrl(url.toString());browser.requestFocus();
    }
    @Override public void onBackPressed(){if(browser!=null&&browser.canGoBack())browser.goBack();else finish();}
    @Override protected void onDestroy(){
        if(browser!=null){browser.stopLoading();browser.clearHistory();browser.clearCache(true);browser.destroy();}
        super.onDestroy();
        if(isFinishing() && android.app.Application.getProcessName().endsWith(":private")){
            if(profile!=null)remove(profile);
            android.os.Process.killProcess(android.os.Process.myPid());
        }
    }
}
