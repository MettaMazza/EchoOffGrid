package dev.echooffgrid.mobile;

import android.content.Context;
import java.net.HttpURLConnection;
import java.util.concurrent.*;
import android.graphics.Bitmap;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.webkit.WebResourceResponse;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.List;

final class LocalMedia {
    static File find(Context context, Uri uri) throws IOException {
        File root=new File(context.getExternalFilesDir(null),"Workstation");
        List<String> parts=uri.getPathSegments();
        if(parts.size()<2) throw new IOException("Missing media file");
        String kind=parts.get(1);
        File base, asset;
        if(parts.get(0).equals("content-file") || kind.equals("content")) {
            String key=kind.equals("content") && parts.size()>2 ? parts.get(2):kind;
            int index=Integer.parseInt(uri.getQueryParameter("part")==null?"0":uri.getQueryParameter("part"));
            if(index<0 || !key.matches("[a-zA-Z0-9_-]{1,100}")) throw new IOException("Unknown file");
            base=new File(root,"Content");
            asset=new File(base,resolveName(context,key,index));
        } else {
            String folder;
            switch(kind) {
                case "listen":folder="04-Entertainment/Audio";break;
                case "watch": folder="04-Entertainment/Video";break;
                case "shows": folder="04-Entertainment/Shows";break;
                case "books": folder="04-Entertainment/Books";break;
                case "guides":folder="02-Reference";break;
                case "maps":folder="03-Maps";break;
                default: throw new IOException("Unknown collection");
            }
            base=new File(root,"Kit/"+folder);
            asset=base;
            for(int i=2;i<parts.size();i++) asset=new File(asset,parts.get(i));
        }
        if(!asset.getCanonicalPath().startsWith(base.getCanonicalPath()+"/") || !asset.isFile())
            throw new IOException("The file is missing from this phone");
        return asset;
    }

    // Android and the embedded Python runtime must never open the same WAL with two SQLite libraries.
    private static final ExecutorService resolver=Executors.newFixedThreadPool(2);
    private static String resolveName(Context context,String key,int part)throws IOException {
        Future<String> result=resolver.submit(()->{
            HttpURLConnection c=Main.connection(context,"/mobile-file-name?id="+key+"&part="+part);
            c.setRequestProperty("X-Echo-Native","1");c.setReadTimeout(4000);
            try(BufferedReader in=new BufferedReader(new InputStreamReader(c.getInputStream(),StandardCharsets.UTF_8))){
                String name=in.readLine();
                if(name==null || !new File(name).getName().equals(name))throw new IOException("Invalid media file");
                return name;
            }finally{c.disconnect();}
        });
        try{return result.get(5,TimeUnit.SECONDS);}
        catch(Exception e){result.cancel(true);throw new IOException("Could not resolve local media",e);}
    }

    private static boolean hasPicture(Bitmap frame) {
        int low=255,high=0,lit=0;
        for(int y=0;y<16;y++)for(int x=0;x<16;x++){
            int pixel=frame.getPixel(frame.getWidth()*(2*x+1)/32,frame.getHeight()*(2*y+1)/32);
            int light=(android.graphics.Color.red(pixel)*3+android.graphics.Color.green(pixel)*6+
                       android.graphics.Color.blue(pixel))/10;
            low=Math.min(low,light);high=Math.max(high,light);
            if(light>28)lit++;
        }
        return high-low>=24 && lit>=20;
    }

    private static Bitmap episodeFrame(android.media.MediaMetadataRetriever reader) {
        String millis=reader.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_DURATION);
        long duration=millis==null?0:Long.parseLong(millis)*1000;
        long[] times={1500000,5500000,14000000,duration/8,duration/3,duration/2};
        Bitmap best=null;
        for(long time:times){
            long at=duration>0?Math.min(time,duration-1):time;
            Bitmap frame=reader.getScaledFrameAtTime(at,android.media.MediaMetadataRetriever.OPTION_CLOSEST,640,360);
            if(frame==null)continue;
            if(hasPicture(frame)){if(best!=null)best.recycle();return frame;}
            if(best==null)best=frame;else frame.recycle();
        }
        return best;
    }

    static WebResourceResponse poster(Context context,Uri request) throws IOException {
        File video=find(context,request.buildUpon().encodedPath(request.getEncodedPath().replace("/content-poster/","/content-file/")).build());
        File cache=new File(context.getCacheDir(),"posters");
        cache.mkdirs();
        String base=video.getName()+"-"+video.lastModified();
        File picture=new File(cache,base+"-v2.jpg");
        if(!picture.isFile()) {
            android.media.MediaMetadataRetriever reader=new android.media.MediaMetadataRetriever();
            try {
                reader.setDataSource(video.toString());
                Bitmap frame=episodeFrame(reader);
                if(frame==null) throw new IOException("No video frame available");
                File tmp=File.createTempFile("poster-",".tmp",cache);
                try(FileOutputStream out=new FileOutputStream(tmp)){frame.compress(Bitmap.CompressFormat.JPEG,85,out);}
                finally{frame.recycle();}
                if(!tmp.renameTo(picture))tmp.delete();
                if(picture.isFile())new File(cache,base+".jpg").delete();
            } finally {reader.release();}
        }
        return new WebResourceResponse("image/jpeg",null,new FileInputStream(picture));
    }

    static WebResourceResponse pdf(Context context,Uri source,String page) throws IOException {
        File asset=find(context,source);
        if(!asset.getName().toLowerCase(java.util.Locale.ROOT).endsWith(".pdf"))throw new IOException("Expected a PDF");
        try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(asset,ParcelFileDescriptor.MODE_READ_ONLY);
            PdfRenderer renderer=new PdfRenderer(fd)) {
            if(page==null) {
                StringBuilder html=new StringBuilder("<meta name='viewport' content='width=device-width'><style>body{margin:0;background:#14181c}img{width:100%;display:block;margin:0 0 6px}</style>");
                for(int i=0;i<renderer.getPageCount();i++) html.append("<img loading='lazy' alt='Page ").append(i+1).append("' src='/mobile-pdf?file=").append(Uri.encode(source.toString())).append("&amp;page=").append(i).append("'>");
                return new WebResourceResponse("text/html","UTF-8",new ByteArrayInputStream(html.toString().getBytes(StandardCharsets.UTF_8)));
            }
            try(PdfRenderer.Page p=renderer.openPage(Integer.parseInt(page))) {
                float scale=Math.min(1400f/p.getWidth(),2000f/p.getHeight());
                Bitmap bitmap=Bitmap.createBitmap(Math.max(1,(int)(p.getWidth()*scale)),Math.max(1,(int)(p.getHeight()*scale)),Bitmap.Config.ARGB_8888);
                bitmap.eraseColor(0xffffffff);
                p.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes);bitmap.recycle();
                return new WebResourceResponse("image/png",null,new ByteArrayInputStream(bytes.toByteArray()));
            }
        }
    }
}
