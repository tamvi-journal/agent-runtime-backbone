import io,json,os,socket,ssl,subprocess,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import pytest
from runtime.broker import BrokerConfig,BrokerError,LocalReadBroker
from runtime.instance import InstanceConfig,Ledger,load_instance
from runtime.service import AgentService,valid_args
from runtime.mcp_server import Session,serve
from runtime.adapters.hermes import fragment

def config(port=None):
    broker=port is not None
    return InstanceConfig.from_mapping({"instance_id":"test-agent",
        "role":{"role":"research","operations":["read_registered_resource"] if broker else [],
                "network":"brokered_read" if broker else "deny","external_mutation":False},
        "image_id":None,
        "broker":{"mode":"synthetic_loopback","port":port,"resources":["sample"]} if broker else None})

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.server.requests.append(self.path)
        payload=self.server.payload
        self.send_response(self.server.status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Location","http://192.0.2.123/never-follow")
        self.end_headers()
        self.wfile.write(payload)

@pytest.fixture
def gateway():
    server=HTTPServer(("127.0.0.1",0),Handler)
    server.requests=[];server.payload=b'{"resource":"sample","value":42}';server.status=200
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try: yield server
    finally: server.shutdown();server.server_close();t.join()

def test_broker_success_candidate_and_ledger(gateway,tmp_path):
    ledger=Ledger(tmp_path/"state","test-agent")
    try:
        service=AgentService(config(gateway.server_port),ledger)
        assert [x["name"] for x in service.tools()]==["read_registered_resource"]
        r=service.invoke("read_registered_resource",{"resource":"sample"})
        assert r["status"]=="needs_review" and not r["eligible_for_release"]
        assert gateway.requests==["/v1/read/sample"]
        assert ledger.counts()=={"settled":1}
        assert "42" not in repr(ledger.db.execute("SELECT operation,phase,status FROM events").fetchall())
    finally: ledger.close()

@pytest.mark.parametrize("args",[{"resource":"other"},{"resource":"http://example.org"},
    {"resource":"../sample"},{"resource":"sample","url":"https://example.org"},
    {"resource":"sample","verified":True},{},{"resource":True}])
def test_unapproved_requests_never_reach_gateway(gateway,args):
    assert AgentService(config(gateway.server_port)).invoke("read_registered_resource",args)["status"]=="blocked"
    assert gateway.requests==[]

def test_redirect_no_fallback(gateway):
    gateway.status=302
    assert AgentService(config(gateway.server_port)).invoke("read_registered_resource",{"resource":"sample"})["status"]=="blocked"
    assert gateway.requests==["/v1/read/sample"]

@pytest.mark.parametrize("payload",[b'{"resource":"wrong","value":1}',b'{"resource":"sample","value":NaN}',b'{"resource":"sample","value":1,"verified":true}',b"x"*16385])
def test_invalid_gateway_output_blocked(gateway,payload):
    gateway.payload=payload
    assert AgentService(config(gateway.server_port)).invoke("read_registered_resource",{"resource":"sample"})["status"]=="blocked"
    assert len(gateway.requests)==1

def test_no_gateway_no_route():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0)); port=s.getsockname()[1]
        r=AgentService(config(port)).invoke("read_registered_resource",{"resource":"sample"})
        assert r["status"]=="blocked"

def test_roles_cannot_add_permission():
    with pytest.raises(ValueError):
        InstanceConfig.from_mapping({"instance_id":"x","role":{"role":"r","operations":["read_registered_resource"],"network":"deny","external_mutation":False},"image_id":None,"broker":None})

def test_config_permissions(tmp_path):
    p=tmp_path/"config.json"
    p.write_text(json.dumps({"instance_id":"x","role":{"role":"r","operations":[],"network":"deny","external_mutation":False},"image_id":None,"broker":None}))
    p.chmod(0o600)
    assert load_instance(p).instance_id=="x"
    assert fragment(p,tmp_path/"state",Path("/usr/bin/python3"))["mcp_servers"]["local_agent_runtime"]["tools"]["include"]==[]
    p.chmod(0o666)
    with pytest.raises(ValueError): load_instance(p)

