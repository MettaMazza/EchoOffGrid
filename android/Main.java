package dev.echooffgrid.mobile;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.net.Uri;
import android.webkit.*;
import android.widget.TextView;
import android.widget.Toast;
import java.io.*;
import java.util.UUID;
import java.util.zip.*;

public class Main extends Activity {
    static { System.loadLibrary("workstation"); }
    private static native int start(String home, String storage, String nativeDir, String key);
    private static int port;
    private static final String key = UUID.randomUUID().toString();
    private WebView browser;
    private ValueCallback<Uri[]> picker;
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);
        if(code!=71 || picker==null)return;
        Uri[] files=null;
        if(result==RESULT_OK && data!=null){
            android.content.ClipData clip=data.getClipData();
            if(clip!=null){ files=new Uri[clip.getItemCount()];for(int i=0;i<files.length;i++)files[i]=clip.getItemAt(i).getUri(); }
            else if(data.getData()!=null)files=new Uri[]{data.getData()};
        }
        picker.onReceiveValue(files);picker=null;
    }

    private android.view.View fullVideo;
    private WebChromeClient.CustomViewCallback fullCallback;
    private int previousFlags;
    private int previousOrientation;

    private void exitVideo() {
        if (fullVideo == null) return;
        ((android.view.ViewGroup)fullVideo.getParent()).removeView(fullVideo);
        fullVideo = null;
        getWindow().getDecorView().setSystemUiVisibility(previousFlags);
        setRequestedOrientation(previousOrientation);
        browser.setVisibility(android.view.View.VISIBLE);
        fullCallback.onCustomViewHidden();
        fullCallback = null;
    }

    static int launch(android.content.Context context) throws Exception {
        synchronized (Main.class) {
            if (port != 0) return port;
            long build = context.getPackageManager().getPackageInfo(context.getPackageName(), 0).lastUpdateTime;
            File home = new File(context.getFilesDir(), "runtime-" + build);
            File ready = new File(home, ".ready");
            if (!ready.exists()) {
                try (ZipInputStream zip = new ZipInputStream(context.getAssets().open("runtime.zip"))) {
                    ZipEntry entry;
                    byte[] buffer = new byte[65536];
                    while ((entry = zip.getNextEntry()) != null) {
                        File file = new File(home, entry.getName());
                        if (!file.getCanonicalPath().startsWith(home.getCanonicalPath() + "/"))
                            throw new IOException("Invalid runtime asset");
                        file.getParentFile().mkdirs();
                        try (OutputStream out = new FileOutputStream(file)) {
                            int size;
                            while ((size = zip.read(buffer)) != -1) out.write(buffer, 0, size);
                        }
                    }
                }
                ready.createNewFile();
            }
            File storage = context.getExternalFilesDir(null);
            if (storage == null) throw new IOException("Phone storage unavailable");
            port = start(home.toString(), storage.toString(), context.getApplicationInfo().nativeLibraryDir, key);
            File[] older=context.getFilesDir().listFiles(file -> file.isDirectory() &&
                    file.getName().matches("runtime-[0-9]+") && !file.equals(home));
            if (older != null) for (File file : older) removeOldRuntime(file);
            return port;
        }
    }

    private static void removeOldRuntime(File file) {
        File[] children=file.listFiles();
        if(children!=null) for(File child:children) removeOldRuntime(child);
        if(!file.delete()) android.util.Log.w("EchoOffGrid","Could not remove obsolete runtime asset");
    }

    private void offerHomeIcon() {
        android.content.pm.ShortcutManager manager=getSystemService(android.content.pm.ShortcutManager.class);
        if(manager==null || !manager.isRequestPinShortcutSupported())return;
        if(getPreferences(MODE_PRIVATE).getBoolean("offeredHomeIcon",false))return;
        for(android.content.pm.ShortcutInfo old:manager.getPinnedShortcuts())
            if("workstation".equals(old.getId()))return;
        Intent launch=new Intent(this,Main.class).setAction(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        android.content.pm.ShortcutInfo shortcut=new android.content.pm.ShortcutInfo.Builder(this,"workstation")
                .setShortLabel("EchoOffGrid").setIntent(launch)
                .setIcon(android.graphics.drawable.Icon.createWithResource(this,getApplicationInfo().icon)).build();
        if(manager.requestPinShortcut(shortcut,null))
            getPreferences(MODE_PRIVATE).edit().putBoolean("offeredHomeIcon",true).apply();
    }

    public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView status = new TextView(this);
        status.setPadding(40,100,40,40);
        status.setText("Opening your offline workstation…");
        setContentView(status);
        new Thread(() -> {
            try {
                int active = launch(getApplicationContext());
                runOnUiThread(() -> { if (!isDestroyed()) show(active, state); });
            } catch (Exception e) {
                android.util.Log.e("EchoOffGrid","Startup",e);
                runOnUiThread(() -> status.setText("Could not open EchoOffGrid. " + e.getMessage()));
            }
        }).start();
    }

    private void show(int active, Bundle state) {
        if (new File(getFilesDir(),"paired-device/token").isFile())
            startForegroundService(new Intent(this,SyncService.class));
        String origin = "http://127.0.0.1:" + active;
        browser = new WebView(this);
        browser.setBackgroundColor(0xff14181c);
        browser.getSettings().setJavaScriptEnabled(true);
        browser.getSettings().setDomStorageEnabled(true);
        browser.getSettings().setMediaPlaybackRequiresUserGesture(false);
        browser.getSettings().setAllowFileAccess(false);
        browser.getSettings().setAllowContentAccess(false);
        CookieManager.getInstance().setCookie(origin, "workstation=" + key + "; Path=/; HttpOnly; SameSite=Strict");
        browser.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(picker!=null)picker.onReceiveValue(null);
                picker=callback;
                Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                pick.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try{startActivityForResult(pick,71);}catch(android.content.ActivityNotFoundException e){picker.onReceiveValue(null);picker=null;}
                return true;
            }
            @Override public void onShowCustomView(android.view.View video, CustomViewCallback callback) {
                if (fullVideo != null) { callback.onCustomViewHidden(); return; }
                android.view.ViewGroup decor = (android.view.ViewGroup)getWindow().getDecorView();
                previousFlags = decor.getSystemUiVisibility();
                previousOrientation = getRequestedOrientation();
                fullVideo = video;
                fullCallback = callback;
                browser.setVisibility(android.view.View.INVISIBLE);
                decor.addView(video,new android.widget.FrameLayout.LayoutParams(-1,-1));
                decor.setSystemUiVisibility(android.view.View.SYSTEM_UI_FLAG_FULLSCREEN |
                    android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
                setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
            }
            @Override public void onHideCustomView() { exitVideo(); }
            @Override public android.graphics.Bitmap getDefaultVideoPoster() {
                return android.graphics.Bitmap.createBitmap(1,1,android.graphics.Bitmap.Config.ARGB_8888);
            }
        });
        browser.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri=request.getUrl();
                if (("https".equals(uri.getScheme()) || "http".equals(uri.getScheme())) &&
                    (uri.getPort()!=active || !"127.0.0.1".equals(uri.getHost())))
                    return new WebResourceResponse("text/plain","UTF-8",403,"Offline viewer",java.util.Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
                if (uri.getPort()!=active || !"127.0.0.1".equals(uri.getHost())) return null;
                try {
                    if("POST".equals(request.getMethod()) && uri.getPath().matches("/native-metadata/personal-[a-f0-9]{64}") &&
                        request.getRequestHeaders().entrySet().stream().anyMatch(h -> "X-Echo-Library".equalsIgnoreCase(h.getKey()) && "import".equals(h.getValue()))){
                        FileMetadata.read(Main.this,uri.getLastPathSegment());
                        return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
                    }
                    if (uri.getPath().startsWith("/content-poster/")) return LocalMedia.poster(Main.this,uri);
                    if ("/mobile-pdf".equals(uri.getPath()))
                        return LocalMedia.pdf(Main.this,Uri.parse(uri.getQueryParameter("file")),uri.getQueryParameter("page"));
                    if (!request.isForMainFrame() && (uri.getPath().startsWith("/kit-file/") || uri.getPath().startsWith("/content-file/"))) {
                        boolean pdf=uri.getPath().toLowerCase(java.util.Locale.ROOT).endsWith(".pdf");
                        if (!pdf && uri.getPath().startsWith("/content-file/"))
                            pdf=LocalMedia.find(Main.this,uri).getName().toLowerCase(java.util.Locale.ROOT).endsWith(".pdf");
                        if (pdf) return LocalMedia.pdf(Main.this,uri,null);
                    }
                } catch(Exception e) {
                    android.util.Log.w("EchoOffGrid","Local document unavailable",e);
                }
                return null;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                boolean local = "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost()) && uri.getPort() == active;
                if(request.isForMainFrame() && request.hasGesture() && "https".equals(uri.getScheme()) && view.getUrl()!=null){
                    Uri page=Uri.parse(view.getUrl());
                    if("127.0.0.1".equals(page.getHost()) && page.getPort()==active &&
                       ("/opengov".equals(page.getPath()) || "/opengov/portal".equals(page.getPath()) || "/openintel".equals(page.getPath()))){
                        try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}
                        catch(android.content.ActivityNotFoundException e){Toast.makeText(Main.this,"No web browser installed",Toast.LENGTH_SHORT).show();}
                        return true;
                    }
                }
                if(local && request.isForMainFrame() && "/openintel/camera".equals(uri.getPath())){
                    Uri page = Uri.parse(view.getUrl());
                    if(request.hasGesture() && "/openintel".equals(page.getPath()) && page.getPort()==active)
                        startActivity(new Intent(Main.this,IntelCamera.class));
                    return true;
                }
                if(local && request.isForMainFrame() && "/private-open".equals(uri.getPath())){
                    Uri page=Uri.parse(view.getUrl());
                    if(request.hasGesture() && "/private-browser".equals(page.getPath())){
                        try{int port=Integer.parseInt(uri.getQueryParameter("port"));
                            if(port>=1024 && port<=65535)startActivity(new Intent(Main.this,PrivateBrowser.class).putExtra("port",port));
                        }catch(NumberFormatException ignored){}
                    }
                    return true;
                }
                if(local && request.isForMainFrame() && request.hasGesture() && uri.getPath().matches("/personal-launch/(?:personal-)?[0-9a-f]{64}")){
                    try{
                        File file=LocalMedia.find(Main.this,Uri.parse("/content-file/"+uri.getLastPathSegment()));
                        android.content.pm.PackageInfo info=getPackageManager().getPackageArchiveInfo(file.getPath(),0);
                        if(info==null)throw new IOException("Invalid APK");
                        if(android.os.Build.VERSION.SDK_INT>=33)getPackageManager().getLaunchIntentSenderForPackage(info.packageName).sendIntent(Main.this,0,null,null,null);
                        else {
                            Intent app=getPackageManager().getLaunchIntentForPackage(info.packageName);
                            if(app==null)throw new IOException("App unavailable");
                            startActivity(app);
                        }
                    }catch(Exception e){Toast.makeText(Main.this,"Install the matching app on this device first.",Toast.LENGTH_LONG).show();}
                    return true;
                }
                if(local && request.isForMainFrame() && uri.getPath().matches("/personal-open/(?:personal-)?[0-9a-f]{64}")){
                    Uri file=Uri.parse("content://dev.echooffgrid.mobile.files/"+uri.getLastPathSegment());
                    Intent open=new Intent(Intent.ACTION_VIEW).setDataAndType(file,getContentResolver().getType(file));
                    open.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(open,"Open with"));return true;
                }
                if(local && request.isForMainFrame() && uri.getPath().startsWith("/player/")){
                    startActivity(new Intent(Main.this,Player.class).setData(uri));
                    return true;
                }
                if (local && request.isForMainFrame() && "/echolite".equals(uri.getPath())) {
                    Intent launch = getPackageManager().getLaunchIntentForPackage("dev.echolite.android");
                    if (launch != null) startActivity(launch);
                    else Toast.makeText(Main.this, "Install EchoLite to open its workspace.", Toast.LENGTH_LONG).show();
                    return true;
                }
                return !local;
            }
        });
        android.widget.FrameLayout frame = new android.widget.FrameLayout(this);
        frame.setBackgroundColor(0xff111418);
        if (android.os.Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        frame.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                            insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        frame.addView(browser);
        setContentView(frame);
        frame.requestApplyInsets();
        frame.post(this::offerHomeIcon);
        String path = state == null ? "/" : state.getString("path","/");
        browser.loadUrl(origin + (path.startsWith("/") ? path : "/"));
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        if (browser != null && browser.getUrl() != null) {
            Uri uri = Uri.parse(browser.getUrl());
            state.putString("path", uri.getEncodedPath() + (uri.getEncodedQuery()==null ? "" : "?" + uri.getEncodedQuery()));
        }
    }
    @Override public void onBackPressed() {
        if (fullVideo != null) { exitVideo(); return; }
        if (browser == null) { super.onBackPressed(); return; }
        browser.evaluateJavascript("(() => {const menu=document.querySelector('#section-drawer[open]');if(menu)menu.close();return !!menu})()", result -> {
            if (!"true".equals(result) && !isFinishing() && !isDestroyed()) navigateBack();
        });
    }
    private void navigateBack() {
        if (browser.canGoBack()) browser.goBack();
        else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        exitVideo();
        if (browser != null) browser.destroy();
        super.onDestroy();
    }
}
