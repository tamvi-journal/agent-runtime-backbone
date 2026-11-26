"""Bounded reference mTLS read gateway; not a production perimeter.

Only trusted, reviewed callbacks may be registered. Socket deadlines cannot
cancel arbitrary Python handler computation. Production handlers need their
own deadline, resource budgets and an independently controlled egress policy.
"""
from __future__ import annotations
from collections.abc import Callable,Mapping
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import hashlib,json,re,ssl,socket,threading,time,logging
from runtime.broker import MAX_RESPONSE,_RESOURCE
from runtime.adapters.transport_audit import TransportAuditBudget

_FP=re.compile(r"[a-f0-9]{64}")
_LOG=logging.getLogger("local_agent_runtime.gateway")

def create_gateway(*, bind: tuple[str,int], ca: Path, cert: Path, key: Path,
                   principals: Mapping[str,frozenset[str]],
                   handlers: Mapping[str,Callable[[],int|str]],
                   max_connections: int=16, max_per_source: int=4,
                   request_deadline: float=3.0,
                   audit: Callable[[dict],None]|None=None,
                   transport_audit_interval: float=5.0) -> ThreadingHTTPServer:
    registry=dict(handlers);permissions=dict(principals)
    if not registry or any(not isinstance(k,str) or not _RESOURCE.fullmatch(k) or not callable(v) for k,v in registry.items()):
        raise ValueError("invalid_handler_registry")
    if not permissions or any(not isinstance(k,str) or not _FP.fullmatch(k) or not isinstance(v,frozenset) or not v<=registry.keys() for k,v in permissions.items()):
        raise ValueError("invalid_client_registry")
    if (type(max_connections) is not int or not 1<=max_connections<=128
        or type(max_per_source) is not int or not 1<=max_per_source<=max_connections
        or type(request_deadline) not in (int,float) or not 0.1<=request_deadline<=30):
        raise ValueError("invalid_gateway_limits")
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.verify_mode=ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca))
    context.load_cert_chain(certfile=str(cert),keyfile=str(key))

    def emit(code,reason,principal=None,resource=None):
        # No source address, raw path, header, body, exception or unregistered
        # resource name is persisted. The certificate fingerprint is an
        # authenticated pseudonymous principal, not a secret.
        event={"event":"gateway_request","at":int(time.time()),"code":code,
               "reason":reason,"principal":principal if principal and _FP.fullmatch(principal) else None,
               "resource":resource if resource in registry else None}
        return write_event(event)

    def write_event(event):
        try:
            if audit is not None:
                audit(dict(event))
            else:
                _LOG.warning("%s",json.dumps(event,separators=(",",":")))
        except Exception:
            # An unavailable request audit sink must not silently permit a handler.
            return False
        return True

    transport_audit=TransportAuditBudget(write_event,interval=transport_audit_interval)

    class Handler(BaseHTTPRequestHandler):
        protocol_version="HTTP/1.0"
        def log_message(self,*args): pass

        def send_error(self,code,message=None,explain=None):
            # Covers unsupported methods and parse failures as well as denies.
            # No reflected attacker-controlled diagnostic text.
            emit(code,"request_denied",getattr(self,"principal",None),getattr(self,"resource",None))
            super().send_error(code)

        def do_GET(self):
            self.close_connection=True
            peer=self.connection.getpeercert(binary_form=True)
            self.principal=hashlib.sha256(peer).hexdigest() if peer else None
            prefix="/v1/read/"
            resource=self.path[len(prefix):] if self.path.startswith(prefix) else ""
            self.resource=resource if resource in registry else None
            lengths=self.headers.get_all("Content-Length") or []
            if self.headers.get_all("Transfer-Encoding") or lengths not in ([],["0"]):
                self.send_error(400);return
            if not _RESOURCE.fullmatch(resource):
                self.send_error(404);return
            if resource not in permissions.get(self.principal,frozenset()):
                self.send_error(403);return
            if time.monotonic()>=self.connection._lar_deadline:
                self.send_error(408);return
            # Reserve an audit event before trusted callback dispatch.
            if not emit(0,"authorized_dispatch",self.principal,resource):
                self.send_error(503);return
            try:
                value=registry[resource]()
                if type(value) not in (int,str) or isinstance(value,str) and len(value)>4096:
                    raise ValueError
                data=json.dumps({"resource":resource,"value":value},ensure_ascii=True).encode()
                if len(data)>MAX_RESPONSE: raise ValueError
            except Exception:
                self.send_error(502);return
            if time.monotonic()>=self.connection._lar_deadline:
                self.send_error(504);return
            if not emit(200,"response_ready",self.principal,resource):
                self.send_error(503);return
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Connection","close")
            self.end_headers();self.wfile.write(data)

    class TLSServer(ThreadingHTTPServer):
        daemon_threads=False
        block_on_close=True
        request_queue_size=32

        def __init__(self,*args):
            self._gate=threading.Lock()
            self._sources={}
            self._active=0
            self._accepted={}
            super().__init__(*args)

        def get_request(self):
            # Accept only; TLS handshake must not block the accept loop.
            raw,addr=super().get_request()
            return raw,addr

        def process_request(self,request,client_address):
            source=client_address[0]  # memory only; no address in audit output
            with self._gate:
                if self._active>=max_connections or self._sources.get(source,0)>=max_per_source:
                    admitted=False
                else:
                    admitted=True
                    self._active+=1
                    self._sources[source]=self._sources.get(source,0)+1
                    self._accepted[request]=time.monotonic()
            if not admitted:
                self.shutdown_request(request)
                transport_audit.record("connection_limit")
                return
            try:
                super().process_request(request,client_address)
            except BaseException:
                self._release(request,source)
                self.shutdown_request(request)
                raise

        def _release(self,request,source):
            with self._gate:
                self._accepted.pop(request,None)
                self._active-=1
                n=self._sources[source]-1
                if n:self._sources[source]=n
                else:self._sources.pop(source,None)

        def process_request_thread(self,request,client_address):
            source=client_address[0]
            tls=None; alarm=None; expired=threading.Event(); start=time.monotonic()
            try:
                with self._gate:
                    start=self._accepted[request]
                remaining=request_deadline-(time.monotonic()-start)
                if remaining<=0:
                    transport_audit.record("request_deadline");return
                request.settimeout(remaining)
                tls=context.wrap_socket(request,server_side=True,do_handshake_on_connect=False)
                tls._lar_deadline=start+request_deadline
                def abort():
                    expired.set()
                    try:tls.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                # One wall-clock budget from admission through handshake and
                # request/response, not a new timeout per read.
                alarm=threading.Timer(max(0,request_deadline-(time.monotonic()-start)),abort)
                alarm.daemon=True;alarm.start()
                tls.do_handshake()
                if expired.is_set():
                    return
                self.finish_request(tls,client_address)
            except (OSError,ValueError) as exc:
                if isinstance(exc,TimeoutError) or time.monotonic()>=start+request_deadline:
                    expired.set()
                elif not expired.is_set():
                    transport_audit.record("tls_or_transport_failed")
            except Exception:
                transport_audit.record("gateway_internal_error")
            finally:
                if alarm is not None:alarm.cancel()
                if expired.is_set():transport_audit.record("request_deadline")
                try:self.shutdown_request(tls if tls is not None else request)
                finally:self._release(request,source)

        def service_actions(self):
            transport_audit.flush()
            super().service_actions()

        def server_close(self):
            # ThreadingHTTPServer joins admitted workers before final flush.
            super().server_close()
            transport_audit.flush(force=True)

        @property
        def transport_audit_sink_failures(self):
            return transport_audit.sink_failures

        def handle_error(self,request,client_address):
            transport_audit.record("gateway_internal_error")
    return TLSServer(bind,Handler)
