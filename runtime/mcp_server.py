"""Bounded local MCP stdio transport (legacy 2025-11-25 handshake).

The operator launches one process for one instance; stdin is the capability
channel, not an authentication claim. No HTTP server, listening port, remote
client auth, credentials, shell, custom executable or model-selected profile.
"""
from __future__ import annotations
from runtime.strict_json import loads as strict_loads
import argparse, json, sys
from pathlib import Path
from runtime.instance import load_instance,Ledger
from runtime.service import AgentService

VERSION="0.2.0a4"
SUPPORTED=("2024-11-05","2025-03-26","2025-06-18","2025-11-25")
MAX_LINE=65536

def error(ident,code,msg):
    return {"jsonrpc":"2.0","id":ident,"error":{"code":code,"message":msg}}

def success(ident,result):
    return {"jsonrpc":"2.0","id":ident,"result":result}

class Session:
    def __init__(self,service):
        self.service=service
        self.negotiated=False
        self.ready=False

    def handle(self,message):
        if not isinstance(message,dict) or message.get("jsonrpc")!="2.0":
            return error(None,-32600,"Invalid request")
        method=message.get("method")
        ident=message.get("id")
        if "id" in message and type(ident) not in (int,str,type(None)):
            return error(None,-32600,"Invalid id")
        if not isinstance(method,str):
            return error(ident,-32600,"Invalid method")
        params=message.get("params",{})
        if not isinstance(params,dict):
            if method=="tools/call" and self.ready and "id" in message:
                self.service.record_denial(None)
            return error(ident,-32602,"Invalid params") if "id" in message else None
        if "id" not in message:
            if method=="notifications/initialized" and self.negotiated:
                self.ready=True
            # Notifications never execute tools.
            return None
        if method=="initialize":
            if self.negotiated or not isinstance(params.get("protocolVersion"),str):
                return error(ident,-32602,"Invalid initialization")
            requested=params["protocolVersion"]
            version=requested if requested in SUPPORTED else SUPPORTED[-1]
            self.negotiated=True
            return success(ident,{"protocolVersion":version,"capabilities":{"tools":{}},
                                  "serverInfo":{"name":"local-agent-runtime","version":VERSION}})
        if method=="ping":
            return success(ident,{})
        if not self.ready:
            return error(ident,-32002,"Initialization required")
        if method=="tools/list":
            if params.get("cursor") is not None:
                return error(ident,-32602,"Invalid cursor")
            return success(ident,{"tools":self.service.tools()})
        if method=="tools/call":
            if set(params)-{"name","arguments","_meta"} or not isinstance(params.get("name"),str):
                self.service.record_denial(params.get("name"))
                return error(ident,-32602,"Invalid tool call")
            result=self.service.invoke(params["name"],params.get("arguments",{}))
            return success(ident,{"content":[{"type":"text","text":json.dumps(result,ensure_ascii=True)}],
                                  "isError":result.get("status") in {"blocked","blocked_candidate"}})
        return error(ident,-32601,"Method not found")

def serve(service,stdin=None,stdout=None):
    stdin=stdin if stdin is not None else sys.stdin.buffer
    stdout=stdout if stdout is not None else sys.stdout.buffer
    session=Session(service)
    while True:
        raw=stdin.readline(MAX_LINE+1)
        if not raw:
            return 0
        if len(raw)>MAX_LINE or not raw.endswith(b"\n"):
            # Stop rather than parse an attacker-controlled partial next frame.
            return 3
        try:
            message=strict_loads(raw)
        except (ValueError,UnicodeError,RecursionError):
            response=error(None,-32700,"Parse error")
        else:
            try:response=session.handle(message)
            except Exception:
                ident=message.get("id") if isinstance(message,dict) else None
                response=error(ident if type(ident) in (int,str,type(None)) else None,-32603,"Internal error") if isinstance(message,dict) and "id" in message else None
        if response is not None:
            stdout.write((json.dumps(response,ensure_ascii=True)+"\n").encode())
            stdout.flush()

def main():
    p=argparse.ArgumentParser(description="Role-scoped local MCP stdio server")
    p.add_argument("--config",required=True,type=Path)
    p.add_argument("--state-root",required=True,type=Path)
    args=p.parse_args()
    try:
        cfg=load_instance(args.config)
        ledger=Ledger(args.state_root,cfg.instance_id)
        try:
            if ledger.recovered_count:
                print(f"local-agent-runtime: recovered {ledger.recovered_count} unsettled invocation(s) as unknown",file=sys.stderr)
            return serve(AgentService(cfg,ledger))
        finally:
            ledger.close()
    except Exception:
        # No configuration data or raw exception on stdout or stderr.
        print("local-agent-runtime: configuration or backend unavailable",file=sys.stderr)
        return 3

if __name__=="__main__":
    raise SystemExit(main())
