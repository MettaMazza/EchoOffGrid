package dev.echooffgrid.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.provider.MediaStore;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;

final class CaseExport {
    static String mime(String url) {
        String path=Uri.parse(url).getPath();
        if("/archive/backup".equals(path))return "application/octet-stream";
        if("/evidence.csv".equals(path))return "text/csv";
        return "application/zip";
    }
    static void copy(String url, String cookie, OutputStream out) throws IOException {
        HttpURLConnection conn=(HttpURLConnection)new URL(url).openConnection();
        conn.setInstanceFollowRedirects(false);
        conn.setRequestProperty("Cookie",cookie);
        conn.setRequestProperty("X-Echo-Export","1");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(120000);
        try {
            if(conn.getResponseCode()!=200 || !mime(url).equals(String.valueOf(conn.getContentType()).split(";",2)[0]))
                throw new IOException("Export unavailable");
            try(InputStream in=conn.getInputStream()){
                byte[] buf=new byte[65536];int n;long written=0;
                while((n=in.read(buf))!=-1){out.write(buf,0,n);written+=n;}
                if(written!=conn.getContentLengthLong())throw new IOException("Incomplete export");
            }
        } finally {conn.disconnect();}
    }
    static void download(Context context,String url,String cookie,String name) throws IOException {
        ContentValues values=new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME,name);
        values.put(MediaStore.Downloads.MIME_TYPE,mime(url));
        values.put(MediaStore.Downloads.IS_PENDING,1);
        Uri uri=context.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
        if(uri==null)throw new IOException("Downloads unavailable");
        try {
            try(OutputStream out=context.getContentResolver().openOutputStream(uri)){copy(url,cookie,out);}
            values.clear();values.put(MediaStore.Downloads.IS_PENDING,0);
            context.getContentResolver().update(uri,values,null,null);
        } catch(IOException|RuntimeException e){context.getContentResolver().delete(uri,null,null);throw e;}
    }
}
