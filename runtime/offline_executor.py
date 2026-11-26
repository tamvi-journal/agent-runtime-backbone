"""Host-owned Docker backend; no direct network, host mounts, or host fallback.

Only the trusted operator selects a reviewed local image. No arbitrary worker
command, environment, socket, proxy, image, mount, or network setting is accepted.
The daemon/host/operator and reviewed image are trusted dependencies.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import selectors
import time
import subprocess
import tempfile
import uuid
from dataclasses import dataclass

_IMAGE = re.compile(r"sha256:[0-9a-f]{64}")
_CONTAINER = re.compile(r"[0-9a-f]{64}")
# Reserved documentation destinations: diagnostics never contact commerce sites.
_DIAGNOSTICS = """
import os, socket, json
interfaces=sorted(n for n in os.listdir('/sys/class/net') if os.path.isdir('/sys/class/net/'+n))
active_interfaces=[]
for name in interfaces:
    with open('/sys/class/net/'+name+'/flags') as f:
        if int(f.read().strip(),16) & 1: active_interfaces.append(name)
with open('/proc/net/route') as f:
    ipv4_routes=[line.split()[0] for line in f.readlines()[1:] if line.strip()]
with open('/proc/net/ipv6_route') as f:
    ipv6_routes=[line.split()[-1] for line in f if line.strip()]
def blocked(family, addr):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(addr) != 0
    except OSError:
        return True
def udp_blocked():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 53))
            return False
    except OSError:
        return True
print(json.dumps({'interfaces':interfaces,
 'ipv4_blocked':blocked(socket.AF_INET,('192.0.2.1',443)),
 'ipv6_blocked':blocked(socket.AF_INET6,('2001:db8::1',443,0,0)),
 'udp_blocked':udp_blocked(),
 'uid':os.getuid(),'active_interfaces':active_interfaces,
 'ipv4_route_interfaces':ipv4_routes,'ipv6_route_interfaces':ipv6_routes}))
