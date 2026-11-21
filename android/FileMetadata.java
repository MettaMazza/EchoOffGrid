package dev.echooffgrid.mobile;

import android.content.Context;
import java.net.HttpURLConnection;
import android.content.pm.PackageInfo;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import java.io.*;

final class FileMetadata {
    static void read(Context context,String id) throws Exception {
        File file=LocalMedia.find(context,Uri.parse("/content-file/"+id));
        String title=null;
        byte[] artwork=null;
        if(file.getName().endsWith(".apk")){
            PackageInfo info=context.getPackageManager().getPackageArchiveInfo(file.getPath(),0);
            if(info!=null && info.applicationInfo!=null){
                info.applicationInfo.sourceDir=file.getPath();info.applicationInfo.publicSourceDir=file.getPath();
                title=info.applicationInfo.loadLabel(context.getPackageManager()).toString();
                if(info.applicationInfo.icon!=0){
                    Drawable icon=info.applicationInfo.loadIcon(context.getPackageManager());
                    Bitmap bitmap=Bitmap.createBitmap(256,256,Bitmap.Config.ARGB_8888);
                    icon.setBounds(0,0,256,256);icon.draw(new Canvas(bitmap));
                    ByteArrayOutputStream bytes=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes);
                    artwork=bytes.toByteArray();bitmap.recycle();
                }
            }
        } else if(file.getName().matches(".*\\.(mp3|ogg|oga|m4a|flac|opus|wav|aac|mp4|mov|mkv|webm|m4v|ogv)")){
            MediaMetadataRetriever reader=new MediaMetadataRetriever();
            try{
                reader.setDataSource(file.getPath());
                title=reader.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE);
                artwork=reader.getEmbeddedPicture();
            }finally{reader.release();}
        }
        if(artwork!=null && artwork.length<=8*1024*1024){
            File temp=File.createTempFile(".metadata-",".tmp",file.getParentFile());
            try{
                try(FileOutputStream out=new FileOutputStream(temp)){out.write(artwork);}
                android.system.Os.rename(temp.getPath(),new File(file.getParentFile(),id+".cover").getPath());
            }finally{temp.delete();}
        }
        if(title!=null && !title.trim().isEmpty()){
            HttpURLConnection c=Main.connection(context,"/mobile-file-title");
            c.setRequestMethod("POST");c.setRequestProperty("X-Echo-Native","1");c.setDoOutput(true);
            try{
                byte[] data=new org.json.JSONObject().put("id",id).put("title",title.substring(0,Math.min(400,title.length()))).toString().getBytes("UTF-8");
                c.setFixedLengthStreamingMode(data.length);
                try(OutputStream out=c.getOutputStream()){out.write(data);}
                if(c.getResponseCode()!=204)throw new IOException("Could not save media title");
            }finally{c.disconnect();}
        }
    }
}
