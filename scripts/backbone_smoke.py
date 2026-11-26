"""Synthetic distribution smoke; not a test of a running agent or LLM."""
import hashlib,tempfile
from pathlib import Path
from memory_core import MemoryStore
from runtime.memory_core_adapter.cli import render_context
from runtime.workers.preflight_guard import validate_worker_invocation_envelope
from runtime.workers.evidence_gate import build_worker_evidence_gate
from runtime.security.secret_scan import scan_text
with tempfile.TemporaryDirectory() as t:
    db=Path(t)/"candidate.sqlite"
    MemoryStore(db).initialize()
    db.chmod(0o600)
    before=hashlib.sha256(db.read_bytes()).digest()
    assert isinstance(render_context(db,"synthetic-instance","sample context"),str)
    assert hashlib.sha256(db.read_bytes()).digest()==before
    try: render_context(db,"synthetic-instance","x",limit=9)
    except ValueError: pass
    else: raise AssertionError("recall budget")
assert validate_worker_invocation_envelope(None)["decision"]=="invalid_envelope"
print("Shared backbone import, private read-only cue recall and budget PASS")