"""
_COMPUTE = "import json; print(json.dumps({'fixture_sum':sum(range(11))}))"
_ANALYZE = """import json,sys,math
v=json.loads(sys.stdin.read(16384))
print(json.dumps({'count':len(v),'min':min(v),'max':max(v),'mean':math.fsum(v)/len(v)}))
"""
_JOBS = {
    "offline_diagnostics": ("/usr/local/bin/python", "-I", "-c", _DIAGNOSTICS),
    "offline_compute": ("/usr/local/bin/python", "-I", "-c", _COMPUTE),
}

class IsolationError(RuntimeError):
    """No alternate execution path is permitted after an isolation failure."""

@dataclass(frozen=True)
class ExecutionResult:
    operation: str
    output: str
    isolation: str = "docker_network_none"
    # Not a statement that the worker result or all security properties are verified.

class DockerOfflineExecutor:
    def __init__(self, *, image_id: str, docker: str | None = None,
                 socket: str = "unix:///var/run/docker.sock"):
        if not isinstance(image_id, str) or not _IMAGE.fullmatch(image_id):
            raise ValueError("reviewed_local_image_id_required")
        executable = docker or shutil.which("docker")
        if not executable or not Path(executable).is_absolute():
            raise IsolationError("docker_unavailable")
        if socket != "unix:///var/run/docker.sock":
            raise IsolationError("unsupported_daemon_endpoint")
        self.image_id = image_id
        self._docker = executable
        self._socket = socket

    def _call(self, config: str, args: list[str], *, timeout: int = 15, input_text: str | None = None) -> str:
        env = {"PATH": os.defpath, "DOCKER_CONFIG": config}
        p=None
        try:
            p=subprocess.Popen([self._docker,"--host",self._socket,"--config",config,*args],
                stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            pending=memoryview(input_text.encode("utf-8") if input_text is not None else b"")
            chunks=bytearray()
            size=0
            end=time.monotonic()+timeout
            with selectors.DefaultSelector() as sel:
                for stream in (p.stdout,p.stderr):
                    os.set_blocking(stream.fileno(),False)
                    sel.register(stream,selectors.EVENT_READ)
                if p.stdin is not None:
                    os.set_blocking(p.stdin.fileno(),False)
                    sel.register(p.stdin,selectors.EVENT_WRITE)
                while sel.get_map():
                    remaining=end-time.monotonic()
                    if remaining<=0:
                        raise IsolationError("docker_timeout")
                    for key,_ in sel.select(remaining):
                        stream=key.fileobj
                        if stream is p.stdin:
                            if pending:
                                try: count=os.write(stream.fileno(),pending[:4096])
                                except BlockingIOError: continue
                                pending=pending[count:]
                            if not pending:
                                sel.unregister(stream)
                                stream.close()
                        else:
                            try: data=os.read(stream.fileno(),4096)
                            except BlockingIOError: continue
                            if not data:
                                sel.unregister(stream)
                                stream.close()
                                continue
                            size+=len(data)
                            if size>65536:
                                raise IsolationError("docker_output_limit")
                            if stream is p.stdout:
                                chunks.extend(data)
            if p.wait(timeout=max(0.1,end-time.monotonic()))!=0:
                raise IsolationError("docker_call_failed")
            return chunks.decode("utf-8").strip()
        except (OSError,subprocess.SubprocessError,UnicodeError) as exc:
            raise IsolationError("docker_call_failed") from exc
        finally:
            if p is not None:
                if p.poll() is None:
                    p.kill()
                    p.wait(timeout=3)
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream is not None:
                        stream.close()

    def _json(self, config: str, args: list[str]) -> dict:
        try:
            value = json.loads(self._call(config,args))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, TypeError) as exc:
            raise IsolationError("invalid_daemon_evidence") from exc

    def _validate_inspection(self, data: dict) -> None:
        h, c, n, state = (data.get(k, {}) for k in
                          ("HostConfig","Config","NetworkSettings","State"))
        if not all(isinstance(v,dict) for v in (h,c,n,state)):
            raise IsolationError("invalid_daemon_evidence")
        # Verify before starting the container. No healthchecks, mounts, ports,
        # additional capabilities, or privileged execution.
        if not (
            data.get("Image") == self.image_id
            and h.get("NetworkMode") == "none"
            and h.get("Privileged") is False
            and h.get("ReadonlyRootfs") is True
            and h.get("CapDrop") == ["ALL"]
            and not h.get("CapAdd")
            and not h.get("Binds") and not h.get("Mounts")
            and not data.get("Mounts")
            and not h.get("PortBindings") and not h.get("PublishAllPorts")
            and not h.get("Devices") and not h.get("DeviceRequests")
            and h.get("PidMode") in ("", "private", None)
            and h.get("IpcMode") in ("", "private", "none", None)
            and h.get("UsernsMode") == ""
            and h.get("UTSMode") == ""
            and h.get("CgroupnsMode") == "private"
            and h.get("Runtime") == "runc"
            and data.get("AppArmorProfile") != "unconfined"
            and set(h.get("SecurityOpt") or []) == {"no-new-privileges"}
            and {"/proc/kcore","/proc/keys","/sys/firmware"} <= set(h.get("MaskedPaths") or [])
            and {"/proc/sys","/proc/irq","/proc/sysrq-trigger"} <= set(h.get("ReadonlyPaths") or [])
            and h.get("MemorySwap") == 256*1024*1024
            and h.get("PidsLimit") == 64
            and h.get("Memory") == 256*1024*1024
            and h.get("NanoCpus") == 1000000000
            and not h.get("ExtraHosts")
            and not h.get("Links")
            and not h.get("VolumesFrom")
            and not h.get("GroupAdd")
            and not h.get("Sysctls")
            and not h.get("Dns")
            and not h.get("DnsSearch")
            and "no-new-privileges" in (h.get("SecurityOpt") or [])
            and c.get("User") == "65534:65534"
            and state.get("Status") == "created"
            and not state.get("Running")
            and set((n.get("Networks") or {}).keys()) <= {"none"}
        ):
            raise IsolationError("isolation_prestart_check_failed")

    def execute(self, operation: str) -> ExecutionResult:
        if operation not in _JOBS:
            raise IsolationError("unknown_operation")
        return self._execute_job(operation,_JOBS[operation])

    def analyze(self, numbers: list) -> ExecutionResult:
        if (not isinstance(numbers,list) or not 1<=len(numbers)<=256
                or not all(type(n) in (int,float) and -1e12<=n<=1e12 and math.isfinite(n) for n in numbers)):
            raise IsolationError("invalid_numbers")
        return self._execute_job("offline_analyze",("/usr/local/bin/python","-I","-c",_ANALYZE),json.dumps(numbers))

    def _execute_job(self,operation: str,job: tuple,input_text: str|None=None) -> ExecutionResult:
        # Empty Docker config prevents implicit host proxy or credential config.
        with tempfile.TemporaryDirectory(prefix="local-agent-docker-") as config:
            image = self._json(config, ["image","inspect","--format","{{json .}}",self.image_id])
            if image.get("Id") != self.image_id or (image.get("Config") or {}).get("Volumes"):
                raise IsolationError("unapproved_image_shape")
            name = "local-agent-offline-" + uuid.uuid4().hex
            creation_attempted = False
            try:
                creation_attempted = True
                cid = self._call(config, ["create", "--name", name,
                    *(["--interactive"] if input_text is not None else []),
                    "--label=local-agent-runtime.managed=offline", "--pull=never", "--network=none", "--read-only",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--user=65534:65534", "--pids-limit=64", "--memory=256m", "--memory-swap=256m",
                    "--runtime=runc","--cgroupns=private","--ipc=private",
                    "--cpus=1", "--no-healthcheck", "--entrypoint", job[0],
                    self.image_id, *job[1:]])
                if not _CONTAINER.fullmatch(cid):
                    raise IsolationError("invalid_container_receipt")
                before = self._json(config, ["inspect","--format","{{json .}}",cid])
                self._validate_inspection(before)
                c=before["Config"]
                if (c.get("Entrypoint")!=[job[0]] or c.get("Cmd")!=list(job[1:])
                    or bool(c.get("OpenStdin"))!=(input_text is not None)
                    or (c.get("Healthcheck") or {}).get("Test") != ["NONE"]
                    or (c.get("Labels") or {}).get("local-agent-runtime.managed")!="offline"):
                    raise IsolationError("registered_job_binding_mismatch")
                output = self._call(config, ["start","--attach",*(["--interactive"] if input_text is not None else []),cid], timeout=12,input_text=input_text)
                after = self._json(config, ["inspect","--format","{{json .State}}",cid])
                if after.get("Status") != "exited" or after.get("ExitCode") != 0:
                    raise IsolationError("worker_not_cleanly_exited")
                return ExecutionResult(operation, output)
            finally:
                # Exact uniquely named container only, even after create timeout.
                try:
                    self._call(config, ["rm","-f",name])
                except IsolationError:
                    if creation_attempted:
                        raise IsolationError("container_cleanup_unconfirmed")
