"""Run with stdlib + openssl inside a disposable, network=none test container.
Synthetic keys never enter the host repo. No actual gateway or commerce site.
"""
import json,ssl,subprocess,threading,tempfile,unittest,os,socket,hashlib,time
from contextlib import contextmanager
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
from runtime.broker import BrokerConfig,BrokerError,LocalReadBroker
from runtime.instance import InstanceConfig
from runtime.service import AgentService
from runtime.adapters.gateway_server import create_gateway

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.server.requests.append(self.path)
        data=b'{"resource":"sample","value":42}'
        self.send_response(self.server.status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Location","https://192.0.2.123/never-follow")
        self.end_headers()
        self.wfile.write(data)

class TLSAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        def run(*args):
            subprocess.run(["openssl",*args],check=True,capture_output=True)
        def p(n):return str(cls.root/n)
        run("req","-x509","-newkey","rsa:2048","-nodes","-days","1","-subj","/CN=Fixture CA","-keyout",p("ca.key"),"-out",p("ca.crt"))
        run("req","-x509","-newkey","rsa:2048","-nodes","-days","1","-subj","/CN=Unrelated Fixture CA","-keyout",p("other-ca.key"),"-out",p("other-ca.crt"))
        for name,cn,ext in (("server","gateway.example.invalid","subjectAltName=DNS:gateway.example.invalid\nextendedKeyUsage=serverAuth\n"),("client","fixture-client","extendedKeyUsage=clientAuth\n")):
            run("req","-newkey","rsa:2048","-nodes","-subj","/CN="+cn,"-keyout",p(name+".key"),"-out",p(name+".csr"))
            (cls.root/(name+".ext")).write_text(ext)
            run("x509","-req","-in",p(name+".csr"),"-CA",p("ca.crt"),"-CAkey",p("ca.key"),"-CAcreateserial","-days","1","-extfile",p(name+".ext"),"-out",p(name+".crt"))
            (cls.root/(name+".key")).chmod(0o600)
        # Explicit historical dates, not wall-clock sleeps or near-expiry races.
        (cls.root/"index.txt").write_text("")
        (cls.root/"serial").write_text("1000\\n".replace("\\n","\n"))
        (cls.root/"issued").mkdir()
        (cls.root/"ca.cnf").write_text(f"""[ca]
default_ca=fixture
[fixture]
database={p('index.txt')}
serial={p('serial')}
new_certs_dir={p('issued')}
certificate={p('ca.crt')}
private_key={p('ca.key')}
default_md=sha256
policy=policy
[policy]
commonName=supplied
[server_ext]
subjectAltName=DNS:gateway.example.invalid
extendedKeyUsage=serverAuth
[client_ext]
extendedKeyUsage=clientAuth
""")
        for name in ("server","client"):
            run("ca","-batch","-config",p("ca.cnf"),"-in",p(name+".csr"),"-out",p("expired-"+name+".crt"),"-startdate","20000101000000Z","-enddate","20000102000000Z","-extensions",name+"_ext")

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        s=HTTPServer(("127.0.0.1",0),Handler)
        s.requests=[];s.status=200
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.verify_mode=ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=str(self.root/"ca.crt"))
        ctx.load_cert_chain(str(self.root/"server.crt"),str(self.root/"server.key"))
        s.socket=ctx.wrap_socket(s.socket,server_side=True)
        self.server=s
        self.thread=threading.Thread(target=s.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def config(self,name="gateway.example.invalid"):
        r=self.root
        return BrokerConfig(self.server.server_port,frozenset({"sample"}),"mutual_tls_gateway",name,"127.0.0.1",
            str(r/"ca.crt"),str(r/"client.crt"),str(r/"client.key"))

    def test_pinned_mtls(self):
        self.assertEqual(json.loads(LocalReadBroker(self.config()).read("sample"))["value"],42)
        self.assertEqual(self.server.requests,["/v1/read/sample"])

    def test_wrong_name(self):
        with self.assertRaises(BrokerError):
            LocalReadBroker(self.config("wrong.example.invalid")).read("sample")
        self.assertEqual(self.server.requests,[])

    def test_no_client_cert(self):
        ctx=ssl.create_default_context(cafile=str(self.root/"ca.crt"))
        with self.assertRaises((ssl.SSLError,OSError)):
            with socket.create_connection(("127.0.0.1",self.server.server_port),2) as raw:
                with ctx.wrap_socket(raw,server_hostname="gateway.example.invalid") as s:
                    s.sendall(b"GET /v1/read/sample HTTP/1.1\r\nHost: gateway.example.invalid\r\n\r\n")
                    self.assertTrue(s.recv(4096))
        self.assertEqual(self.server.requests,[])

    def test_redirect(self):
        self.server.status=302
        with self.assertRaises(BrokerError):
            LocalReadBroker(self.config()).read("sample")
        self.assertEqual(self.server.requests,["/v1/read/sample"])

    def test_unregistered_resource(self):
        with self.assertRaises(BrokerError):
            LocalReadBroker(self.config()).read("https://example.invalid")
        self.assertEqual(self.server.requests,[])

    def test_gateway_down_no_fallback(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
            cfg=self.config()
            cfg=BrokerConfig(port,cfg.resources,cfg.mode,cfg.server_name,cfg.pinned_ip,cfg.ca_file,cfg.client_cert,cfg.client_key)
            with self.assertRaises(BrokerError):LocalReadBroker(cfg).read("sample")
        self.assertEqual(self.server.requests,[])

    def test_end_to_end_candidate(self):
        cfg=self.config()
        data={"instance_id":"fixture-reader","role":{"role":"reader","operations":["read_registered_resource"],"network":"brokered_read","external_mutation":False},"image_id":None,
              "broker":{"mode":cfg.mode,"port":cfg.port,"resources":["sample"],"server_name":cfg.server_name,"pinned_ip":cfg.pinned_ip,"ca_file":cfg.ca_file,"client_cert":cfg.client_cert,"client_key":cfg.client_key}}
        service=AgentService(InstanceConfig.from_mapping(data))
        result=service.invoke("read_registered_resource",{"resource":"sample"})
        self.assertEqual(result["status"],"needs_review")
        self.assertFalse(result["eligible_for_release"])

    def test_reference_gateway_client_scope(self):
        r=self.root
        peer=ssl.PEM_cert_to_DER_cert((r/"client.crt").read_text())
        fp=hashlib.sha256(peer).hexdigest()
        calls=[]
        def handler():
            calls.append(1)
            return 42
        server=create_gateway(bind=("127.0.0.1",0),ca=r/"ca.crt",cert=r/"server.crt",key=r/"server.key",
            principals={fp:frozenset({"sample"})},handlers={"sample":handler,"other":handler})
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cfg=self.config()
            b=LocalReadBroker(BrokerConfig(server.server_port,frozenset({"sample","other"}),cfg.mode,
                cfg.server_name,cfg.pinned_ip,cfg.ca_file,cfg.client_cert,cfg.client_key))
            self.assertEqual(json.loads(b.read("sample"))["value"],42)
            with self.assertRaises(BrokerError):b.read("other")
            self.assertEqual(calls,[1])
        finally:server.shutdown();server.server_close();thread.join()

    def test_reference_gateway_unknown_principal(self):
        r=self.root
        calls=[]
        server=create_gateway(bind=("127.0.0.1",0),ca=r/"ca.crt",cert=r/"server.crt",key=r/"server.key",
            principals={"0"*64:frozenset({"sample"})},handlers={"sample":lambda:calls.append(1) or 42})
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cfg=self.config()
            b=LocalReadBroker(BrokerConfig(server.server_port,cfg.resources,cfg.mode,cfg.server_name,
                cfg.pinned_ip,cfg.ca_file,cfg.client_cert,cfg.client_key))
            with self.assertRaises(BrokerError):b.read("sample")
            self.assertEqual(calls,[])
        finally:server.shutdown();server.server_close();thread.join()

    @contextmanager
    def reference(self,*,cert="server.crt",key="server.key",audit=None,**kwargs):
        r=self.root
        peer=ssl.PEM_cert_to_DER_cert((r/"client.crt").read_text())
        fp=hashlib.sha256(peer).hexdigest()
        events=[];calls=[]
        def handler():
            calls.append("sample");return 42
        server=create_gateway(bind=("127.0.0.1",0),ca=r/"ca.crt",cert=r/cert,key=r/key,
            principals={fp:frozenset({"sample"})},handlers={"sample":handler,"other":handler},
            audit=events.append if audit is None else audit,**kwargs)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cfg=self.config()
        cfg=BrokerConfig(server.server_port,frozenset({"sample","other"}),cfg.mode,
            cfg.server_name,cfg.pinned_ip,cfg.ca_file,cfg.client_cert,cfg.client_key)
        try:yield server,cfg,events,calls,fp
        finally:server.shutdown();server.server_close();thread.join()

    def test_reference_silent_peer_does_not_starve_valid_clients(self):
        with self.reference(request_deadline=2.5) as (server,cfg,events,calls,fp):
            with socket.create_connection(("127.0.0.1",server.server_port),1):
                time.sleep(.05)
                for i in range(5):
                    self.assertEqual(json.loads(LocalReadBroker(cfg).read("sample"))["value"],42)
            self.assertEqual(calls,["sample"]*5)

    def test_reference_total_handshake_deadline_and_slot_recovery(self):
        with self.reference(max_connections=2,max_per_source=1,request_deadline=1.0) as (server,cfg,events,calls,fp):
            started=time.monotonic()
            with socket.create_connection(("127.0.0.1",server.server_port),1) as raw:
                raw.settimeout(2.2)
                time.sleep(.08)
                with self.assertRaises(BrokerError):LocalReadBroker(cfg).read("sample")
                self.assertEqual(raw.recv(1),b"")
            self.assertLess(time.monotonic()-started,2.3)
            deadline=time.monotonic()+.5
            while time.monotonic()<deadline and (server._active or not any(e["reason"]=="request_deadline" for e in events)):time.sleep(.02)
            self.assertTrue(any(e["reason"]=="connection_limit" for e in events))
            self.assertTrue(any(e["reason"]=="request_deadline" for e in events))
            self.assertEqual(json.loads(LocalReadBroker(cfg).read("sample"))["value"],42)

    def test_reference_partial_http_deadline(self):
        with self.reference(request_deadline=1.2) as (server,cfg,events,calls,fp):
            ctx=ssl.create_default_context(cafile=cfg.ca_file)
            ctx.load_cert_chain(cfg.client_cert,cfg.client_key)
            start=time.monotonic()
            with socket.create_connection(("127.0.0.1",server.server_port),1) as raw:
                with ctx.wrap_socket(raw,server_hostname=cfg.server_name) as s:
                    s.settimeout(2.0)
                    s.sendall(b"GET /v1/read/sample HTTP/1.1\r\nHost: gateway.example.invalid\r\n")
                    try: self.assertEqual(s.recv(1),b"")
                    except (ssl.SSLError,ConnectionResetError):pass
            self.assertLess(time.monotonic()-start,2.2)
            self.assertEqual(calls,[])

    def test_reference_no_client_cert(self):
        with self.reference() as (server,cfg,events,calls,fp):
            ctx=ssl.create_default_context(cafile=cfg.ca_file)
            with self.assertRaises((ssl.SSLError,OSError)):
                with socket.create_connection(("127.0.0.1",server.server_port),2) as raw:
                    with ctx.wrap_socket(raw,server_hostname=cfg.server_name) as s:
                        s.sendall(b"GET /v1/read/sample HTTP/1.1\r\nHost: gateway.example.invalid\r\n\r\n")
                        data=s.recv(4096)
                        if not data:raise OSError("closed")
            self.assertEqual(calls,[])

    def test_reference_wrong_ca(self):
        from dataclasses import replace
        with self.reference() as (server,cfg,events,calls,fp):
            with self.assertRaises(BrokerError):
                LocalReadBroker(replace(cfg,ca_file=str(self.root/"other-ca.crt"))).read("sample")
            self.assertEqual(calls,[])

    def test_reference_expired_server(self):
        with self.reference(cert="expired-server.crt") as (server,cfg,events,calls,fp):
            with self.assertRaises(BrokerError):LocalReadBroker(cfg).read("sample")
            self.assertEqual(calls,[])

    def test_reference_expired_client(self):
        from dataclasses import replace
        with self.reference() as (server,cfg,events,calls,fp):
            with self.assertRaises(BrokerError):
                LocalReadBroker(replace(cfg,client_cert=str(self.root/"expired-client.crt"))).read("sample")
            self.assertEqual(calls,[])

    def test_reference_denial_audit_privacy(self):
        with self.reference() as (server,cfg,events,calls,fp):
            with self.assertRaises(BrokerError):LocalReadBroker(cfg).read("other")
            self.assertEqual(calls,[])
            self.assertTrue(any(e["code"]==403 and e["principal"]==fp and e["resource"]=="other" for e in events))
            self.assertTrue(all(set(e)=={"event","at","code","reason","principal","resource"} for e in events))
            self.assertNotIn("127.0.0.1",repr(events))

    def test_reference_audit_unavailable_blocks_handler(self):
        def broken(_):raise RuntimeError("fixture sink unavailable")
        with self.reference(audit=broken) as (server,cfg,events,calls,fp):
            with self.assertRaises(BrokerError):LocalReadBroker(cfg).read("sample")
            self.assertEqual(calls,[])

    def test_reference_transport_denial_audit_bounded(self):
        with self.reference(max_connections=2,max_per_source=1,request_deadline=2.5,
                            transport_audit_interval=5.0) as (server,cfg,events,calls,fp):
            with socket.create_connection(("127.0.0.1",server.server_port),1):
                stop=time.monotonic()+1
                while server._active!=1 and time.monotonic()<stop:time.sleep(.01)
                self.assertEqual(server._active,1)
                for _ in range(30):
                    with socket.create_connection(("127.0.0.1",server.server_port),1) as raw:
                        raw.settimeout(1)
                        self.assertEqual(raw.recv(1),b"")
                self.assertEqual(len([e for e in events if e["reason"]=="connection_limit"]),1)
            stop=time.monotonic()+2
            while server._active and time.monotonic()<stop:time.sleep(.01)
            self.assertEqual(server._active,0)
            self.assertEqual(json.loads(LocalReadBroker(cfg).read("sample"))["value"],42)
        denied=[e for e in events if e["reason"]=="connection_limit"]
        self.assertEqual(len(denied),2)
        self.assertEqual(sum(e["count"] for e in denied),30)
        self.assertTrue(all(e["principal"] is None and e["resource"] is None for e in denied))
        self.assertEqual(calls,["sample"])

if __name__=="__main__":
    unittest.main(verbosity=2)
