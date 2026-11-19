package dev.echooffgrid.mobile;

import android.content.*;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;

/** Grants the selected application read access to one imported file. */
public class SharedFile extends ContentProvider {
    public boolean onCreate(){return true;}
    private File resolve(Uri uri) throws IOException {
        String key=uri.getLastPathSegment();
        if(uri.getPathSegments().size()!=1 || key==null || !key.matches("(?:personal-)?[0-9a-f]{64}"))
            throw new FileNotFoundException();
        return LocalMedia.find(getContext(),Uri.parse("/content-file/"+key));
    }
    public String getType(Uri uri){
        try{
            String name=resolve(uri).getName();
            String mime=android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substring(name.lastIndexOf('.')+1));
            return mime==null?"application/octet-stream":mime;
        }catch(IOException e){return "application/octet-stream";}
    }
    public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if(!"r".equals(mode))throw new FileNotFoundException();
        try{return ParcelFileDescriptor.open(resolve(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
        catch(IOException e){throw new FileNotFoundException();}
    }
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
        String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
        MatrixCursor result=new MatrixCursor(cols);
        try{
            File file=resolve(uri);MatrixCursor.RowBuilder row=result.newRow();
            for(String col:cols) row.add(col.equals(OpenableColumns.DISPLAY_NAME)?file.getName():col.equals(OpenableColumns.SIZE)?file.length():null);
        }catch(IOException ignored){}
        return result;
    }
    public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
