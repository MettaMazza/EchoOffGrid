package dev.echooffgrid.checks;
import android.app.*;
import android.os.Bundle;
import android.content.Intent;
import android.view.*;
import android.webkit.*;
import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import java.util.regex.*;

public class Checks extends Instrumentation {
    WebView web;
    String origin, cookie;
    Bundle results=new Bundle();
    private boolean intelOnly, historyOnly, govOnly, privateCheck, gamesOnly, mediaOnly, bridgeOnly;
    private String filmId;
    @Override public void onCreate(Bundle args) {super.onCreate(args);intelOnly=args!=null && "1".equals(args.getString("intel"));historyOnly=args!=null && "1".equals(args.getString("history"));govOnly=args!=null && "1".equals(args.getString("opengov"));bridgeOnly=args!=null && "1".equals(args.getString("bridge"));mediaOnly=args!=null && "1".equals(args.getString("media"));filmId=args==null?null:args.getString("film");gamesOnly=args!=null && "1".equals(args.getString("games"));privateCheck=args!=null && "1".equals(args.getString("private"));start();}
    WebView locate(View view) {
        if (view instanceof WebView) return (WebView)view;
        if (view instanceof ViewGroup) {
            ViewGroup g=(ViewGroup)view;
            for(int i=0;i<g.getChildCount();i++){WebView w=locate(g.getChildAt(i));if(w!=null)return w;}
        }
        return null;
    }
    void historyScreenshot(String name) throws Exception {
        CountDownLatch painted=new CountDownLatch(1);
        runOnMainSync(()->web.postVisualStateCallback(0,new WebView.VisualStateCallback(){
            public void onComplete(long id){web.postOnAnimation(()->web.postOnAnimation(painted::countDown));}
        }));
        if(!painted.await(5,TimeUnit.SECONDS))throw new IOException("Timed out waiting for rendered timeline");
        Thread.sleep(350);
        try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),name+".png"))){
            android.graphics.Bitmap screen=getUiAutomation().takeScreenshot();
            if(screen==null)throw new IOException("Screen capture unavailable");
            try{screen.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);}finally{screen.recycle();}
        }
    }
    String get(String path, String expected) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(origin+path).openConnection();
        c.setRequestProperty("Cookie",cookie);
        c.setConnectTimeout(10000);c.setReadTimeout(40000);
        try (InputStream in=c.getInputStream()) {
            byte[] b=new byte[8192];ByteArrayOutputStream out=new ByteArrayOutputStream();
            for(int n;(n=in.read(b))!=-1 && out.size()<2000000;) out.write(b,0,n);
            String body=out.toString("UTF-8");
            if (!body.contains(expected)) throw new IOException("Missing content for "+path);
            return body;
        } finally {c.disconnect();}
    }
    void check(String route,String expected) {
        try { get(route,expected);results.putString(route,"PASS"); }
        catch(Exception e){results.putString(route,e.toString());}
    }
    String js(String script) throws Exception {
        CountDownLatch latch=new CountDownLatch(1);
        String[] value={null};
        runOnMainSync(()->web.evaluateJavascript(script,r->{value[0]=r;latch.countDown();}));
        if(!latch.await(10,TimeUnit.SECONDS)) throw new IOException("WebView script timed out: "+script.substring(0,Math.min(95,script.length())));
        return value[0];
    }
    void navigate(String path) throws Exception {
        String target=origin+path;
        runOnMainSync(()->web.loadUrl(target));
        for(int n=0;n<300;n++){
            boolean[] ready={false};
            runOnMainSync(()->ready[0]=target.equals(web.getUrl()) && web.getProgress()==100);
            if(ready[0] && "true".equals(js("!!document.querySelector('main')")))return;
            Thread.sleep(100);
        }
        throw new IOException("Could not open "+path);
    }
    void puzzleCheck() throws Exception {
        navigate("/library/games");
        org.json.JSONArray boards=new org.json.JSONArray(js("Array.from(document.querySelectorAll('a[href*=play]'),a=>a.href)"));
        int ready=0;
        for(int i=0;!gamesOnly && i<boards.length();i++){
            navigate(boards.getString(i).substring(origin.length()));
            for(int j=0;j<60;j++){
                if("true".equals(js("(()=>{const f=document.querySelector('.puzzle-frame');return !!f && location.href==="+org.json.JSONObject.quote(boards.getString(i))+" && !!f.contentDocument?.querySelector('canvas')?.onmousedown && f.contentDocument.querySelector('#puzzle').style.display!=='none'})()"))){ready++;break;}
                Thread.sleep(100);
            }
        }
        if(!gamesOnly)results.putString("Playable puzzle boards",ready+"/"+boards.length());
        navigate("/library/games");
        runOnMainSync(()->web.loadUrl(origin+"/library/games?play=net"));Thread.sleep(700);
        boolean loaded=false;
        for(int n=0;n<120;n++){
            if("true".equals(js("(()=>{let d=document.querySelector('.puzzle-frame')?.contentDocument;return !!d?.querySelector('#puzzlecanvas') && d.querySelector('#puzzle').style.display!=='none' && !!d.querySelector('#puzzlecanvas').onmousedown})()"))){loaded=true;break;}
            Thread.sleep(100);
        }
        results.putString("Net board loaded",String.valueOf(loaded));if(!loaded)return;
        js("(()=>{let f=document.querySelector('.puzzle-frame'),c=f.contentDocument.querySelector('canvas');c.scrollIntoView({block:'center',behavior:'instant'});return true;})()");
        Thread.sleep(250);
        String point=js("(()=>{let f=document.querySelector('.puzzle-frame'),c=f.contentDocument.querySelector('canvas'),r=c.getBoundingClientRect(),b=f.getBoundingClientRect();window.beforeMove=c.toDataURL();return [(b.left+r.left+r.width*.48)*devicePixelRatio,(b.top+r.top+r.height*.48)*devicePixelRatio,r.width<=f.clientWidth+1,document.elementFromPoint(b.left+r.left+r.width*.48,b.top+r.top+r.height*.48)?.tagName]})()");
        org.json.JSONArray pos=new org.json.JSONArray(point);
        results.putString("touch target",pos.optString(3));
        results.putString("board fits phone",String.valueOf(pos.getBoolean(2)));
        int[] loc=new int[2];runOnMainSync(()->web.getLocationOnScreen(loc));
        long time=android.os.SystemClock.uptimeMillis();
        for(int action:new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_UP}){
            MotionEvent event=MotionEvent.obtain(time,android.os.SystemClock.uptimeMillis(),action,(float)pos.getDouble(0),(float)pos.getDouble(1),0);
            event.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);runOnMainSync(()->web.dispatchTouchEvent(event));event.recycle();
        }
        Thread.sleep(400);
        results.putString("touch changes board",js("(()=>{let c=document.querySelector('.puzzle-frame')?.contentDocument?.querySelector('canvas');return typeof window.beforeMove==='string' && !!c && c.toDataURL()!==window.beforeMove;})()"));
    }
    void mediaChecks() throws Exception {
        navigate("/library");
        js("document.querySelector('.rail.watch .item').scrollIntoView()");
        for(int i=0;i<60;i++){
            if("true".equals(js("document.querySelector('.rail.watch img').naturalWidth>0")))break;
            Thread.sleep(150);
        }
        results.putString("library poster",js("document.querySelector('.rail.watch img').naturalWidth>0"));
        js("(()=>{let i=document.querySelector('.rail.watch .item');i.scrollIntoView();i.dispatchEvent(new PointerEvent('pointerover',{bubbles:true,pointerType:'mouse'}));})()");
        boolean decoded=false;
        for(int n=0;n<20;n++){
            if("true".equals(js("(()=>{let v=document.querySelector('.rail.watch .item video');return !!v && v.currentTime>0 && v.readyState>=2 && v.style.visibility==='visible'})()"))){decoded=true;break;}
            Thread.sleep(100);
        }
        results.putString("decoded hover preview",String.valueOf(decoded));
        navigate("/library/watch/Big%20Buck%20Bunny.mp4");
        results.putString("player uses local poster",js("document.querySelector('main video').poster.startsWith(location.origin+'/poster/')"));
        results.putString("video duration",js("document.querySelector('main video').duration"));
        results.putString("Native player controls",js("document.querySelector('main video').controls && !document.querySelector('.video-fullscreen')"));
        results.putString("Up next carousel",js("!!document.querySelector('.up-next .carousel .item')"));
        String next=js("document.querySelector('.up-next').dataset.next");
        if(!next.equals("\"\"")){
            js("(()=>{let t=document.querySelector('#video-autoplay');if(!t.checked)t.click();document.querySelector('main video').dispatchEvent(new Event('ended'));})()");
            boolean moved=false;
            for(int i=0;i<100;i++){
                if("true".equals(js("location.pathname==="+next+" && document.querySelector('main video')?.currentTime>0"))){moved=true;break;}
                Thread.sleep(150);
            }
            results.putString("Autoplay next local video",String.valueOf(moved));
            js("document.cookie='echo_autoplay=0; Path=/; Max-Age=31536000; SameSite=Strict'");
        }
        for(String shelf:new String[]{"watch","shows","listen","books","software","pictures","games","guides","maps"}){
            navigate("/library/"+shelf);
            results.putString("Browse grid "+shelf,js("!document.querySelector('main .carousel') && !!document.querySelector('.category-grid')"));
        }
        Intent vlc=new Intent().setClassName("dev.echooffgrid.mobile","dev.echooffgrid.mobile.Player");
        vlc.setData(android.net.Uri.parse(origin+"/player/shows/Caminandes%2001%20-%20Llama%20Drama.ogv"));
        vlc.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Activity playerActivity=startActivitySync(vlc);
        try {
            java.lang.reflect.Field field=playerActivity.getClass().getDeclaredField("player");
            field.setAccessible(true);
            Object nativePlayer=field.get(playerActivity);
            boolean playing=false;
            Object media=nativePlayer == null ? null : nativePlayer.getClass().getMethod("getMedia").invoke(nativePlayer);
            for(int n=0;n<150 && nativePlayer!=null;n++){
                Object stats=media.getClass().getMethod("getStats").invoke(media);
                if(stats!=null && stats.getClass().getField("displayedPictures").getInt(stats)>1){playing=true;break;}
                if((Long)nativePlayer.getClass().getMethod("getTime").invoke(nativePlayer)>0){playing=true;break;}
                Thread.sleep(100);
            }
            if(media!=null)media.getClass().getMethod("release").invoke(media);
            results.putString("local VLC Ogg playback",String.valueOf(playing));
        } finally {runOnMainSync(()->playerActivity.finish());}
        navigate("/library");
    }
    String postPrivate(String fields) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(origin+"/private-browser").openConnection();
        c.setRequestProperty("Cookie",cookie);c.setRequestMethod("POST");c.setDoOutput(true);
        c.setConnectTimeout(5000);c.setReadTimeout(45000);
        try(OutputStream out=c.getOutputStream()){out.write(fields.getBytes("UTF-8"));}
        try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] buf=new byte[8192];int n;
            while((n=in.read(buf))!=-1)out.write(buf,0,n);
            return out.toString("UTF-8");
        }finally{c.disconnect();}
    }
    android.view.accessibility.AccessibilityNodeInfo findNode(android.view.accessibility.AccessibilityNodeInfo n,String label,boolean byClass){
        if(n==null)return null;
        String text=String.valueOf(byClass?n.getClassName():n.getText());
        boolean pageTitle = !label.equals("DuckDuckGo") || "android.widget.TextView".contentEquals(n.getClassName());
        if(pageTitle && (byClass?text.equals(label):text.toLowerCase(java.util.Locale.ROOT).contains(label.toLowerCase(java.util.Locale.ROOT)) && (label.length()>3 || text.equalsIgnoreCase(label))))return n;
        for(int i=0;i<n.getChildCount();i++){
            android.view.accessibility.AccessibilityNodeInfo found=findNode(n.getChild(i),label,byClass);
            if(found!=null)return found;
        }
        return null;
    }
    android.view.accessibility.AccessibilityNodeInfo awaitNode(String label,boolean byClass)throws Exception{
        for(int n=0;n<140;n++){
            android.view.accessibility.AccessibilityNodeInfo found=findNode(getUiAutomation().getRootInActiveWindow(),label,byClass);
            if(found!=null)return found;
            Thread.sleep(350);
        }
        throw new IOException("Native browser did not display "+label);
    }
    void echoLiteBridge() throws Exception {
        navigate("/library");
        js("document.querySelector('a[href=\"/echolite\"]').click()");
        waitForPackage("dev.echolite.android");
        results.putString("EchoLite launched from Library","PASS");
        long now=android.os.SystemClock.uptimeMillis();
        for(int action:new int[]{KeyEvent.ACTION_DOWN,KeyEvent.ACTION_UP})
            getUiAutomation().injectInputEvent(new KeyEvent(now,now,action,KeyEvent.KEYCODE_BACK,0),true);
        waitForPackage("dev.echooffgrid.mobile");
        results.putString("Back from EchoLite",js("location.pathname==='/library'"));
    }
    void waitForPackage(String name) throws Exception {
        for(int i=0;i<100;i++){
            android.view.accessibility.AccessibilityNodeInfo window=getUiAutomation().getRootInActiveWindow();
            if(window!=null && name.contentEquals(String.valueOf(window.getPackageName())))return;
            Thread.sleep(170);
        }
        throw new IOException("Expected foreground app "+name);
    }
    void privateReview() throws Exception {
        String page=get("/private-browser","Exit location");
        Matcher match=Pattern.compile("data-token=\"([^\"]+)\"").matcher(page);
        if(!match.find())throw new IOException("No token");
        String fields="token="+match.group(1);
        try{
            postPrivate(fields+"&action=connect&country=gb");
            String state="";
            for(int i=0;i<100;i++){
                state=get("/private-status","status");
                if(state.contains("Tor connected")||state.contains("failed"))break;
                Thread.sleep(1000);
            }
            results.putString("Tor status",state);
            if(state.contains("Tor connected")){
                navigate("/private-browser");
                org.json.JSONArray pos=new org.json.JSONArray(js("(()=>{let a=document.querySelector('#native-browser-launch');a.scrollIntoView({block:'center',behavior:'instant'});let r=a.getBoundingClientRect();return [(r.left+r.width/2)*devicePixelRatio,(r.top+r.height/2)*devicePixelRatio]})()"));
                int[] loc=new int[2];runOnMainSync(()->web.getLocationOnScreen(loc));
                float x=(float)pos.getDouble(0)+loc[0],y=(float)pos.getDouble(1)+loc[1];
                long now=android.os.SystemClock.uptimeMillis();
                sendPointerSync(MotionEvent.obtain(now,now,MotionEvent.ACTION_DOWN,x,y,0));
                sendPointerSync(MotionEvent.obtain(now,now+60,MotionEvent.ACTION_UP,x,y,0));
                awaitNode("DuckDuckGo",false);
                results.putString("Private homepage","DuckDuckGo");
                android.view.accessibility.AccessibilityNodeInfo field=awaitNode("android.widget.EditText",true);
                Bundle value=new Bundle();
                value.putCharSequence(android.view.accessibility.AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,"https://check.torproject.org/");
                field.performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_SET_TEXT,value);
                awaitNode("Go",false).performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK);
                awaitNode("Congratulations",false);
                results.putString("Native Tor exit check","PASS");
                awaitNode("‹ Back",false).performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK);
                awaitNode("DuckDuckGo",false);
                results.putString("Native navigation and Back","PASS");
                awaitNode("Done",false).performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK);
            }
        }finally{postPrivate(fields+"&action=disconnect");}
    }
    @Override public void onStart() {
        try{

            ActivityMonitor monitor=addMonitor("dev.echooffgrid.mobile.Main",null,false);
            try(android.os.ParcelFileDescriptor command=getUiAutomation().executeShellCommand("am start -n dev.echooffgrid.mobile/.Main");
                InputStream in=new android.os.ParcelFileDescriptor.AutoCloseInputStream(command)){while(in.read()!=-1){}}
            Activity app=monitor.waitForActivityWithTimeout(20000);
            removeMonitor(monitor);
            if(app==null)throw new IOException("The phone did not foreground EchoOffGrid within 20 seconds");
            for(int n=0;n<300 && cookie==null;n++){
                runOnMainSync(()->{
                    web=locate(app.getWindow().getDecorView());
                    if(web!=null && web.getUrl()!=null && web.getUrl().startsWith("http://127.0.0.1:")){
                        origin=android.net.Uri.parse(web.getUrl()).getAuthority();
                        origin="http://"+origin;
                        cookie=android.webkit.CookieManager.getInstance().getCookie(origin);
                    }
                });
                Thread.sleep(100);
            }
            if(cookie==null) throw new IOException("Local dashboard did not open");
            if(intelOnly){
                navigate("/openintel?region=finland&view=sample");
                for(int i=0;i<100 && !"true".equals(js("!!document.querySelector('.intel-result')"));i++)Thread.sleep(100);
                if(!"true".equals(js("!!document.querySelector('.intel-result') && document.documentElement.scrollWidth<=innerWidth+1")))throw new IOException("Sample observations or responsive layout failed");
                js("document.querySelector('.intel-result').click()");
                if(!"true".equals(js("document.querySelector('#intel-detail').textContent.includes('OFFLINE SAMPLE')")))throw new IOException("Selection did not open");
                for(int i=0;i<120 && !"true".equals(js("document.querySelector('#intel-map').contentDocument.body.dataset.mapReady==='true'"));i++)Thread.sleep(100);
                if(!"true".equals(js("document.querySelector('#intel-map').contentDocument.body.dataset.mapReady==='true'")))throw new IOException("Offline map failed to render");
                historyScreenshot("openintel-mobile");
                get("/openintel/data?region=finland&view=sample","Fintraffic");
                results.putString("OpenIntel","PASS · local samples, selection and responsive view");
                finish(Activity.RESULT_OK,results);return;
            }
            if(historyOnly){
                navigate("/history");
                if(!"true".equals(js("document.querySelectorAll('.h-period').length===10")))throw new IOException("Missing timeline");
                historyScreenshot("history-layout");
                navigate("/history?from=1450&to=1459");
                js("window.zoomTest=history.length;document.querySelector('a.h-period[href*=\"from=1453\"]').click()");
                for(int i=0;i<60 && !"true".equals(js("location.search.includes('from=1453') && document.activeElement?.id==='history-entries'"));i++)Thread.sleep(100);
                String atYear=js("location.search.includes('from=1453') && window.zoomTest===history.length && !!document.querySelector('.h-entry') && document.querySelector('#history-entries').getBoundingClientRect().top<innerHeight/3");
                if(!"true".equals(atYear))throw new IOException("Zoom did not reveal the entries in place: "+atYear);
                historyScreenshot("history-year");
                js("document.querySelector('#history-entries + nav a').click()");
                for(int i=0;i<60 && !"true".equals(js("document.querySelectorAll('.h-period').length===10"));i++)Thread.sleep(100);
                if(!"true".equals(js("document.querySelectorAll('.h-period').length===10 && window.zoomTest===history.length")))throw new IOException("Could not return to all eras in one tap");
                js("document.querySelector('input[name=jump]').value='1453';document.querySelector('input[name=jump]').form.requestSubmit()");
                for(int i=0;i<60 && !"true".equals(js("document.activeElement?.id==='history-entries'"));i++)Thread.sleep(100);
                if(!"true".equals(js("document.querySelector('#history-entries h3').textContent.includes('1453') && history.length===window.zoomTest")))throw new IOException("Jump did not show the requested year");
                get("/history?from=1453&to=1453","Constantinople");
                navigate("/history?q=Rapa%20Nui");
                get("/history?q=Rapa%20Nui","Population collapse or resilience?");
                navigate("/history");
                results.putString("History","PASS · era rail, date jump, year, search, evidence comparison");
                finish(Activity.RESULT_OK,results);return;
            }
            if(govOnly){
                navigate("/opengov?source=local&q=Transparency");
                String key=new org.json.JSONArray(js("Array.from(document.querySelectorAll('.gov-card input[name=item],.gov-card a[href]'),e=>e.value||e.pathname.split('/').pop())")).getString(0);
                js("document.querySelector('.gov-card button')?.click()");
                String shelf="";
                for(int n=0;n<60;n++){
                    shelf=get("/library/documents","Lend-Lease Act");
                    if(shelf.contains(key))break;
                    Thread.sleep(500);
                }
                if(!shelf.contains(key))throw new IOException("Downloaded record missing from shelf");
                get("/content-file/"+key,"%PDF-");
                navigate("/content/"+key);
                get("/content/"+key,"kit-document");
                navigate("/opengov?country=CAN");
                get("/opengov?country=CAN","www.canada.ca");
                navigate("/opengov");
                if(!"true".equals(js("document.querySelectorAll('select[name=country] option').length>190")))throw new IOException("Worldwide directory missing");
                results.putString("OpenGov","PASS · search, save, shelf, local PDF");
                finish(Activity.RESULT_OK,results);return;
            }
            if(privateCheck){privateReview();finish(Activity.RESULT_OK,results);return;}
            if(filmId!=null && filmId.matches("[a-f0-9]{64}")){
                navigate("/content/"+filmId);
                js("(()=>{let v=document.querySelector('main video');v.muted=true;v.play().catch(()=>{});return true})()");
                boolean started=false,seeked=false;
                for(int i=0;i<100;i++){
                    if("true".equals(js("(()=>{let v=document.querySelector('main video');return v.currentTime>.3 && v.videoWidth>0})()"))){started=true;break;}
                    Thread.sleep(100);
                }
                if(started){
                    js("(()=>{let v=document.querySelector('main video');v.currentTime=Math.max(0,v.duration-8);return true})()");
                    for(int i=0;i<100;i++){
                        if("true".equals(js("(()=>{let v=document.querySelector('main video');return !v.seeking && v.readyState>=2 && v.currentTime>v.duration-8})()"))){seeked=true;break;}
                        Thread.sleep(100);
                    }
                }
                results.putString("Android offline film playback",String.valueOf(started));
                results.putString("Android seek near end",String.valueOf(seeked));
                finish(Activity.RESULT_OK,results);return;
            }
            if(bridgeOnly){echoLiteBridge();finish(Activity.RESULT_OK,results);return;}
            if(mediaOnly){mediaChecks();finish(Activity.RESULT_OK,results);return;}
            if(gamesOnly){puzzleCheck();finish(Activity.RESULT_OK,results);return;}
            String home=get("/","<h2>Discover</h2>");
            results.putString("home","PASS");
            check("/library","/poster/watch/");
            check("/library/books","Dracula");
            check("/library/listen","Sherlock");
            check("/library/shows","Caminandes");
            check("/library/games","Blackbox");
            check("/library/software","Software");
            String newsroom=get("/news","rail news-grid");
            Matcher article=Pattern.compile("href=\"(/news/[a-zA-Z0-9_-]+)\"").matcher(newsroom);
            if(article.find())check(article.group(1),"Related articles");
            results.putString("/news","PASS");
            check("/archive","Saved sources");
            check("/downloads","Downloads");
            check("/devices","Devices");
            check("/dictionary?q=dog","Canidae");
            check("/atlas/UK.pmtiles","PMTiles");
            check("/atlas/World.pmtiles","PMTiles");
            check("/atlas/vendor/maplibre-gl.js","MapLibre");
            String wiki=get("/wikipedia?q=Aberdeen","/zim/search?");
            Matcher link=Pattern.compile("src=\"(/zim/search[^\"]+)").matcher(wiki);
            if(link.find()){
                String route=link.group(1).replace("&amp;","&");
                check(route,"Aberdeen");
                if(!"PASS".equals(results.getString(route))){Thread.sleep(2000);check(route,"Aberdeen");}
            }
            Matcher token=Pattern.compile("data-token=\"([^\"]+)\"").matcher(home);
            if(!token.find())throw new IOException("Reader token missing");
            HttpURLConnection c=(HttpURLConnection)new URL(origin+"/narrate").openConnection();
            c.setRequestProperty("Cookie",cookie);c.setRequestMethod("POST");c.setDoOutput(true);c.setReadTimeout(90000);
            try(OutputStream o=c.getOutputStream()){o.write(("token="+token.group(1)+"&text=Local+voice+test.").getBytes("UTF-8"));}
            try(DataInputStream i=new DataInputStream(c.getInputStream())){
                results.putString("offline voice",i.readInt()==0x52494646 && c.getContentLength()>1000?"PASS":"Invalid WAV");
            }finally{c.disconnect();}
            navigate("/library/books");
            js("document.querySelector('.import-panel').open=true");
            results.putString("Category import form",js("document.querySelector('.personal-import').action.endsWith('/library/books/import') && !document.querySelector('.personal-import select')"));
            navigate("/");
            results.putString("Discover card bounds",js("Array.from(document.querySelectorAll('.discovery-card')).every(c=>Array.from(c.children).every(x=>x.getBoundingClientRect().right<=c.getBoundingClientRect().right && x.scrollWidth<=x.clientWidth+1))"));
            puzzleCheck();mediaChecks();echoLiteBridge();
        }catch(Throwable t){results.putString("error",t.toString());}
        finish(Activity.RESULT_OK,results);
    }
}
