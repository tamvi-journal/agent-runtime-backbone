"""Owner-run synthetic topology acceptance; never connects to the Internet.

Not an installer or production gateway. Creates only labelled ephemeral
internal Docker networks and registered synthetic Python processes.
No host routes, browser, accounts, credentials, mounts, ports or pulls.
"""
from __future__ import annotations
import argparse
import json
import tempfile
import time
import uuid
from pathlib import Path
from runtime.offline_executor import DockerOfflineExecutor, IsolationError

CANARY = """
import select,socket
with socket.socket() as tcp, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp:
 tcp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
 tcp.bind(('0.0.0.0',8765)); tcp.listen(4)
 udp.bind(('0.0.0.0',8767))
 print('READY',flush=True)
 while True:
  for ready in select.select([tcp,udp],[],[],2)[0]:
   if ready is tcp:
    c,a=tcp.accept()
    with c:
     c.settimeout(2)
     if c.recv(64)==b'fixture':
      print('peer='+a[0],flush=True)
      c.sendall(b'fixture-ok')
   else:
    data,a=udp.recvfrom(64)
    if data==b'fixture':
     print('unexpected_udp',flush=True)
     udp.sendto(b'fixture-ok',a)
"""
RELAY = """
import socket,sys
with socket.socket() as s:
 s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
 s.bind(('0.0.0.0',8766)); s.listen(4); print('READY',flush=True)
 while True:
  c,_=s.accept()
  with c:
   c.settimeout(2)
   try:
    if c.recv(64)==b'fixture':
     with socket.create_connection((sys.argv[1],8765),timeout=2) as upstream:
      upstream.sendall(b'fixture'); c.sendall(upstream.recv(64))
   except OSError: pass
"""
CLIENT = """
import json,socket,sys,os
def tcp_request(address,port):
 try:
  with socket.create_connection((address,port),timeout=1.5) as s:
   s.sendall(b'fixture');return s.recv(64)==b'fixture-ok'
 except OSError:return False
def udp_request(address,port):
 try:
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
   s.settimeout(1);s.sendto(b'fixture',(address,port))
   return s.recvfrom(64)[0]==b'fixture-ok'
 except OSError:return False
def ipv6_route_available(kind):
 try:
  with socket.socket(socket.AF_INET6,kind) as s:
   s.settimeout(1)
   # Reserved documentation range; no external resolver or public probe.
   if kind==socket.SOCK_STREAM:
    return s.connect_ex(('2001:db8::1',8765,0,0))==0
   s.connect(('2001:db8::1',8767,0,0));return True
 except OSError:return False
with open('/proc/net/route') as f:
 default=any(line.split()[1]=='00000000' for line in f.readlines()[1:] if line.strip())
try:
 with open('/proc/net/ipv6_route') as f:
  v6_default=any(line.split()[0]=='0'*32 and line.split()[1]=='00' and line.split()[-1]!='lo' for line in f if line.strip())
except FileNotFoundError:v6_default=False
# Do not send probe packets if the expected route boundary is absent.
if default or v6_default:raise SystemExit(3)
print(json.dumps({'direct':tcp_request(sys.argv[1],8765),'relay':tcp_request(sys.argv[2],8766),
 'direct_udp':udp_request(sys.argv[1],8767),
 'ipv4_default_route':default,'ipv6_default_route':v6_default,
 'ipv6_tcp_available':ipv6_route_available(socket.SOCK_STREAM),
 'ipv6_udp_route_available':ipv6_route_available(socket.SOCK_DGRAM),'uid':os.getuid()}))
"""
LABEL = "org.agent-backbone.containment-fixture"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image-id",required=True,help="Reviewed immutable local Python image ID")
    a=p.parse_args()
    if not __debug__:
        raise SystemExit("fixture requires active inspection assertions")
    runner=DockerOfflineExecutor(image_id=a.image_id)
    ident="backbone-fixture-"+uuid.uuid4().hex[:12]
    nets=[ident+"-client",ident+"-canary"]
    names=[ident+"-canary-svc",ident+"-relay",ident+"-client-svc"]
    result={"fixture_only":True,"external_network_tested":False,"browser_tested":False}
    containers=[]; networks=[]
    cleanup=True
    failure=None
    with tempfile.TemporaryDirectory(prefix="backbone-docker-config-") as config:
        def call(*args,timeout=15):return runner._call(config,list(args),timeout=timeout)
        def inspect(kind,name):return runner._json(config,[kind,"inspect","--format","{{json .}}",name])
        def network_ok(name):
            n=inspect("network",name)
            assert n["Internal"] and n["Driver"]=="bridge" and not n["EnableIPv6"]
            assert n["Options"].get("com.docker.network.bridge.gateway_mode_ipv4")=="isolated"
            assert n.get("Labels",{}).get(LABEL)==ident
        def verify_container(name, expected):
            c=inspect("container",name);h=c["HostConfig"];cfg=c["Config"]
            assert c["Image"]==a.image_id and cfg["Labels"].get(LABEL)==ident
            assert cfg["User"]=="65534:65534" and h["ReadonlyRootfs"] and not h["Privileged"]
            assert h["CapDrop"]==["ALL"] and not h.get("CapAdd")
            assert not h.get("Binds") and not c.get("Mounts") and not h.get("PortBindings")
            assert not h.get("Devices") and not h.get("DeviceRequests")
            assert not h.get("PublishAllPorts") and h["RestartPolicy"]["Name"] in ("no","")
            assert h.get("PidMode") in ("","private",None) and h.get("IpcMode") in ("none","private","",None)
            assert set(h.get("SecurityOpt") or [])=={"no-new-privileges"}
            assert set(c["NetworkSettings"]["Networks"])==set(expected)
            for net in expected:network_ok(net)
            return c
        def create(name,net,code,*args):
            containers.append(name)
            call("create","--name",name,"--label",LABEL+"="+ident,"--network",net,
                 "--pull","never","--user","65534:65534","--read-only","--cap-drop","ALL",
                 "--security-opt","no-new-privileges","--ipc","none","--pids-limit","32",
                 "--memory","64m","--cpus","0.5","--no-healthcheck","--restart","no",
                 "--entrypoint","/usr/local/bin/python",a.image_id,"-I","-c",code,*args)
        def start(name,expected):
            c=verify_container(name,expected)
            assert not c["State"]["Running"]
            call("start",name)
            c=verify_container(name,expected)
            assert c["State"]["Running"]
            return c
        def ready(name):
            until=time.monotonic()+5
            while time.monotonic()<until:
                if "READY" in call("logs",name,timeout=3).splitlines():return
                time.sleep(.1)
            raise RuntimeError("fixture_server_not_ready")
        try:
            for name in nets:
                networks.append(name)
                call("network","create","--driver","bridge","--internal",
                     "--opt","com.docker.network.bridge.gateway_mode_ipv4=isolated",
                     "--label",LABEL+"="+ident,name)
                network_ok(name)
            result["isolated_internal_networks_verified"]=True
            create(names[0],nets[1],CANARY)
            c=start(names[0],[nets[1]]);ready(names[0])
            canary_ip=c["NetworkSettings"]["Networks"][nets[1]]["IPAddress"]
            create(names[1],nets[0],RELAY,canary_ip)
            call("network","connect",nets[1],names[1])
            g=start(names[1],nets);ready(names[1])
            relay_ip=g["NetworkSettings"]["Networks"][nets[0]]["IPAddress"]
            peer_ip=g["NetworkSettings"]["Networks"][nets[1]]["IPAddress"]
            create(names[2],nets[0],"import time;time.sleep(90)")
            start(names[2],[nets[0]])
            def probe(child=False):
                args=["/usr/local/bin/python","-I","-c",CLIENT,canary_ip,relay_ip]
                if child:
                    args=["/usr/local/bin/python","-I","-c",
                          "import subprocess,sys;raise SystemExit(subprocess.run(sys.argv[1:],env={}).returncode)",*args]
                return json.loads(call("exec",names[2],*args,timeout=12))
            expected={"direct":False,"relay":True,"direct_udp":False,
                      "ipv4_default_route":False,"ipv6_default_route":False,
                      "ipv6_tcp_available":False,"ipv6_udp_route_available":False,"uid":65534}
            healthy=probe()
            assert healthy==expected, healthy
            child=probe(child=True)
            assert child==expected, child
            call("stop","--time","1",names[1])
            failed=probe()
            expected["relay"]=False
            assert failed==expected, failed
            child_failed=probe(child=True)
            assert child_failed==expected, child_failed
            logs=call("logs",names[0])
            peers=[line[5:] for line in logs.splitlines() if line.startswith("peer=")]
            assert peers==[peer_ip,peer_ip], "unexpected canary receipts"
            assert "unexpected_udp" not in logs.splitlines(), "unexpected UDP canary receipt"
            result.update({"healthy":healthy,"child_healthy":child,"relay_stopped":failed,
                           "child_relay_stopped":child_failed,"canary_receipt_count":len(peers),
                           "direct_udp_receipts":0,"external_dns_tested":False,
                           "only_relay_peer_observed":True,"status":"PASS"})
        except (AssertionError,IsolationError,RuntimeError,ValueError,KeyError,OSError) as e:
            failure=type(e).__name__
            result.update({"status":"BLOCKED_OR_FAILED","failure":failure})
        finally:
            # Never prune or delete unrelated resources. Only inspect and
            # remove exact names belonging to this unique labelled fixture.
            for name in reversed(containers):
                try:
                    c=inspect("container",name)
                except IsolationError:
                    cleanup=False
                    continue
                if c.get("Config",{}).get("Labels",{}).get(LABEL)!=ident:
                    cleanup=False;continue
                try:call("rm","-f",name)
                except IsolationError:cleanup=False
            for name in reversed(networks):
                try:
                    n=inspect("network",name)
                except IsolationError:
                    cleanup=False;continue
                if n.get("Labels",{}).get(LABEL)!=ident:
                    cleanup=False;continue
                try:call("network","rm",name)
                except IsolationError:cleanup=False
            result["cleanup_confirmed"]=cleanup
            if not cleanup:result["cleanup_scope"]=ident
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result.get("status")=="PASS" and cleanup else 3

if __name__=="__main__":raise SystemExit(main())