def test_instance_ledger_separation(tmp_path):
    a=Ledger(tmp_path/"state","a");b=Ledger(tmp_path/"state","b")
    try:
        a.begin("offline_compute")
        assert a.counts()=={"started":1} and b.counts()=={}
    finally: a.close(); b.close()

@pytest.mark.parametrize("values",[[],[True],[float("nan")],[float("inf")],[1e13],[1]*257])
def test_numeric_bounds(values):
    assert not valid_args("offline_analyze",{"numbers":values})

def test_legacy_mcp_no_call_before_init():
    s=Session(AgentService(config()))
    assert s.handle({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"offline_compute"}})["error"]["code"]==-32002
    r=s.handle({"jsonrpc":"2.0","id":2,"method":"initialize","params":{"protocolVersion":"2025-11-25"}})
    assert r["result"]["protocolVersion"]=="2025-11-25"
    assert s.handle({"jsonrpc":"2.0","method":"notifications/initialized"}) is None
    assert s.handle({"jsonrpc":"2.0","id":3,"method":"tools/list"})["result"]["tools"]==[]
    assert s.handle({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"offline_compute"}})["result"]["isError"]

def test_oversized_frame_closes():
    assert serve(AgentService(config()),io.BytesIO(b"a"*65537),io.BytesIO())==3

def test_tls_requires_explicit_credentials():
    with pytest.raises(ValueError):
        BrokerConfig(18443,frozenset({"sample"}),"mutual_tls_gateway")


def test_strict_json_rejects_duplicate_keys():
    from runtime.strict_json import loads
    with pytest.raises(ValueError): loads('{"resource":"sample","resource":"other"}')

def test_advisory_monitor_no_completion(gateway):
    r=AgentService(config(gateway.server_port)).invoke("read_registered_resource",{"resource":"sample"})
    assert r["effort"]["advisory_only"] and not r["effort"]["permission_claimed"]
    assert not r["monitor"]["completion_claim_allowed"]
    assert r["monitor"]["verification_status"]=="pending"

def test_duplicate_gateway_fields_blocked(gateway):
    gateway.payload=b'{"resource":"sample","value":1,"value":2}'
    assert AgentService(config(gateway.server_port)).invoke("read_registered_resource",{"resource":"sample"})["status"]=="blocked"

def test_every_service_denial_is_recorded(gateway,tmp_path):
    ledger=Ledger(tmp_path/"state","test-agent")
    try:
        svc=AgentService(config(gateway.server_port),ledger)
        for op,args,reason in [
            ("unknown-secret-text",{},"role_operation_not_allowed"),
            ("read_registered_resource",{"bad":"private payload"},"invalid_arguments"),
            ("read_registered_resource",{"resource":"unknown-secret-text"},"resource_not_allowed"),
        ]:
            r=svc.invoke(op,args);assert r["reason"]==reason and r["invocation_id"]
        rows=ledger.db.execute("SELECT operation,status,reason FROM events").fetchall()
        assert len(rows)==3
        assert all(x[1]=="blocked" for x in rows)
        assert "unknown-secret-text" not in repr(rows)
        assert "private payload" not in repr(rows)
        assert gateway.requests==[]
    finally:ledger.close()

def test_offline_backend_denial_logged(tmp_path):
    ledger=Ledger(tmp_path/"state","agent")
    try:
        cfg=InstanceConfig.from_mapping({"instance_id":"agent","role":{"role":"analyst","operations":["offline_compute"],"network":"deny","external_mutation":False},"image_id":"sha256:"+"1"*64,"broker":None})
        svc=AgentService(cfg,ledger);svc.executor=None
        assert svc.invoke("offline_compute",{})["reason"]=="offline_backend_unavailable"
        assert ledger.db.execute("SELECT status,reason FROM events").fetchone()==("blocked","offline_backend_unavailable")
    finally:ledger.close()

@pytest.mark.parametrize("component",["allocate_effort","evaluate_commit","build_observability_mirror"])
def test_postprocess_failure_settles_without_release(gateway,tmp_path,monkeypatch,component):
    import runtime.service as service
    def fail(*a,**k):raise RuntimeError("private failure")
    monkeypatch.setattr(service,component,fail)
    ledger=Ledger(tmp_path/"state","test-agent")
    try:
        r=AgentService(config(gateway.server_port),ledger).invoke("read_registered_resource",{"resource":"sample"})
        assert r["status"]=="blocked" and r["reason"]=="postprocess_failed"
        assert r["worker_ran"] is True and not r["eligible_for_release"]
        assert ledger.db.execute("SELECT phase,status,reason FROM events").fetchone()==("settled","blocked","postprocess_failed")
        assert gateway.requests==["/v1/read/sample"]
    finally:ledger.close()

