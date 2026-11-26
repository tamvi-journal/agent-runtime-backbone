"""Bound transport-only diagnostic volume without sampling request denials.

One immediate sample per reason per monotonic window, then a count summary.
No peer identifiers, arbitrary reason keys, or unbounded event queue.
"""
from __future__ import annotations
from dataclasses import dataclass
import threading,time

REASONS=frozenset({"connection_limit","tls_or_transport_failed",
                   "request_deadline","gateway_internal_error"})

@dataclass
class _Window:
    deadline: float
    suppressed: int=0

class TransportAuditBudget:
    def __init__(self,write,*,interval: float=5.0,clock=time.monotonic):
        if type(interval) not in (int,float) or not 0.1<=interval<=60:
            raise ValueError("invalid_transport_audit_interval")
        self._write=write
        self._interval=interval
        self._clock=clock
        self._lock=threading.Lock()
        self._windows={}
        self._sink_failures=0

    def _event(self,reason,count,summary):
        return {"event":"gateway_transport_summary" if summary else "gateway_request",
                "at":int(time.time()),"code":0,"reason":reason,
                "principal":None,"resource":None,
                "count":count}

    def _deliver(self,event):
        try:
            ok=self._write(event)
        except Exception:
            ok=False
        if not ok:
            with self._lock:self._sink_failures+=event["count"]

    def record(self,reason):
        if reason not in REASONS:
            raise ValueError("unknown_transport_audit_reason")
        ready=[]
        with self._lock:
            now=self._clock()
            old=self._windows.get(reason)
            if old is not None and now<old.deadline:
                old.suppressed+=1
                return
            if old is not None and old.suppressed:
                ready.append(self._event(reason,old.suppressed,True))
            self._windows[reason]=_Window(now+self._interval)
            ready.append(self._event(reason,1,False))
        for event in ready:self._deliver(event)

    def flush(self,*,force=False):
        ready=[]
        with self._lock:
            now=self._clock()
            for reason,window in list(self._windows.items()):
                if force or now>=window.deadline:
                    if window.suppressed:
                        ready.append(self._event(reason,window.suppressed,True))
                    del self._windows[reason]
        for event in ready:self._deliver(event)

    @property
    def sink_failures(self):
        # Counts represented events whose sink failed; not a durability proof.
        with self._lock:return self._sink_failures
