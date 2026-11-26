import concurrent.futures
import pytest
from runtime.adapters.transport_audit import TransportAuditBudget

def test_window_counts_and_periodic_flush():
    now=[0.0];events=[]
    b=TransportAuditBudget(lambda e:events.append(e) or True,clock=lambda:now[0])
    for _ in range(100):b.record("connection_limit")
    assert len(events)==1 and events[0]["count"]==1
    b.flush();assert len(events)==1
    now[0]=5;b.flush()
    assert len(events)==2 and events[1]["event"]=="gateway_transport_summary"
    assert events[1]["count"]==99
    b.record("connection_limit");assert len(events)==3
    assert all(e["principal"] is None and e["resource"] is None for e in events)

def test_concurrent_counts_no_unbounded_keys():
    events=[]
    b=TransportAuditBudget(lambda e:events.append(e) or True,clock=lambda:0)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(b.record,["tls_or_transport_failed"]*400))
    b.flush(force=True)
    assert len(events)==2 and sum(e["count"] for e in events)==400
    with pytest.raises(ValueError):b.record("raw peer")

def test_rollover_without_periodic_flush():
    now=[0];events=[]
    b=TransportAuditBudget(lambda e:events.append(e) or True,clock=lambda:now[0])
    for _ in range(3):b.record("request_deadline")
    now[0]=6;b.record("request_deadline");b.flush(force=True)
    assert [e["count"] for e in events]==[1,2,1]

def test_sink_failure_is_counted():
    b=TransportAuditBudget(lambda e:False,clock=lambda:0)
    for _ in range(17):b.record("connection_limit")
    b.flush(force=True)
    assert b.sink_failures==17
