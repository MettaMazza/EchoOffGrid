package dev.echooffgrid.mobile;

import android.content.Context;
import android.net.nsd.*;
import java.io.*;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

class Bonjour {
    static NsdManager.RegistrationListener advertise(Context context) {
        try {
            File token=new File(context.getFilesDir(),"paired-device/token");
            if(!token.isFile())return null;
            byte[] credential=java.nio.file.Files.readAllBytes(token.toPath());
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(credential);
            StringBuilder name=new StringBuilder("EchoOffGrid-");
            for(int i=0;i<6;i++)name.append(String.format(java.util.Locale.ROOT,"%02x",digest[i]));
            NsdServiceInfo info=new NsdServiceInfo();
            info.setServiceName(name.toString());info.setServiceType("_echooffgrid._tcp.");info.setPort(38779);
            NsdManager.RegistrationListener listener=new NsdManager.RegistrationListener() {
                public void onServiceRegistered(NsdServiceInfo info){}
                public void onRegistrationFailed(NsdServiceInfo info,int error){android.util.Log.w("EchoOffGrid","LAN discovery unavailable");}
                public void onServiceUnregistered(NsdServiceInfo info){}
                public void onUnregistrationFailed(NsdServiceInfo info,int error){}
            };
            context.getSystemService(NsdManager.class).registerService(info,NsdManager.PROTOCOL_DNS_SD,listener);
            return listener;
        } catch(Exception e){return null;}
    }
}
