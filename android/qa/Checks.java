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
    private boolean captureOnly, shelvesOnly, vpnRegion, geography, trackHistory;
    private int reviewCaptureOwner;
    private boolean exportsOnly, tabsOnly, corpoOnly, casesOnly, visualsOnly, drawerOnly, intelOnly, historyOnly, govOnly, privateCheck, gamesOnly, mediaOnly, bridgeOnly;
    private String backgroundMode, seriesIds, cancelId;
    private String filmId, exportCase;
    private boolean protectedLink;
    @Override public void onCreate(Bundle args) {super.onCreate(args);trackHistory=args!=null && "1".equals(args.getString("tracks"));geography=args!=null && "1".equals(args.getString("geography"));vpnRegion=args!=null && "1".equals(args.getString("vpnRegion"));shelvesOnly=args!=null && "1".equals(args.getString("shelves"));reviewCaptureOwner=args==null?0:Integer.parseInt(args.getString("reviewCapture","0"));captureOnly=args!=null && "1".equals(args.getString("capture"));seriesIds=args==null?null:args.getString("series");cancelId=args==null?null:args.getString("cancel");backgroundMode=args==null?null:args.getString("background");protectedLink=args!=null && "1".equals(args.getString("protectedLink"));exportsOnly=args!=null && "1".equals(args.getString("exports"));tabsOnly=args!=null && "1".equals(args.getString("tabs"));corpoOnly=args!=null && "1".equals(args.getString("corpo"));exportCase=args==null?null:args.getString("exportCase");casesOnly=args!=null && "1".equals(args.getString("cases"));visualsOnly=args!=null && "1".equals(args.getString("visuals"));drawerOnly=args!=null && "1".equals(args.getString("drawer"));intelOnly=args!=null && "1".equals(args.getString("intel"));historyOnly=args!=null && "1".equals(args.getString("history"));govOnly=args!=null && "1".equals(args.getString("opengov"));bridgeOnly=args!=null && "1".equals(args.getString("bridge"));mediaOnly=args!=null && "1".equals(args.getString("media"));filmId=args==null?null:args.getString("film");gamesOnly=args!=null && "1".equals(args.getString("games"));privateCheck=args!=null && "1".equals(args.getString("private"));start();}
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
    void awaitWeb(String condition, int seconds) throws Exception {
        for(int i=0;i<seconds*4;i++){
            if("true".equals(js(condition)))return;
            Thread.sleep(250);
        }
        throw new IOException("Timed out waiting for "+condition+" · "+js("document.querySelector('.phone-vpn-toggle')?.title"));
    }
    void tapVpnSwitch() throws Exception {
        org.json.JSONArray point=new org.json.JSONArray(js("(()=>{let b=document.querySelector('.phone-vpn-toggle');b.scrollIntoView({block:'center'});let r=b.getBoundingClientRect();return [(r.left+r.width/2)*devicePixelRatio,(r.top+r.height/2)*devicePixelRatio]})()"));
        int[] offset=new int[2];
        runOnMainSync(()->web.getLocationOnScreen(offset));
        float x=(float)point.getDouble(0)+offset[0], y=(float)point.getDouble(1)+offset[1];
        long now=android.os.SystemClock.uptimeMillis();
        for(int action:new int[]{0,1}){
            android.view.MotionEvent event=android.view.MotionEvent.obtain(now,android.os.SystemClock.uptimeMillis(),action,x,y,0);
            event.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);
            try{getUiAutomation().injectInputEvent(event,true);}finally{event.recycle();}
        }
    }
    void selectExit(String country) throws Exception {
        js("(()=>{const s=document.querySelector('.private-browser-controls [name=country]');s.value="+org.json.JSONObject.quote(country)+";s.dispatchEvent(new Event('change'));})()");
        awaitWeb("!document.querySelector('.private-browser-controls [name=country]').disabled",15);
    }
    String verifyTorExit(String country) throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL("https://check.torproject.org/api/ip").openConnection();
        connection.setUseCaches(false);
        connection.setRequestProperty("Connection","close");
        connection.setConnectTimeout(25000);connection.setReadTimeout(25000);
        String address;
        try(java.util.Scanner scanner=new java.util.Scanner(connection.getInputStream(),"UTF-8")){
            org.json.JSONObject check=new org.json.JSONObject(scanner.useDelimiter("\\A").next());
            if(!check.getBoolean("IsTor"))throw new IOException("Tor check reported a direct route");
            address=check.getString("IP");
        }finally{connection.disconnect();}
        byte[] raw=java.net.InetAddress.getByName(address).getAddress();
        java.math.BigInteger number=new java.math.BigInteger(1,raw);
        long build=getTargetContext().getPackageManager().getPackageInfo(getTargetContext().getPackageName(),0).lastUpdateTime;
        File geo=new File(getTargetContext().getFilesDir(),"runtime-"+build+"/lib/python3.14/site-packages/vendor/private-browser/data/"+(raw.length==4?"geoip":"geoip6"));
        try(BufferedReader reader=new BufferedReader(new FileReader(geo))){
            for(String line;(line=reader.readLine())!=null;){
                if(line.isEmpty() || line.charAt(0)=='#')continue;
                String[] r=line.split(",",3);
                if(!r[2].equalsIgnoreCase(country))continue;
                java.math.BigInteger lo=raw.length==4?new java.math.BigInteger(r[0]):new java.math.BigInteger(1,java.net.InetAddress.getByName(r[0]).getAddress());
                java.math.BigInteger hi=raw.length==4?new java.math.BigInteger(r[1]):new java.math.BigInteger(1,java.net.InetAddress.getByName(r[1]).getAddress());
                if(number.compareTo(lo)>=0 && number.compareTo(hi)<=0)return "Tor exit verified in "+country;
            }
        }
        throw new IOException("Reported Tor exit did not match the selected region "+country);
    }
    void checkVpnRegion() throws Exception {
        navigate("/private-browser");
        String switches="Array.from(document.querySelectorAll('.phone-vpn-toggle'))";
        awaitWeb(switches+".length===2 && "+switches+".every(b=>b.hasAttribute('aria-checked'))",20);
        boolean initialOn="true".equals(js("document.querySelector('.phone-vpn-toggle').dataset.enabled==='true'"));
        String prior=getTargetContext().getSharedPreferences("vpn",0).getString("country","");
        try{
            selectExit("gb");
            if(!initialOn)tapVpnSwitch();
            for(String country:new String[]{"gb","se"}){
                if(country.equals("se"))selectExit(country);
                awaitWeb(switches+".every(b=>b.textContent==='VPN on' && b.title.endsWith('"+country.toUpperCase(java.util.Locale.ROOT)+"'))",120);
                results.putString("Phone VPN "+country,verifyTorExit(country));
            }
            navigate("/");
            awaitWeb("document.querySelector('.phone-vpn-toggle')?.title.endsWith('SE')===true",12);
            navigate("/private-browser");
            awaitWeb("document.querySelector('.private-browser-controls [name=country]')?.value==='se'",12);
        }finally{
            if(!initialOn && "true".equals(js("document.querySelector('.phone-vpn-toggle')?.dataset.enabled==='true'"))){
                tapVpnSwitch();
                awaitWeb("document.querySelector('.phone-vpn-toggle')?.dataset.enabled==='false'",12);
            }
            selectExit(prior);
        }
    }
    void checkTrackHistory() throws Exception {
        File path=new File(getTargetContext().getExternalFilesDir(null),"Workstation/OpenIntel/observations.sqlite3");
        String object="QA-history-"+java.util.UUID.randomUUID();
        long now=System.currentTimeMillis()/1000;
        try(android.database.sqlite.SQLiteDatabase db=android.database.sqlite.SQLiteDatabase.openDatabase(path.toString(),null,android.database.sqlite.SQLiteDatabase.OPEN_READWRITE)){
            try{
                for(String source:new String[]{"air","ships"})for(int offset:new int[]{1800,30}){
                    String id=java.util.UUID.randomUUID().toString();
                    org.json.JSONObject report=new org.json.JSONObject().put("id",id).put("source",source).put("object",object)
                        .put("title",object+" "+source).put("lat",60).put("lon",24).put("time",now-offset).put("detail","Synthetic QA history");
                    db.execSQL("INSERT INTO obs VALUES (?,?,?,?,?,?,?,NULL)",new Object[]{"finland",source,object,now-offset,now,id,report.toString()});
                }
                navigate("/openintel?region=finland&view=reports");
                for(String source:new String[]{"air","ships"}){
                    String choice="Array.from(document.querySelectorAll('.intel-result')).find(b=>b.textContent.includes('"+object+" "+source+"'))";
                    awaitWeb("!!"+choice,12);
                    js(choice+".click();Array.from(document.querySelectorAll('#intel-detail button')).find(b=>b.textContent==='View report history').click()");
                    awaitWeb("document.querySelectorAll('#track-reports li').length===2 && document.querySelector('#track-reports em')?.textContent.includes('30 min')===true",15);
                    results.putString("Track history "+source,js("document.querySelector('#track-summary a').textContent"));
                    js("document.querySelector('#track-close').click()");
                }
            }finally{db.delete("obs","region=? AND object=?",new String[]{"finland",object});}
        }
    }
    void checkEpisodeShelves() throws Exception {
        navigate("/library/shows");
        org.json.JSONArray links=new org.json.JSONArray(js("Array.from(document.querySelectorAll('a.item[href^=\"/content/\"]'),a=>a.pathname)"));
        int collections=0;
        for(int i=0;i<links.length();i++){
            navigate(links.getString(i));
            if(!"true".equals(js("!!document.querySelector('.episode-grid')")))continue;
            collections++;
            String ready="Array.from(document.querySelectorAll('.episode-grid a.item'))";
            js("(async()=>{let bad=[];let imgs=[...document.querySelectorAll('.episode-grid a img')];"+
               "for(let i=0;i<imgs.length;i+=2){await Promise.all(imgs.slice(i,i+2).map(async img=>{img.loading='eager';"+
               "try{await img.decode();if(!img.naturalWidth)throw Error()}catch{bad.push(img.closest('a').search)}}))}"+
               "window.episodeArtQA={count:imgs.length,bad};})()");
            for(int n=0;n<900 && !"true".equals(js("!!window.episodeArtQA"));n++)Thread.sleep(150);
            org.json.JSONObject art=new org.json.JSONObject(js("window.episodeArtQA"));
            if(art.getJSONArray("bad").length()>0)throw new IOException("Missing episode artwork "+links.getString(i)+" "+art);
            js("document.querySelector('.episode-grid').scrollIntoView({block:'start'})");
            if(!"true".equals(js("!!document.querySelector('.series-hero')?.naturalWidth && !!document.querySelector('.episode-grid a img')?.naturalWidth && "+ready+".every((a,i,all)=>i===0 || +new URL(a.href).searchParams.get('part')>+new URL(all[i-1].href).searchParams.get('part'))")))
                throw new IOException("Collection art or ordering failed for "+links.getString(i));
            results.putString("Episode grid "+collections,js("document.querySelector('.episode-grid').previousElementSibling.textContent"));
            if(collections==1){
                String lit=js("Array.from(document.querySelectorAll('.episode-grid img')).slice(0,6).map(img=>{"+
                    "const c=document.createElement('canvas');c.width=c.height=16;const ctx=c.getContext('2d');ctx.drawImage(img,0,0,16,16);"+
                    "return Array.from(ctx.getImageData(0,0,16,16).data).filter((v,i)=>i%4!==3&&v>28).length})");
                results.putString("First six thumbnails, lit channels",lit);
                historyScreenshot("openintel-qa-episode-grid");
            }
        }
        if(collections==0)throw new IOException("No saved episode collections");
        navigate("/dictionary");
        if(!"true".equals(js("getComputedStyle(document.body).caretColor==='rgba(0, 0, 0, 0)' && Array.from(document.querySelectorAll('input')).some(i=>i.type==='search'&&getComputedStyle(i).caretColor!=='rgba(0, 0, 0, 0)')")))throw new IOException("Reading caret or editable field contrast failed");
        results.putString("Read-only caret and dictionary search","PASS");
    }
    void captureCheck() throws Exception {
        navigate("/private-browser?to=https%3A%2F%2Fwww.legislation.gov.uk%2Fssi%2F2016%2F414%2Farticle%2F1%2Fmade");
        boolean tapped=false;
        for(int n=0;n<180 && !tapped;n++){
            android.view.accessibility.AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();
            if(root!=null && !root.findAccessibilityNodeInfosByText("Aberdeen Harbour Revision Order").isEmpty()){
                for(android.view.accessibility.AccessibilityNodeInfo button:root.findAccessibilityNodeInfosByText("Capture page to case")){
                    if(button.isClickable())tapped=button.performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK);
                }
            }
            if(!tapped)Thread.sleep(700);
        }
        if(!tapped)throw new IOException("The protected browser did not show the harbour order and capture button.");
        for(int n=0;n<150 && !"true".equals(js("!!document.querySelector('#capture-review[open] select option')"));n++)Thread.sleep(150);
        if(!"true".equals(js("document.getElementById('capture-title')?.textContent.includes('legislation.gov.uk')")))throw new IOException("Capture review failed to open");
        js("var f=document.getElementById('capture-form');f.elements.owner.value='new';f.elements.owner.onchange();f.elements.title.value='Browser capture QA '+Date.now();f.requestSubmit()");
        for(int n=0;n<150 && !"true".equals(js("!!document.querySelector('#case-exhibits')?.textContent.includes('Browser viewport')"));n++)Thread.sleep(150);
        if(!"true".equals(js("['Browser viewport','Rendered page text','Rendered HTML'].every(v=>document.querySelector('#case-exhibits')?.textContent.includes(v))")))
            throw new IOException("Missing saved browser exhibits. "+js("document.getElementById('capture-status')?.textContent"));
        int owner=Integer.parseInt(new org.json.JSONArray(js("[document.getElementById('case-owner').value]")).getString(0));
        verifyCapture(owner);
    }
    void verifyCapture(int owner) throws Exception {
        org.json.JSONArray items=new org.json.JSONObject(get("/openintel/cases?owner="+owner,"Browser viewport")).getJSONArray("items");
        if(items.length()!=3)throw new IOException("Unexpected exhibit count");
        for(int i=0;i<items.length();i++){
            org.json.JSONObject item=items.getJSONObject(i);
            HttpURLConnection source=(HttpURLConnection)new URL(origin+"/openintel/cases/"+owner+"/exhibits/"+item.getString("ref")).openConnection();
            source.setRequestProperty("Cookie",cookie);
            try(InputStream in=source.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int n;
                while((n=in.read(buffer))!=-1)out.write(buffer,0,n);
                byte[] bytes=out.toByteArray();
                StringBuilder hash=new StringBuilder();
                for(byte b:java.security.MessageDigest.getInstance("SHA-256").digest(bytes))hash.append(String.format("%02x",b&255));
                if(!hash.toString().equals(item.getString("sha256")))throw new IOException("Saved bytes changed");
                if(item.getString("material").equals("Browser viewport")){
                    android.graphics.Bitmap pic=android.graphics.BitmapFactory.decodeByteArray(bytes,0,bytes.length);
                    if(pic==null||pic.getWidth()<100)throw new IOException("Missing viewport");
                    java.util.HashSet<Integer> colors=new java.util.HashSet<>();
                    for(int y=0;y<pic.getHeight();y+=4)for(int x=0;x<pic.getWidth();x+=4)colors.add(pic.getPixel(x,y));
                    pic.recycle();if(colors.size()<8)throw new IOException("Viewport is blank");
                }else if(!new String(bytes,"UTF-8").contains(item.getString("url").startsWith("https://example.org/")?
                            "This domain is for use in documentation examples":"Aberdeen Harbour Revision Order"))throw new IOException("Case "+owner+" "+item.getString("material")+" unexpected content: "+new String(bytes,"UTF-8").substring(0,Math.min(200,new String(bytes,"UTF-8").length())));
            }finally{source.disconnect();}
        }
        results.putString("Browser capture","Case "+owner+" has a nonblank viewport, readable text and rendered HTML, all reopened and hash verified");
    }
    void puzzleCheck() throws Exception {
        navigate("/library/games");
        org.json.JSONArray boards=new org.json.JSONArray(js("Array.from(document.querySelectorAll('a[href*=play]'),a=>a.href)"));
        if(boards.length()==0){
            String link=new org.json.JSONArray(js("Array.from(document.querySelectorAll('a.item'),a=>[a.textContent,a.pathname]).filter(a=>a[0].includes('Lights Out')).map(a=>a[1])")).getString(0);
            navigate(link);
            String raw=new org.json.JSONArray(js("[document.querySelector('.puzzle-frame').getAttribute('src')]")).getString(0);
            if(!get(raw,"Switch off every light").contains("aria-pressed"))throw new IOException("Bundled board unavailable");
            js("document.querySelector('.puzzle-frame').scrollIntoView({block:'center'})");
            Thread.sleep(800);
            android.graphics.Bitmap before=getUiAutomation().takeScreenshot();
            if(before==null)throw new IOException("Game screen unavailable");
            int tx=-1,ty=-1,original=0;
            for(int y=100;y<before.getHeight()-80 && tx<0;y+=4){
                for(int x=24;x<before.getWidth()-24;x+=4){
                    int color=before.getPixel(x,y)&0xffffff;
                    if((color==0xa9d9b7 || color==0x26372d) && (before.getPixel(x+10,y+10)&0xffffff)==color){
                        tx=x+5;ty=y+5;original=color;break;
                    }
                }
            }
            before.recycle();
            if(tx<0)throw new IOException("Rendered game board missing");
            long now=android.os.SystemClock.uptimeMillis();
            sendPointerSync(MotionEvent.obtain(now,now,MotionEvent.ACTION_DOWN,tx,ty,0));
            sendPointerSync(MotionEvent.obtain(now,now+70,MotionEvent.ACTION_UP,tx,ty,0));
            Thread.sleep(350);
            android.graphics.Bitmap after=getUiAutomation().takeScreenshot();
            int color=after.getPixel(tx,ty)&0xffffff;after.recycle();
            if(color==original || (color!=0xa9d9b7 && color!=0x26372d))throw new IOException("Touch did not switch the rendered light");
            results.putString("Bundled Lights Out move","PASS");
            return;
        }
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
        navigate("/library/watch");
        String videoPage=new org.json.JSONArray(js("Array.from(document.querySelectorAll('a.item'),a=>[a.textContent,a.pathname]).filter(a=>a[0].includes('Big Buck Bunny')).map(a=>a[1])")).getString(0);
        navigate(videoPage);
        String playerLink=new org.json.JSONArray(js("[document.querySelector('a[href^=\"/player/\"]').getAttribute('href')]")).getString(0);
        results.putString("player uses local poster",js("document.querySelector('main video').poster.startsWith(location.origin+'/')"));
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
        navigate(videoPage);
        ActivityMonitor playerMonitor=addMonitor("dev.echooffgrid.mobile.Player",null,false);
        js("document.querySelector('a[href^=\"/player/\"]').click()");
        Activity playerActivity=playerMonitor.waitForActivityWithTimeout(10000);
        removeMonitor(playerMonitor);
        if(playerActivity==null)throw new IOException("Native player link failed to open");
        try {
            java.lang.reflect.Field field=playerActivity.getClass().getDeclaredField("player");
            field.setAccessible(true);
            Object nativePlayer=field.get(playerActivity);
            if(nativePlayer==null)throw new IOException("Native player failed to initialize for "+playerLink);
            results.putString("VLC source",playerLink);
            boolean playing=false;
            Object media=nativePlayer == null ? null : nativePlayer.getClass().getMethod("getMedia").invoke(nativePlayer);
            for(int n=0;n<150 && nativePlayer!=null;n++){
                Object stats=media.getClass().getMethod("getStats").invoke(media);
                if(stats!=null && stats.getClass().getField("displayedPictures").getInt(stats)>1){playing=true;break;}
                if((Long)nativePlayer.getClass().getMethod("getTime").invoke(nativePlayer)>0){playing=true;break;}
                Thread.sleep(100);
            }
            if(media!=null)media.getClass().getMethod("release").invoke(media);
            results.putString("VLC length",String.valueOf(nativePlayer.getClass().getMethod("getLength").invoke(nativePlayer)));
            results.putString("VLC final state",String.valueOf(nativePlayer.getClass().getMethod("getPlayerState").invoke(nativePlayer)));
            if(!playing)throw new IOException("VLC did not decode the local file");
            results.putString("local VLC playback","PASS");
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
        String text=String.valueOf(byClass?n.getClassName():(n.getText()!=null?n.getText():n.getContentDescription()));
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
    private void shell(String cmd)throws Exception{
        try(android.os.ParcelFileDescriptor fd=getUiAutomation().executeShellCommand(cmd);
            InputStream stream=new android.os.ParcelFileDescriptor.AutoCloseInputStream(fd)){while(stream.read()!=-1){}}
    }
    private org.json.JSONObject audioState()throws Exception{
        Class<?> service=getTargetContext().getClassLoader().loadClass("dev.echooffgrid.mobile.Playback");
        java.lang.reflect.Method method=service.getDeclaredMethod("snapshot");method.setAccessible(true);
        org.json.JSONObject[] state={null};runOnMainSync(()->{try{state[0]=(org.json.JSONObject)method.invoke(null);}catch(Exception e){throw new RuntimeException(e);}});
        return state[0];
    }
    private String firstShelf(String kind,String selector)throws Exception{
        navigate("/library/"+kind);
        return new org.json.JSONArray(js("Array.from(document.querySelectorAll("+org.json.JSONObject.quote(selector)+"),a=>a.pathname+a.search)")).getString(0);
    }
    private String seedSeriesFixture() throws Exception {
        String key=java.util.UUID.randomUUID().toString().replace("-","");key=key+key;
        File root=new File(getTargetContext().getExternalFilesDir(null),"Workstation");
        // Seed before Main starts so the embedded runtime has no open database connection.
        try(android.database.sqlite.SQLiteDatabase db=android.database.sqlite.SQLiteDatabase.openDatabase(new File(root,"archive.sqlite3").getPath(),null,android.database.sqlite.SQLiteDatabase.OPEN_READWRITE)){
            db.beginTransaction();
            try{
                for(int part=0;part<3;part++){
                    String file=key+"-"+part+".mp4",title="Fixture S01E0"+(part+1);
                    try(InputStream in=getContext().getAssets().open("show.mp4")){
                        java.nio.file.Files.copy(in,new File(new File(root,"Content"),file).toPath());
                    }
                    if(part==0)db.execSQL("INSERT INTO discovery_item VALUES(?,?,?,?,?,?,?,?,?)",new Object[]{key,"Shows","Playback QA","","","","","QA",file});
                    db.execSQL("INSERT INTO discovery_file VALUES(?,?,?,?)",new Object[]{key,part,title,file});
                    db.execSQL("INSERT INTO series_parts VALUES(?,?,?)",new Object[]{key,part,title});
                }
                db.setTransactionSuccessful();
            }finally{db.endTransaction();}
        }
        return key;
    }

    private void checkSeriesPlayback(String key) throws Exception {
        navigate("/content/"+key+"?episodes=1");
        String original=js("document.cookie.split('; ').includes('echo_autoplay=1')");
        try(java.util.Scanner input=new java.util.Scanner(getContext().getAssets().open("series-playback.js"),"UTF-8")){
            String script=input.useDelimiter("\\A").next();
            js("sessionStorage.removeItem('seriesStep')");
            for(int i=0;i<400;i++){
                js("if(document.readyState==='complete' && location.pathname==='/content/"+key+"'){window.qaSeriesKey='"+key+"';"+script+"}");
                String proof=js("window.seriesPlaybackProof");
                if(proof.contains("FAIL"))throw new IOException(proof);
                if(proof.contains("PASS")){
                    results.putString("Series playback",proof);
                    navigate("/content/"+key+"?part=2");
                    ActivityMonitor monitor=addMonitor("dev.echooffgrid.mobile.Player",null,false);
                    js("document.querySelector('a[href^=\"/player/content/\"]').click()");
                    Activity nativePlayer=monitor.waitForActivityWithTimeout(12000);removeMonitor(monitor);
                    if(nativePlayer==null)throw new IOException("Native episode failed to open");
                    for(int n=0;n<600 && !nativePlayer.isDestroyed();n++)Thread.sleep(100);
                    if(!nativePlayer.isDestroyed()){runOnMainSync(nativePlayer::finish);throw new IOException("Native episode did not finish");}
                    navigate("/content/"+key+"?episodes=1");
                    awaitWeb("document.querySelectorAll('.episode-grid progress[value=\"100\"]').length===3",8);
                    results.putString("Native series playback","Last episode played to completion and saved its watched bar");
                    return;
                }
                Thread.sleep(180);
            }
            throw new IOException("Series test timed out "+js("[location.href,sessionStorage.seriesStep,document.querySelector('video')?.error?.message]"));
        }finally{
            js("document.cookie='echo_autoplay="+("true".equals(original)?"1":"0")+"; Path=/; Max-Age=31536000; SameSite=Strict'");
            navigate("/content/"+key+"?episodes=1");
            js("document.querySelector('form[action=\"/download/remove\"]').requestSubmit()");
        }
    }
    private void checkGridDelete() throws Exception {
        // Import and delete a disposable file through the same endpoints and UI as the user.
        navigate("/library/books");
        String token=new org.json.JSONArray(js("[document.querySelector('.personal-import').dataset.token]")).getString(0);
        HttpURLConnection upload=(HttpURLConnection)new URL(origin+"/library/books/import").openConnection();
        upload.setRequestProperty("Cookie",cookie);upload.setRequestProperty("X-Library-Token",token);
        upload.setRequestProperty("X-Filename","Temporary deletion test.txt");upload.setRequestMethod("POST");upload.setDoOutput(true);
        String key;
        try{
            try(OutputStream out=upload.getOutputStream()){out.write(("Temporary library QA "+java.util.UUID.randomUUID()).getBytes("UTF-8"));}
            try(BufferedReader in=new BufferedReader(new InputStreamReader(upload.getInputStream()))){key=in.readLine();}
        }finally{upload.disconnect();}
        if(key==null || !key.matches("personal-[0-9a-f]{64}"))throw new IOException("Could not import temporary test file");
        navigate("/library/books");
        String card="document.querySelector('a[href=\"/content/"+key+"\"]')";
        js(card+".parentElement.querySelector('.grid-delete').click()");
        awaitWeb("document.querySelector('.library-delete-dialog').open",3);
        js("document.querySelector('.library-delete-dialog button[value=cancel]').click()");
        if(!"true".equals(js("!!"+card)))throw new IOException("Cancel lost the test title");
        js(card+".parentElement.querySelector('.grid-delete').click();document.querySelector('.delete-title').click()");
        awaitWeb("!"+card,10);
        File disposable=new File(getTargetContext().getExternalFilesDir(null),"Workstation/Content/"+key+".txt");
        for(int n=0;n<100 && disposable.exists();n++)Thread.sleep(100);
        if(disposable.exists() || get("/library/books","Books").contains("/content/"+key))throw new IOException("Delete did not clear test title");
        results.putString("Delete","Removed temporary title and local bytes");
    }
    private void backgroundChecks(String mode)throws Exception{
        if(mode.equals("gridDelete")){checkGridDelete();return;}
        if(mode.equals("pip")){
            String path=firstShelf("watch","a.item");navigate(path);
            ActivityMonitor monitor=addMonitor("dev.echooffgrid.mobile.Player",null,false);
            js("Array.from(document.querySelectorAll('a')).find(a=>a.textContent==='Picture in picture').click()");
            Activity activity=monitor.waitForActivityWithTimeout(15000);removeMonitor(monitor);
            if(activity==null)throw new IOException("Native player did not open");
            try{
                for(int n=0;n<120&&!activity.isInPictureInPictureMode();n++)Thread.sleep(100);
                if(!activity.isInPictureInPictureMode())throw new IOException("Not in PiP");
                java.lang.reflect.Field field=activity.getClass().getDeclaredField("player");field.setAccessible(true);
                Object player=field.get(activity);
                java.lang.reflect.Method clock=player.getClass().getMethod("getTime");
                long before=(Long)clock.invoke(player);Thread.sleep(1200);long after=(Long)clock.invoke(player);
                if(after<=before)throw new IOException("PiP playback did not advance: "+before+" to "+after);
                results.putString("Native PiP",path+" · "+before+" to "+after+" ms");
            }finally{runOnMainSync(activity::finish);}
            return;
        }
        boolean book=mode.equals("book"),download=mode.equals("download");
        File saved=null;
        String path="";
        String bookMarker="SHAKESPEARE";
        org.json.JSONObject before=new org.json.JSONObject();
        if(download){
            String id="75974d82939c68e2d9df886f2678b7060197f7ba1bfbae4188351d11a5e39132";
            File content=new File(getTargetContext().getExternalFilesDir(null),"Workstation/Content");
            String query="Complete+Works+William+Shakespeare";
            if(new File(content,id+".txt").exists()){
                id="9c7416c8b818ba80d4a0e927e0f7b2f9fc63a818b7817d8cd7317258519a2ffb";
                bookMarker="MOBY";
                query="Moby+Dick+Melville";
            }
            saved=new File(content,id+".txt");
            if(saved.exists())throw new IOException("Test titles already installed. Use a clean test library.");
            get("/discover?kind=Books&provider=Project+Gutenberg&q="+query,"Project Gutenberg");
            navigate("/discover/item/"+id);
            js("document.querySelector('form[action=\"/discover/add\"] button').click()");
        }else{
            path=book?firstShelf("listen","a.item[href^='/library/listen/']"):"/dictionary?q=fern";
            navigate(path);
            if(book)js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Play audiobook').click()");
            else js("document.querySelector('#read-all').click()");
            for(int n=0;n<300;n++){before=audioState();if(before.optLong("position")>300 && before.optBoolean("ready"))break;Thread.sleep(200);}
            if(before.optLong("position")<=300)throw new IOException("Playback failed to start "+path+" "+before);
        }
        shell("am start -a android.settings.SETTINGS");

        shell("input keyevent KEYCODE_SLEEP");
        android.os.PowerManager power=getTargetContext().getSystemService(android.os.PowerManager.class);
        if(power.isInteractive())Thread.sleep(1500);
        if(power.isInteractive())throw new IOException("Screen did not lock");
        long bytes=saved==null?0:saved.length();long atLock=audioState().optLong("position");
        Thread.sleep(16000);
        org.json.JSONObject after=audioState();
        if(!download){
            if(power.isInteractive() || after.optBoolean("paused") || after.optLong("position")<=atLock+1000)
                throw new IOException("Audio failed screen-off check "+after);
            if(!book && after.optInt("part")==before.optInt("part"))throw new IOException("Narration did not advance to another passage");
            results.putString(mode+" background playback",path+" · "+atLock+" to "+after.getLong("position")+" ms · part "+after.optInt("part"));
        }
        if(saved!=null){
            for(int n=0;n<180 && !saved.exists();n++)Thread.sleep(500);
            if(!saved.exists())throw new IOException("Download did not complete "+get("/downloads","Downloads").replaceAll("<[^>]+>"," ").replaceAll("\\s+"," ").substring(0,400));
            if(power.isInteractive())throw new IOException("Display woke before download verification");
            if(bytes>0)throw new IOException("Transfer finished before screen lock");
            String text=new String(java.nio.file.Files.readAllBytes(saved.toPath()),"UTF-8");
            if(!text.toUpperCase(java.util.Locale.ROOT).contains(bookMarker) || !text.toUpperCase(java.util.Locale.ROOT).contains("END OF THE PROJECT GUTENBERG"))throw new IOException("Invalid Gutenberg download");
            results.putString("Completed locked download",saved.length()+" bytes, "+bookMarker+", verified book and end marker");
        }
    }

    @Override public void onStart() {
        try{

            String fixture="seriesPlayback".equals(backgroundMode)?seedSeriesFixture():null;
            ActivityMonitor monitor=addMonitor("dev.echooffgrid.mobile.Main",null,false);
            try(android.os.ParcelFileDescriptor command=getUiAutomation().executeShellCommand("am start -n dev.echooffgrid.mobile/.Main");
                InputStream in=new android.os.ParcelFileDescriptor.AutoCloseInputStream(command)){while(in.read()!=-1){}}
            Activity app=monitor.waitForActivityWithTimeout(20000);
            removeMonitor(monitor);
            if(app==null)throw new IOException("The phone did not foreground EchoOffGrid within 20 seconds");
            runOnMainSync(()->app.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON));
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
            if(fixture!=null){checkSeriesPlayback(fixture);finish(Activity.RESULT_OK,results);return;}
            if(seriesIds!=null){
                String[] ids=seriesIds.split(",");
                for(String id:ids)if(!id.matches("[0-9a-f]{64}"))throw new IOException("Invalid test selection");
                if(cancelId!=null){
                    if(!cancelId.matches("[0-9a-f]{64}"))throw new IOException("Invalid test cancellation");
                    navigate("/downloads");
                    String select="form[action='/download/cancel'] input[value='discover-"+cancelId+"']";
                    if(!"true".equals(js("!!document.querySelector("+org.json.JSONObject.quote(select)+")")))throw new IOException("Test queue entry missing");
                    js("document.querySelector("+org.json.JSONObject.quote(select)+").form.requestSubmit()");
                    Thread.sleep(1300);
                    if(get("/downloads","Downloads").contains("value=\"discover-"+cancelId+"\""))throw new IOException("Cancel did not clear test entry");
                    results.putString("Queue cancellation","Only requested item removed");
                    for(String id:ids){
                        navigate("/discover/item/"+id);
                        String btn="form[action='/discover/add'] button";
                        if(!"true".equals(js("!!document.querySelector("+org.json.JSONObject.quote(btn)+")")))navigate("/content/"+id);
                        js("document.querySelector("+org.json.JSONObject.quote(btn)+").click()");
                        Thread.sleep(700);
                    }
                }
                checkGridDelete();
                for(String id:ids){
                    boolean ready=false;
                    for(int n=0;n<720;n++){
                        if(get("/library/shows","Shows").contains("/content/"+id)){ready=true;break;}
                        Thread.sleep(5000);
                    }
                    if(!ready)throw new IOException("No complete episode yet for "+id);
                    navigate("/library/shows");
                    js("document.querySelector('a[href=\"/content/"+id+"\"]').click()");
                    for(int n=0;n<100 && !"true".equals(js("!!document.querySelector('.episode-grid a, main video')"));n++)Thread.sleep(150);
                    js("document.querySelector('.episode-grid a')?.click()");
                    for(int n=0;n<100 && !"true".equals(js("!!document.querySelector('main video')"));n++)Thread.sleep(150);
                    ActivityMonitor movie=addMonitor("dev.echooffgrid.mobile.Player",null,false);
                    js("document.querySelector('a[href^=\"/player/content/\"]').click()");
                    Activity activity=movie.waitForActivityWithTimeout(15000);removeMonitor(movie);
                    if(activity==null)throw new IOException("Player did not open");
                    try{
                        java.lang.reflect.Field field=activity.getClass().getDeclaredField("player");field.setAccessible(true);
                        Object player=field.get(activity);
                        java.lang.reflect.Method clock=player.getClass().getMethod("getTime");
                        long first=(Long)clock.invoke(player),last=first;
                        for(int n=0;n<120 && last<=first+1000;n++){Thread.sleep(150);last=(Long)clock.invoke(player);}
                        if(last<=first+1000)throw new IOException("Video did not advance for "+id);
                        results.putString("Series "+id.substring(0,8),"Shelf → native video, "+last+" ms");
                        android.util.Log.i("EchoSeries","Played "+id.substring(0,8)+" to "+last+" ms");
                    }finally{runOnMainSync(activity::finish);}
                }
                finish(Activity.RESULT_OK,results);return;
            }
            if("inlinePip".equals(backgroundMode) || "swipePip".equals(backgroundMode) || "pausedPip".equals(backgroundMode)){
                String page=firstShelf("watch","a.item");navigate(page);
                String video="document.querySelector('main video[controls]')";
                js(video+".loop=true;"+video+".play()");
                awaitWeb(video+".currentTime>0.1",20);
                if("pausedPip".equals(backgroundMode)){
                    js(video+".pause()");
                    awaitWeb(video+".paused",5);waitForIdleSync();
                    shell("input keyevent KEYCODE_HOME");Thread.sleep(1200);
                    if(app.isInPictureInPictureMode())throw new IOException("Paused video incorrectly entered PiP");
                    results.putString(backgroundMode,"Paused video stayed out of PiP");finish(Activity.RESULT_OK,results);return;
                }
                if("inlinePip".equals(backgroundMode))shell("input keyevent KEYCODE_HOME");
                else {
                    android.graphics.Rect display=app.getWindowManager().getCurrentWindowMetrics().getBounds();
                    int x=display.centerX();
                    shell("input swipe "+x+" "+(display.bottom-2)+" "+x+" "+display.centerY()+" 180");
                }
                for(int i=0;i<60 && !app.isInPictureInPictureMode();i++)Thread.sleep(100);
                if(!app.isInPictureInPictureMode())throw new IOException("Home did not float the inline video");
                awaitWeb("document.documentElement.classList.contains('video-pip')",10);
                double before=Double.parseDouble(js(video+".currentTime"));Thread.sleep(1100);
                double after=Double.parseDouble(js(video+".currentTime"));
                if(before==after || !"false".equals(js(video+".paused")))throw new IOException("Floating playback stalled");
                boolean fills="true".equals(js("(()=>{let r="+video+".getBoundingClientRect();return Math.abs(r.width-innerWidth)<3 && Math.abs(r.height-innerHeight)<3})()"));
                if(!fills)throw new IOException("Video does not fill the floating screen");
                results.putString(backgroundMode,page+" · "+before+" to "+after+" s");finish(Activity.RESULT_OK,results);return;
            }
            if(backgroundMode!=null){backgroundChecks(backgroundMode);finish(Activity.RESULT_OK,results);return;}
            if(protectedLink){
                navigate("/news");
                js("(()=>{const a=document.createElement('a');a.href='https://check.torproject.org/';a.target='_blank';a.textContent='Publisher link';document.querySelector('main').append(a);a.click();})()");
                awaitNode("Congratulations",false);
                results.putString("Protected external link","PASS · clicked from News and verified Tor exit");
                awaitNode("Done",false).performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK);
                finish(Activity.RESULT_OK,results);return;
            }
            if(exportsOnly){
                for(String[] item:new String[][]{{"/archive","/archive/backup","EchoOffGrid","SQLite format 3"},{"/evidence","/evidence.csv","EchoOffGrid-evidence","event_at_utc"}}){
                    navigate(item[0]);
                    android.net.Uri downloads=android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI;
                    android.content.ContentResolver resolver=getTargetContext().getContentResolver();
                    long last=0;
                    try(android.database.Cursor c=resolver.query(downloads,new String[]{"_id"},null,null,"_id DESC")){
                        if(c!=null && c.moveToFirst())last=c.getLong(0);
                    }
                    js("document.querySelector('main a[href^="+org.json.JSONObject.quote(item[1])+"]').click()");
                    boolean valid=false;
                    for(int i=0;i<300 && !valid;i++){
                        try(android.database.Cursor c=resolver.query(downloads,new String[]{"_id"},"_id>? AND _display_name LIKE ? AND is_pending=0",new String[]{String.valueOf(last),item[2]+"%"},"_id DESC")){
                            if(c!=null && c.moveToFirst()){
                                try(InputStream in=resolver.openInputStream(android.content.ContentUris.withAppendedId(downloads,c.getLong(0)))){
                                    DataInputStream data=new DataInputStream(in);byte[] head=new byte[item[3].length()];data.readFully(head);
                                    valid=item[3].equals(new String(head,"UTF-8"));
                                }
                            }
                        }
                        if(!valid)Thread.sleep(100);
                    }
                    if(!valid)throw new IOException("Download missing or incorrect: "+item[1]);
                    results.putString(item[1],"PASS · file written in Downloads and header matches");
                }
                finish(Activity.RESULT_OK,results);return;
            }
            if(tabsOnly){
                navigate("/");
                String[] pages={"/","/library","/news","/openintel","/opengov","/opencorpo","/history","/wikipedia","/dictionary","/maps","/downloads","/private-browser","/echolite","/devices"};
                for(String path:pages){
                    String target=org.json.JSONObject.quote(path);
                    js("document.querySelector('.drawer-trigger').click();document.querySelector('#section-drawer a[href='+JSON.stringify("+target+")+']').click()");
                    if(path.equals("/echolite")){
                        waitForPackage("dev.echolite.android");
                        sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
                        waitForPackage("dev.echooffgrid.mobile");
                    }else{
                        boolean rendered=false;
                        for(int n=0;n<300 && !rendered;n++){
                            boolean[] loaded={false};
                            runOnMainSync(()->loaded[0]=(origin+path).equals(web.getUrl()) && web.getProgress()==100);
                            if(!loaded[0]){Thread.sleep(150);continue;}
                            rendered="true".equals(js("location.pathname==="+target+" && document.readyState==='complete' && !!document.querySelector('main')?.innerText.trim() && document.documentElement.scrollWidth<=innerWidth+1"));
                            if(!rendered)Thread.sleep(150);
                        }
                        if(!rendered)throw new IOException("Tab failed to render or overflowed: "+path+" "+js("[location.pathname,document.readyState,document.documentElement.scrollWidth,innerWidth]"));
                    }
                    results.putString("Tab "+path,"PASS");
                }
                for(String path:new String[]{"/evidence?source=HackRF","/evidence?source=ScotMesh","/evidence","/evidence.csv?checks=1","/wiki-progress","/home-status","/archive","/library/documents"})get(path,"");
                results.putString("Devices","PASS · receiver, mesh, comparisons and CSV");
                finish(Activity.RESULT_OK,results);return;
            }
            if(corpoOnly){
                navigate("/opencorpo?country=ownership");
                get("/opencorpo?country=ownership","beneficial ownership");
                get("/opencorpo?country=royal","Royal House of Spain");
                get("/opencorpo?source=local&q=Berkshire","Read offline");
                navigate("/opencorpo?source=gleif&q=Siemens");
                String key=new org.json.JSONArray(js("Array.from(document.querySelectorAll('.gov-card input[name=item],.gov-card a[href]'),e=>e.value||e.pathname.split('/').pop())")).getString(0);
                js("document.querySelector('.gov-card button')?.click()");
                boolean saved=false;
                for(int i=0;i<60 && !saved;i++){
                    saved=get("/library/documents","Lend-Lease Act").contains(key);
                    if(!saved)Thread.sleep(500);
                }
                if(!saved)throw new IOException("Entity record missing from Documents");
                navigate("/content/"+key);
                get("/content/"+key,"Legal name");
                get("/content-file/"+key,"legalName");
                results.putString("OpenCorpo","PASS · live lookup, save, shelf, local reader and source JSON");
                finish(Activity.RESULT_OK,results);return;
            }
            if(exportCase!=null){
                navigate("/openintel");
                org.json.JSONObject list=new org.json.JSONObject(get("/openintel/cases","cases"));
                org.json.JSONArray entries=list.getJSONArray("cases");
                int id=0;
                for(int i=0;i<entries.length();i++){
                    org.json.JSONObject row=entries.getJSONObject(i);
                    if(exportCase.equals(row.getString("title")))id=row.getInt("id");
                }
                if(id==0)throw new IOException("Requested case missing");
                HttpURLConnection c=(HttpURLConnection)new URL(origin+"/openintel/cases/"+id+"/export").openConnection();
                c.setRequestProperty("Cookie",cookie);
                try(InputStream in=c.getInputStream(); FileOutputStream out=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),"sync-proof.zip"))){
                    byte[] buf=new byte[8192];
                    for(int n;(n=in.read(buf))!=-1;)out.write(buf,0,n);
                }finally{c.disconnect();}
                results.putString("export",exportCase);
                finish(Activity.RESULT_OK,results);return;
            }
            if(trackHistory){checkTrackHistory();finish(Activity.RESULT_OK,results);return;}
            if(geography){
                navigate("/openintel?region=aberdeen");
                try(java.util.Scanner script=new java.util.Scanner(getContext().getAssets().open("geography.js"),"UTF-8")){
                    js(script.useDelimiter("\\A").next());
                }
                awaitWeb("!!window.geographyQA",350);
                org.json.JSONObject proof=new org.json.JSONObject(js("window.geographyQA"));
                if(proof.has("error"))throw new IOException(proof.getString("error"));
                results.putString("Geography",proof.toString());finish(Activity.RESULT_OK,results);return;
            }
            if(vpnRegion){checkVpnRegion();finish(Activity.RESULT_OK,results);return;}
            if(shelvesOnly){checkEpisodeShelves();finish(Activity.RESULT_OK,results);return;}
            if(reviewCaptureOwner>0){verifyCapture(reviewCaptureOwner);finish(Activity.RESULT_OK,results);return;}
            if(captureOnly){captureCheck();finish(Activity.RESULT_OK,results);return;}
            if(casesOnly){
                navigate("/openintel");
                try(java.util.Scanner script=new java.util.Scanner(getContext().getAssets().open("cases.js"),"UTF-8")){
                    js(script.useDelimiter("\\A").next());
                }
                for(int n=0;n<900 && !"true".equals(js("!!window.caseQA"));n++)Thread.sleep(100);
                String result=js("window.caseQA");
                org.json.JSONObject proof=new org.json.JSONObject(result);
                if(proof.has("error"))throw new IOException(proof.getString("error"));
                String name="EchoOffGrid-case-"+proof.getString("owner")+".zip";
                boolean saved=false;
                for(int n=0;n<150 && !saved;n++){
                    try(android.database.Cursor files=getTargetContext().getContentResolver().query(
                        android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI,new String[]{"_size"},
                        "_display_name=? AND is_pending=0",new String[]{name},null)){
                        saved=files!=null && files.moveToFirst() && files.getLong(0)>0;
                    }
                    if(!saved)Thread.sleep(100);
                }
                if(!saved)throw new IOException("ZIP did not finish writing to Downloads");
                results.putString("caseProof",result);
                finish(Activity.RESULT_OK,results);return;
            }
            if(visualsOnly){
                navigate("/openintel?region=aberdeen");
                for(int i=0;i<100 && !"true".equals(js("!!document.querySelector('.visual-card img')?.naturalWidth"));i++)Thread.sleep(100);
                if(!"true".equals(js("document.querySelectorAll('.visual-card').length>3 && document.querySelector('.visual-card img')?.naturalWidth>100 && document.documentElement.scrollWidth<=innerWidth+1")))throw new IOException("Offline gallery failed");
                historyScreenshot("openintel-visual-gallery");
                js("document.querySelector('.visual-card').click()");
                for(int i=0;i<220 && !"true".equals(js("!!document.querySelector('[data-overlay]')"));i++)Thread.sleep(100);
                if(!"true".equals(js("document.querySelector('#visual-content img')?.naturalWidth===768 && !!document.querySelector('[data-overlay]')")))throw new IOException("Actual NASA frame unavailable: "+js("document.querySelector('#visual-content output')?.textContent"));
                js("document.querySelector('[data-overlay]').click()");
                Thread.sleep(600);
                if(!"true".equals(js("document.querySelector('#intel-map').contentDocument.querySelector('#remove-overlay').hidden===false")))throw new IOException("Satellite overlay failed");
                historyScreenshot("openintel-satellite-overlay");
                js("document.querySelector('#orbit-explorer').open=true");
                for(int i=0;i<60 && !"true".equals(js("!!document.querySelector('#orbit-choice option')"));i++)Thread.sleep(100);
                js("let f=document.querySelector('#orbit-find'); f.value='25544'; f.dispatchEvent(new Event('input')); document.querySelector('#orbit-form').requestSubmit()");
                for(int i=0;i<100 && !"true".equals(js("!!document.querySelector('#intel-map').contentDocument.body.dataset.orbitReady"));i++)Thread.sleep(100);
                if(!"true".equals(js("!!document.querySelector('#intel-map').contentDocument.body.dataset.orbitReady && document.querySelector('#orbit-detail').textContent.includes('elements dated')")))throw new IOException("ISS ground track failed: "+js("document.querySelector('#orbit-detail').textContent"));
                results.putString("Visuals","PASS · bundled gallery, publisher image, satellite overlay, mobile layout, ISS ground track");
                finish(Activity.RESULT_OK,results);return;
            }
            if(drawerOnly){
                navigate("/openintel?view=sample");
                js("document.querySelector('.drawer-trigger').click()");
                String layout=js("(()=>{const d=document.querySelector('#section-drawer'),r=d.getBoundingClientRect();return d.open && r.left < 1 && r.right < innerWidth && [...d.querySelectorAll('a')].map(a=>a.pathname).join() === [...document.querySelectorAll('.workstation-header nav a')].map(a=>a.pathname).join() && d.querySelector('[aria-current=page]').pathname === '/openintel'})()");
                if(!"true".equals(layout))throw new IOException("Drawer layout, active section or links failed: "+layout);
                historyScreenshot("navigation-drawer");
                sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK);
                Thread.sleep(550);
                if(!"true".equals(js("location.pathname==='/openintel' && !document.querySelector('#section-drawer').open")))throw new IOException("System Back did not dismiss the drawer");
                js("document.querySelector('.drawer-trigger').click();document.querySelector('#section-drawer a[href=\"/library\"]').click()");
                for(int i=0;i<80 && !"true".equals(js("location.pathname==='/library' && !!document.querySelector('.drawer-trigger')"));i++)Thread.sleep(100);
                if(!"true".equals(js("location.pathname==='/library' && !document.querySelector('#section-drawer').open && document.documentElement.scrollWidth<=innerWidth+1")))throw new IOException("Library navigation failed");
                String target=js("document.querySelector('.echo-shortcut').pathname");
                if(!"\"/echolite\"".equals(target))throw new IOException("EchoLite shortcut target missing");
                String before=js("document.querySelector('.echo-shortcut').style.left");
                org.json.JSONArray point=new org.json.JSONArray(js("(()=>{const r=document.querySelector('.echo-shortcut').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2,innerWidth]})()"));
                int[] offset=new int[2];runOnMainSync(()->web.getLocationOnScreen(offset));
                float scale=web.getWidth()/(float)point.getDouble(2);
                float x=offset[0]+scale*(float)point.getDouble(0), y=offset[1]+scale*(float)point.getDouble(1);
                float dx=point.getDouble(0)>point.getDouble(2)/2?-72:72;
                long start=android.os.SystemClock.uptimeMillis();
                for(int step=0;step<=10;step++){
                    int action=step==0?MotionEvent.ACTION_DOWN:step==10?MotionEvent.ACTION_UP:MotionEvent.ACTION_MOVE;
                    MotionEvent touch=MotionEvent.obtain(start,android.os.SystemClock.uptimeMillis(),action,x+scale*dx*step/10,y,0);
                    touch.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);
                    sendPointerSync(touch);touch.recycle();Thread.sleep(20);
                }
                String after=js("document.querySelector('.echo-shortcut').style.left");
                if(before.equals(after) || !"true".equals(js("document.visibilityState==='visible' && location.pathname==='/library'")))throw new IOException("Dragging moved away from the library or failed to reposition");
                navigate("/openintel?view=sample");
                String restored=js("document.querySelector('.echo-shortcut').style.left");
                double originalX=Double.parseDouble(new org.json.JSONTokener(after).nextValue().toString().replace("px",""));
                double restoredX=Double.parseDouble(new org.json.JSONTokener(restored).nextValue().toString().replace("px",""));
                if(Math.abs(originalX-restoredX)>1)throw new IOException("Shortcut position changed from "+after+" to "+restored);
                historyScreenshot("echolite-shortcut");
                results.putString("Navigation","PASS · all section links, active section, system Back, Library and responsive layout");
                finish(Activity.RESULT_OK,results);return;
            }
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
            check("/library","/library/watch");
            check("/library/books","Dracula");
            check("/library/listen","A Scandal in Bohemia");
            check("/library/shows","Caminandes");
            check("/library/games","Lights Out");
            check("/library/software","Software");
            String newsroom=get("/news","rail news-grid");
            Matcher article=Pattern.compile("href=\"(/news/[a-zA-Z0-9_-]+)\"").matcher(newsroom);
            if(article.find())check(article.group(1),"Related articles");
            results.putString("/news","PASS");
            check("/archive","Saved sources");
            check("/downloads","Downloads");
            check("/devices","Devices");
            check("/dictionary?q=dog","Canidae");
            navigate("/atlas/");
            js("document.querySelector('[data-map=UK]').click()");
            for(int i=0;i<100 && !"true".equals(js("document.querySelector('[data-map=UK]').getAttribute('aria-pressed')==='true'"));i++)Thread.sleep(120);
            results.putString("UK atlas view",js("document.querySelector('#status').textContent"));
            check("/atlas/World.pmtiles","PMTiles");
            check("/atlas/vendor/maplibre-gl.js","MapLibre");
            String wiki=get("/wikipedia?q=Aberdeen","/zim/search?");
            Matcher link=Pattern.compile("src=\"(/zim/search[^\"]+)").matcher(wiki);
            if(link.find()){
                String route=link.group(1).replace("&amp;","&");
                if(!route.contains("content=wikipedia_"))throw new IOException("Wikipedia search used another reference collection");
                check(route,"Aberdeen");
                if(!"PASS".equals(results.getString(route))){Thread.sleep(2000);check(route,"Aberdeen");}
            }
            if(!wiki.contains("src=\"/zim/search"))throw new IOException("Wikipedia search frame missing");
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
