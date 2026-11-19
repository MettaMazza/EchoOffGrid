"""Loopback CONNECT listener for the native WebViews. All upstream sockets use Tor."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import ipaddress
import re
import select
import socket
from threading import Thread

def receive(stream,count):
    data=bytearray()
    while len(data)<count:
        chunk=stream.recv(count-len(data))
        if not chunk:raise OSError("Tor closed the socket")
        data.extend(chunk)
    return bytes(data)

def through_tor(path,host):
    stream=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        stream.settimeout(35)
        stream.connect(path)
        stream.sendall(b"\x05\x01\x00")
        if receive(stream,2)!=b"\x05\x00":raise OSError("SOCKS negotiation failed")
        name=host.encode("idna")
        if len(name)>253:raise ValueError("Invalid hostname")
        stream.sendall(b"\x05\x01\x00\x03"+bytes([len(name)])+name+b"\x01\xbb")
        v,reply,_,kind=receive(stream,4)
        if v!=5 or reply:raise OSError("Exit unavailable")
        size=receive(stream,1)[0] if kind==3 else {1:4,4:16}[kind]
        receive(stream,size+2)
        return stream
    except BaseException:
        stream.close()
        raise

class Tunnel(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_CONNECT(self):
        host,sep,port=self.path.rpartition(":")
        if port!="443" or not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}",host) or "." not in host or host.rstrip(".").lower().endswith((".localhost",".local",".internal")):
            self.send_error(403);return
        try:
            ip=ipaddress.ip_address(host)
        except ValueError:ip=None
        if ip and not ip.is_global:self.send_error(403);return
        try:
            upstream=through_tor(self.server.tor_path,host)
        except (OSError,ValueError,KeyError):
            self.send_error(502);return
        with upstream:
            self.send_response_only(200,"Connection established");self.end_headers()
            self.connection.settimeout(30)
            try:
                streams=[self.connection,upstream]
                while not self.server.closed:
                    readable,_,_=select.select(streams,[],[],5)
                    for src in readable:
                        data=src.recv(65536)
                        if not data:return
                        (upstream if src is self.connection else self.connection).sendall(data)
            except OSError:pass

class BrowserProxy(ThreadingHTTPServer):
    def __init__(self,tor_path):
        self.tor_path=tor_path
        self.closed=False
        super().__init__(("127.0.0.1",0),Tunnel)
        Thread(target=self.serve_forever,daemon=True).start()

    def stop(self):
        self.closed=True
        self.shutdown()
        self.server_close()
