"""Owner-selected per-instance configuration and a metadata-only local ledger."""
from __future__ import annotations
from runtime.strict_json import loads as strict_loads
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import json, os, re, stat, sqlite3, time, uuid, fcntl
from runtime.roles import OPERATIONS
from runtime.roles import RoleProfile
from runtime.broker import BrokerConfig

_INSTANCE=re.compile(r"[a-z][a-z0-9_-]{0,63}")
_IMAGE=re.compile(r"sha256:[a-f0-9]{64}")

@dataclass(frozen=True)
class InstanceConfig:
    instance_id: str
    role: RoleProfile
    image_id: str | None
    broker: BrokerConfig | None
    @classmethod
    def from_mapping(cls,data: Mapping):
        if not isinstance(data,Mapping) or set(data)!={"instance_id","role","image_id","broker"}:
            raise ValueError("invalid_instance_fields")
        ident=data["instance_id"]
        if not isinstance(ident,str) or not _INSTANCE.fullmatch(ident):
            raise ValueError("invalid_instance_id")
        role=RoleProfile.from_mapping(data["role"])
        image=data["image_id"]
        if image is not None and (not isinstance(image,str) or not _IMAGE.fullmatch(image)):
            raise ValueError("invalid_image_id")
        if any(x.startswith("offline_") for x in role.operations) and image is None:
            raise ValueError("offline_image_required")
        broker=BrokerConfig.from_mapping(data["broker"]) if data["broker"] is not None else None
        if (role.network=="brokered_read") != (broker is not None):
            raise ValueError("broker_role_mismatch")
        return cls(ident,role,image,broker)

def load_instance(path: Path):
    # This is a local operator entrypoint, not a tool-call argument.
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,"rb") as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1:
            raise ValueError("unsafe_config_permissions")
        raw=f.read(32769)
    if len(raw)>32768:
        raise ValueError("config_too_large")
    return InstanceConfig.from_mapping(strict_loads(raw))

class Ledger:
    """No raw user input, provider responses, IPs, paths or credentials in records.
    SQLite is a local operational journal, NOT independently signed evidence.
    """
    def __init__(self, root: Path, instance_id: str):
        if not _INSTANCE.fullmatch(instance_id):
            raise ValueError("invalid_instance_id")
        root=Path(root)
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if root.is_symlink() or root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:
            raise ValueError("private_state_root_required")
        folder=root/instance_id
        folder.mkdir(mode=0o700,exist_ok=True)
        if folder.is_symlink() or folder.stat().st_uid!=os.getuid() or folder.stat().st_mode & 0o077:
            raise ValueError("private_instance_dir_required")
        self._lock_fd=os.open(folder/"writer.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        self.db=None
        try:
            ls=os.fstat(self._lock_fd)
            if not stat.S_ISREG(ls.st_mode) or ls.st_uid!=os.getuid() or ls.st_mode&0o077 or ls.st_nlink!=1:
                raise ValueError("unsafe_writer_lock")
            try:fcntl.flock(self._lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as exc:raise ValueError("instance_writer_active") from exc
            db=folder/"events.sqlite3"
            fd=os.open(db,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            try:
                st=os.fstat(fd)
                if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_nlink!=1:
                    raise ValueError("unsafe_ledger")
            finally:os.close(fd)
            self.db=sqlite3.connect(db,timeout=3)
            with self.db:
                self.db.execute("CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, at INTEGER, operation TEXT, phase TEXT, status TEXT, reason TEXT)")
                if "reason" not in {r[1] for r in self.db.execute("PRAGMA table_info(events)")}:
                    self.db.execute("ALTER TABLE events ADD COLUMN reason TEXT")
                # Only after exclusive instance-writer lock. Do not re-run or
                # claim completion of any abandoned invocation.
                self.recovered_count=self.db.execute("UPDATE events SET phase='settled',status='unknown',reason='recovered_unsettled' WHERE phase='started'").rowcount
        except BaseException:
            if self.db is not None:self.db.close()
            os.close(self._lock_fd)
            raise

    def begin(self,op: str) -> str:
        ident=uuid.uuid4().hex
        safe_op=op if isinstance(op,str) and op in OPERATIONS else "unknown_operation"
        with self.db:
            self.db.execute("INSERT INTO events(id,at,operation,phase,status,reason) VALUES(?,?,?,?,?,?)",
                            (ident,int(time.time()),safe_op,"started","unknown",None))
        return ident

    def settle(self,ident: str,status: str,reason: str|None=None):
        if status not in {"blocked","blocked_candidate","needs_review","needs_approval","allowed","unknown"}:
            status="unknown"
        if reason not in {None,"role_operation_not_allowed","invalid_arguments","resource_not_allowed",
            "offline_backend_unavailable","execution_or_broker_failed","internal_execution_error",
            "postprocess_failed","invalid_tool_call","recovered_unsettled","preflight_denied","candidate_blocked"}:
            reason="internal_execution_error"
        with self.db:
            n=self.db.execute("UPDATE events SET phase='settled',status=?,reason=? WHERE id=? AND phase='started'",(status,reason,ident)).rowcount
            if n!=1:raise ValueError("ledger_settlement_not_unique")

    def counts(self):
        return dict(self.db.execute("SELECT phase, count(*) FROM events GROUP BY phase"))

    def close(self):
        try:self.db.close()
        finally:os.close(self._lock_fd)