def test_restart_recovery_and_exclusive_writer(tmp_path):
    root=tmp_path/"state"
    a=Ledger(root,"a");ident=a.begin("offline_compute")
    try:
        with pytest.raises(ValueError,match="instance_writer_active"):Ledger(root,"a")
    finally:a.close()
    b=Ledger(root,"a")
    try:
        assert b.recovered_count==1
        assert b.db.execute("SELECT id,phase,status,reason FROM events").fetchone()==(ident,"settled","unknown","recovered_unsettled")
        with pytest.raises(ValueError):b.settle(ident,"allowed")
    finally:b.close()

def test_migrate_old_ledger(tmp_path):
    import sqlite3
    root=tmp_path/"state";root.mkdir(mode=0o700);folder=root/"a";folder.mkdir(mode=0o700)
    p=folder/"events.sqlite3"
    with sqlite3.connect(p) as db:
        db.execute("CREATE TABLE events(id TEXT PRIMARY KEY,at INTEGER,operation TEXT,phase TEXT,status TEXT)")
        db.execute("INSERT INTO events VALUES('old',1,'offline_compute','started','unknown')")
    p.chmod(0o600)
    a=Ledger(root,"a")
    try:
        assert a.recovered_count==1
        assert a.db.execute("SELECT reason FROM events").fetchone()==("recovered_unsettled",)
    finally:a.close()

def test_mcp_unexpected_exception_retains_id():
    class Broken:
        def tools(self):raise RuntimeError("private")
    req=[{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":"correlation","method":"tools/list"}]
    inp=io.BytesIO(b"".join((json.dumps(x)+"\n").encode() for x in req));out=io.BytesIO()
    assert serve(Broken(),inp,out)==0
    last=json.loads(out.getvalue().splitlines()[-1]);assert last["id"]=="correlation" and last["error"]["code"]==-32603

def test_mcp_malformed_call_logged(tmp_path):
    ledger=Ledger(tmp_path/"state","test-agent")
    try:
        s=Session(AgentService(config(),ledger))
        s.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}})
        s.handle({"jsonrpc":"2.0","method":"notifications/initialized"})
        assert s.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"offline_compute","extra":1}})["error"]["code"]==-32602
        assert s.handle({"jsonrpc":"2.0","id":3,"method":"tools/call","params":[]})["error"]["code"]==-32602
        assert ledger.db.execute("SELECT count(*) FROM events WHERE status='blocked' AND reason='invalid_tool_call'").fetchone()[0]==2
    finally:ledger.close()

def test_owner_config_rejects_world_readable(tmp_path):
    p=tmp_path/"instance.json";p.write_text("{}");p.chmod(0o644)
    with pytest.raises(ValueError,match="unsafe_config_permissions"):load_instance(p)

def test_independent_role_policy_compiles_all_allowed_operations(gateway,monkeypatch):
    import runtime.service as mod
    from types import SimpleNamespace
    cfg=InstanceConfig.from_mapping({"instance_id":"test-agent","role":{"role":"combined","operations":["offline_compute","read_registered_resource"],"network":"brokered_read","external_mutation":False},"image_id":"sha256:"+"1"*64,"broker":{"mode":"synthetic_loopback","port":gateway.server_port,"resources":["sample"]}})
    def gate(envelope,policy,execute):
        assert set(policy.allowed_actions)=={"offline_compute","read_registered_resource"}
        assert set(policy.allowed_tools)=={"sandbox_compute","broker_read"}
        assert policy.network_allowed is True
        assert envelope["requested_actions"]==["read_registered_resource"]
        return SimpleNamespace(to_dict=lambda:{"status":"blocked","worker_ran":False})
    monkeypatch.setattr(mod,"run_guarded_task",gate)
    result=AgentService(cfg).invoke("read_registered_resource",{"resource":"sample"})
    assert result["reason"]=="preflight_denied" and gateway.requests==[]
