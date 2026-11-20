package dev.echooffgrid.mobile;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
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
            try(SQLiteDatabase db=SQLiteDatabase.openDatabase(new File(root,"archive.sqlite3").toString(),null,SQLiteDatabase.OPEN_READONLY);
                Cursor c=db.rawQuery("SELECT coalesce((SELECT filename FROM discovery_file WHERE id=? ORDER BY sequence LIMIT 1 OFFSET ?),filename) FROM discovery_item WHERE id=?",
                    new String[]{key,String.valueOf(index),key})) {
                if(!c.moveToFirst() || c.isNull(0))throw new IOException("Missing download");
                asset=new File(base,c.getString(0));
            }
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

    static WebResourceResponse poster(Context context,Uri request) throws IOException {
        File video=find(context,request.buildUpon().encodedPath(request.getEncodedPath().replace("/content-poster/","/content-file/")).build());
        File cache=new File(context.getCacheDir(),"posters");
        cache.mkdirs();
        File picture=new File(cache,video.getName()+"-"+video.lastModified()+".jpg");
        if(!picture.isFile()) {
            android.media.MediaMetadataRetriever reader=new android.media.MediaMetadataRetriever();
            try {
                reader.setDataSource(video.toString());
                Bitmap frame=reader.getScaledFrameAtTime(1500000,android.media.MediaMetadataRetriever.OPTION_CLOSEST_SYNC,640,360);
                if(frame==null) throw new IOException("No video frame available");
                File tmp=File.createTempFile("poster-",".tmp",cache);
                try(FileOutputStream out=new FileOutputStream(tmp)){frame.compress(Bitmap.CompressFormat.JPEG,85,out);}
                finally{frame.recycle();}
                if(!tmp.renameTo(picture))tmp.delete();
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
