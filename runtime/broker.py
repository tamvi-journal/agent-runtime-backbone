"""Trusted connector boundary: only the owner-configured gateway may be dialed.

The separate gateway is a trust root. This module does not attest its egress,
proxy, or authorization. Remote use requires owner-approved gateway deployment.
Both plain synthetic loopback and pinned mutual TLS transports are supported.
"""
from __future__ import annotations
from runtime.strict_json import loads as strict_loads
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from collections.abc import Mapping
import json
import re
import socket
import ipaddress
import ssl
import os
import stat
from pathlib import Path
import time
import threading

_RESOURCE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
MAX_RESPONSE = 16384
_HOST=re.compile(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")

class BrokerError(RuntimeError):
    pass

def _owner_file(path: str, secret: bool = False):
    if not isinstance(path,str) or not Path(path).is_absolute():
        raise ValueError("absolute_credential_path_required")
    p=Path(path)
    s=p.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1
            or s.st_mode & (0o077 if secret else 0o022)):
        raise ValueError("unsafe_credential_file")
    return str(p)

@dataclass(frozen=True)
class BrokerConfig:
    port: int
    resources: frozenset[str]
    mode: str = "synthetic_loopback"
    server_name: str | None = None
    pinned_ip: str | None = None
    ca_file: str | None = None
    client_cert: str | None = None
    client_key: str | None = None

    def __post_init__(self):
        if (type(self.port) is not int or not 1024 <= self.port <= 65535
                or self.mode not in {"synthetic_loopback","mutual_tls_gateway"}
                or not isinstance(self.resources,frozenset) or not self.resources
                or any(not isinstance(x,str) or not _RESOURCE.fullmatch(x) for x in self.resources)):
            raise ValueError("invalid_broker_config")
        fields=(self.server_name,self.pinned_ip,self.ca_file,self.client_cert,self.client_key)
        if self.mode=="synthetic_loopback":
            if any(v is not None for v in fields):
                raise ValueError("unexpected_tls_config")
            return
        if not all(isinstance(v,str) and v for v in fields):
            raise ValueError("tls_configuration_required")
        if not _HOST.fullmatch(self.server_name) or ".." in self.server_name:
            raise ValueError("invalid_gateway_name")
        addr=ipaddress.ip_address(self.pinned_ip)
        if addr.is_unspecified or addr.is_multicast or addr.is_link_local or "%" in self.pinned_ip:
            raise ValueError("invalid_gateway_ip")
        _owner_file(self.ca_file)
        _owner_file(self.client_cert)
        _owner_file(self.client_key,secret=True)

    @classmethod
    def from_mapping(cls,data: Mapping):
        if not isinstance(data,Mapping):
            raise ValueError("invalid_broker_fields")
        mode=data.get("mode")
        base={"port","resources","mode"}
        fields={"server_name","pinned_ip","ca_file","client_cert","client_key"}
        if set(data)!=(base|fields if mode=="mutual_tls_gateway" else base):
            raise ValueError("invalid_broker_fields")
        res=data["resources"]
        if not isinstance(res,list) or any(not isinstance(x,str) for x in res):
            raise ValueError("invalid_resources")
        extra={k:data[k] for k in fields} if mode=="mutual_tls_gateway" else {}
        return cls(data["port"],frozenset(res),mode,**extra)

class _PinnedHTTPS(HTTPSConnection):
    def __init__(self,cfg: BrokerConfig):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cafile=_owner_file(cfg.ca_file))
        context.load_cert_chain(certfile=_owner_file(cfg.client_cert),keyfile=_owner_file(cfg.client_key,secret=True))
        super().__init__(cfg.server_name,cfg.port,timeout=2,context=context)
        self.pinned_ip=cfg.pinned_ip

    def connect(self):
        # Exact configured numeric endpoint. TLS authenticates the named
        # gateway; no DNS lookup of its name or direct-origin alternative.
        raw=socket.create_connection((self.pinned_ip,self.port),self.timeout)
        try:
            if ipaddress.ip_address(raw.getpeername()[0])!=ipaddress.ip_address(self.pinned_ip):
                raise BrokerError("unexpected_peer")
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:
            raw.close()
            raise

class LocalReadBroker:
    def __init__(self, config: BrokerConfig):
        self.config=config

    def read(self, resource: str) -> str:
        if (not isinstance(resource,str) or not _RESOURCE.fullmatch(resource)
                or resource not in self.config.resources):
            raise BrokerError("resource_not_allowed")
        # No DNS, proxy-env handling, redirect support, URL supplied by model,
        # generic CONNECT, caller-supplied credentials, retries, alternate route or fallback.
        conn=None
        alarm=None
        deadline=time.monotonic()+4.0
        try:
            tls=self.config.mode=="mutual_tls_gateway"
            conn=_PinnedHTTPS(self.config) if tls else HTTPConnection("127.0.0.1",self.config.port,timeout=2.0)
            conn.connect()
            transport=conn.sock
            def abort_transport():
                try: transport.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            alarm=threading.Timer(max(0,deadline-time.monotonic()),abort_transport)
            alarm.daemon=True
            alarm.start()
            peer=transport.getpeername()
            expected=self.config.pinned_ip if tls else "127.0.0.1"
            if ipaddress.ip_address(peer[0]) != ipaddress.ip_address(expected) or peer[1] != self.config.port:
                raise BrokerError("unexpected_peer")
            conn.request("GET", "/v1/read/"+resource,
                         headers={"Accept":"application/json","Connection":"close"})
            res=conn.getresponse()
            if res.status != 200 or res.headers.get_content_type() != "application/json":
                raise BrokerError("gateway_response_denied")
            if res.headers.get("Transfer-Encoding") or res.headers.get("Content-Encoding"):
                raise BrokerError("gateway_encoding_denied")
            lengths=res.headers.get_all("Content-Length") or []
            if len(lengths)!=1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_RESPONSE:
                raise BrokerError("invalid_response_length")
            remaining=int(lengths[0])
            chunks=[]
            while remaining:
                if time.monotonic() >= deadline:
                    raise BrokerError("gateway_timeout")
                # read1 bounds each blocking socket read; no chunked bodies.
                data=res.read1(min(4096,remaining))
                if not data:
                    raise BrokerError("truncated_response")
                chunks.append(data)
                remaining-=len(data)
            if time.monotonic() >= deadline:
                raise BrokerError("gateway_timeout")
            data=strict_loads(b"".join(chunks).decode("utf-8"))
            # The synthetic gateway has a narrow schema. Never return arbitrary
            # headers, body, errors or remotely supplied authorization fields.
            if (not isinstance(data,dict) or set(data)!={"resource","value"}
                or data["resource"]!=resource
                or type(data["value"]) not in (int,str)
                or isinstance(data["value"],str) and len(data["value"])>4096):
                raise BrokerError("invalid_resource_payload")
            return json.dumps(data,ensure_ascii=True)
        except (OSError,HTTPException,ValueError,UnicodeError,RecursionError) as exc:
            raise BrokerError("gateway_unavailable_or_invalid") from exc
        finally:
            if alarm is not None:
                alarm.cancel()
            if conn is not None:
                conn.close()