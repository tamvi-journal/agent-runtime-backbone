"""Use a real installed MCP SDK client to start the installed runtime wheel.
No modifications to the existing Hermes agent or its profiles.
"""
import asyncio, json, os, subprocess, sys,tempfile
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import contextmanager
from http.server import HTTPServer,BaseHTTPRequestHandler
import threading,socket

class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.server.requests.append(self.path)
        data=b'{"resource":"sample","value":42}'
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)

@contextmanager
def gateway():
    server=HTTPServer(("127.0.0.1",0),Fixture);server.requests=[]
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:yield server
    finally:server.shutdown();server.server_close();t.join()

async def run(python,root,image):
    cfg=root/"instance.json";state=root/"state"
    def write(data):cfg.write_text(json.dumps(data));cfg.chmod(0o600)
    common={"instance_id":"fixture-analyst","role":{"role":"analyst","operations":["offline_analyze","offline_diagnostics"],"network":"deny","external_mutation":False},"image_id":image,"broker":None}
    write(common)
    args=["-I","-m","runtime.mcp_server","--config",str(cfg),"--state-root",str(state)]
    params=StdioServerParameters(command=python,args=args,env={"PATH":"/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"})
    def result(r):return json.loads(r.content[0].text)
    async with stdio_client(params) as (read,write_stream):
        async with ClientSession(read,write_stream) as s:
            init=await s.initialize()
            assert init.serverInfo.name=="local-agent-runtime"
            tools=await s.list_tools()
            assert sorted(t.name for t in tools.tools)==["offline_analyze","offline_diagnostics"]
            r=await s.call_tool("offline_analyze",{"numbers":[1,2,3,4]})
            value=result(r)
            assert not r.isError and value["status"]=="needs_review" and not value["eligible_for_release"],value
            assert json.loads(value["audit"]["output"]["content"])=={"count":4,"min":1,"max":4,"mean":2.5}
            r=await s.call_tool("offline_diagnostics",{})
            value=result(r); assert value["status"]=="needs_review",value
            d=json.loads(value["audit"]["output"]["content"])
            assert d["active_interfaces"]==["lo"] and not(set(d["ipv4_route_interfaces"]+d["ipv6_route_interfaces"])-{"lo"})
            assert d["ipv4_blocked"] and d["ipv6_blocked"] and d["udp_blocked"] and d["uid"]==65534
            assert (await s.call_tool("offline_compute",{})).isError
            assert (await s.call_tool("offline_analyze",{"numbers":[1,2],"network_access":True})).isError
    print("SDK offline: actual wheel + MCP initialize/list/call + Docker isolation + role deny PASS",flush=True)
    with gateway() as g:
        write({"instance_id":"fixture-reader","role":{"role":"research","operations":["read_registered_resource"],"network":"brokered_read","external_mutation":False},"image_id":None,
            "broker":{"mode":"synthetic_loopback","port":g.server_port,"resources":["sample"]}})
        async with stdio_client(params) as (read,write_stream):
            async with ClientSession(read,write_stream) as s:
                await s.initialize()
                assert [t.name for t in (await s.list_tools()).tools]==["read_registered_resource"]
                r=await s.call_tool("read_registered_resource",{"resource":"sample"})
                assert not r.isError and result(r)["status"]=="needs_review"
                assert json.loads(result(r)["audit"]["output"]["content"])["value"]==42
                assert (await s.call_tool("read_registered_resource",{"resource":"https://example.invalid"})).isError
                assert g.requests==["/v1/read/sample"]
        port=g.server_port
    async with stdio_client(params) as (read,write_stream):
        async with ClientSession(read,write_stream) as s:
            await s.initialize()
            r=await s.call_tool("read_registered_resource",{"resource":"sample"})
            assert r.isError and result(r)["status"]=="blocked"
    print("SDK broker: exact registered resource + unauthorized URL denied + unavailable gateway blocked PASS",flush=True)
    import sqlite3
    for name,expected in [("fixture-analyst",4),("fixture-reader",3)]:
        with sqlite3.connect(state/name/"events.sqlite3") as db:
            assert db.execute("select count(*) from events where phase='settled'").fetchone()[0]==expected
            reasons={r[0] for r in db.execute("select reason from events where status='blocked'")}
            assert reasons==({"role_operation_not_allowed","invalid_arguments"} if name=="fixture-analyst" else {"resource_not_allowed","execution_or_broker_failed"})
    print("Per-instance metadata ledger isolation and settlement PASS",flush=True)

if __name__=="__main__":
    with tempfile.TemporaryDirectory() as d:
        asyncio.run(run(os.path.abspath(sys.argv[1]),Path(d),sys.argv[2]))
