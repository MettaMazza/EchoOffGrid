package dev.echooffgrid.mobile;

import android.net.VpnService;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Only the bundled Tor process receives the credential for this VPN-exempt relay. */
final class TorUplink implements AutoCloseable {
    private final VpnService vpn;
    final ServerSocket listener;
    final String credential = "echo:" + UUID.randomUUID();
    private final Set<Socket> sockets = ConcurrentHashMap.newKeySet();
    private final ExecutorService workers = Executors.newCachedThreadPool();

    TorUplink(VpnService vpn) throws IOException {
        this.vpn = vpn;
        listener = new ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"));
        workers.execute(() -> {
            while (!listener.isClosed()) {
                try {
                    Socket client = listener.accept();
                    sockets.add(client);
                    workers.execute(() -> relay(client));
                } catch (IOException | RejectedExecutionException closed) { break; }
            }
        });
    }

    private void relay(Socket client) {
        try (Socket local = client; Socket upstream = new Socket()) {
            sockets.add(upstream);
            try {
                local.setSoTimeout(10000);
                InputStream input = local.getInputStream();
                ByteArrayOutputStream header = new ByteArrayOutputStream();
                int tail = 0;
                while (tail != 0x0d0a0d0a) {
                    int b = input.read();
                    if (b < 0 || header.size() >= 4096) return;
                    tail = (tail << 8) | b;
                    header.write(b);
                }
                String[] lines = header.toString("US-ASCII").split("\r\n");
                String auth = "Basic " + Base64.getEncoder().encodeToString(credential.getBytes(StandardCharsets.US_ASCII));
                boolean allowed = false;
                for (String line : lines) {
                    int split = line.indexOf(':');
                    if (split > 0 && line.substring(0, split).equalsIgnoreCase("Proxy-Authorization")) {
                        allowed = MessageDigest.isEqual(auth.getBytes(StandardCharsets.US_ASCII),
                                line.substring(split + 1).trim().getBytes(StandardCharsets.US_ASCII));
                    }
                }
                if (!allowed || !lines[0].startsWith("CONNECT ")) throw new IOException("Relay handshake rejected");
                URI endpoint = URI.create("https://" + lines[0].split(" ")[1]);
                String host = endpoint.getHost();
                if (host == null || !(host.matches("[0-9.]+") || host.matches("\\[[a-fA-F0-9:]+\\]"))) return;
                InetAddress ip = InetAddress.getByName(host);
                if (ip.isLoopbackAddress() || ip.isAnyLocalAddress() || ip.isLinkLocalAddress() || ip.isSiteLocalAddress()) return;
                // Materialise the socket descriptor before asking Android to exempt it.
                upstream.bind(new InetSocketAddress(0));
                if (!vpn.protect(upstream)) throw new IOException("Cannot protect the Tor relay socket");
                upstream.connect(new InetSocketAddress(ip, endpoint.getPort()), 20000);
                local.getOutputStream().write("HTTP/1.0 200 OK\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
                local.setSoTimeout(0);
                workers.execute(() -> pump(local, upstream));
                pump(upstream, local);
            } finally { sockets.remove(upstream); }
        } catch (IOException | RuntimeException failure) {
            android.util.Log.w("EchoVpn", "Relay connection failed ("+failure.getClass().getSimpleName()+")");
        } finally { sockets.remove(client); }
    }

    private static void pump(Socket source, Socket target) {
        byte[] chunk = new byte[16384];
        try {
            int n;
            while ((n = source.getInputStream().read(chunk)) != -1) target.getOutputStream().write(chunk, 0, n);
            target.shutdownOutput();
        } catch (IOException ignored) { }
    }

    public void close() {
        try { listener.close(); } catch (IOException ignored) { }
        for (Socket socket : sockets) try { socket.close(); } catch (IOException ignored) { }
        workers.shutdownNow();
    }
}
