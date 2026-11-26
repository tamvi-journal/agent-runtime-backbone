"""Run bounded local acceptance and generate evidence from actual test results.
Build dependency network is opt-in. Docker image is never pulled.
"""
from __future__ import annotations
import hashlib,json,os,platform,re,subprocess,sys,tempfile,tomllib,zipfile
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
version=tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["version"]
wheel=ROOT/"dist"/f"local_agent_runtime-{version}-py3-none-any.whl"
evidence=ROOT/"evidence"
local=ROOT/"local"
local.mkdir(exist_ok=True)
client=os.environ.get("MCP_CLIENT_PYTHON")
if not client:
    raise SystemExit("Set MCP_CLIENT_PYTHON to an installed MCP SDK interpreter")
client=os.path.abspath(client)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source_hash():
    # Exclude evidence, packaging outputs, ignored bytecode and private local
    # state. The digest binds the tested code/configuration, not Git identity.
    paths=[ROOT/"pyproject.toml"]
    for folder in ("runtime","src","tests","scripts","licenses"):
        paths.extend(p for p in (ROOT/folder).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix!=".pyc")
    h=hashlib.sha256()
    for p in sorted(paths):
        h.update(p.relative_to(ROOT).as_posix().encode()+b"\0"+p.read_bytes()+b"\0")
    return h.hexdigest()

def run(args,*,cwd=ROOT,env=None):
    print("+ "+str(args[0])+" "+str(args[1] if len(args)>1 else ""),flush=True)
    p=subprocess.run([str(x) for x in args],cwd=cwd,env=env,stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT,text=True)
    print(p.stdout,end="",flush=True)
    if p.returncode:raise SystemExit(p.returncode)
    return p.stdout

def atomic_json(path,data):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2)+"\n")
    os.replace(tmp,path)

with tempfile.TemporaryDirectory(prefix="lar-acceptance-",dir=local) as tmp:
    tmp=Path(tmp)
    source_before=source_hash()
    report=tmp/"pytest.xml"
    unit=run([sys.executable,"-m","pytest","-q","--junitxml",report])
    xml=ElementTree.parse(report).getroot()
    suites=[xml] if xml.tag=="testsuite" else list(xml.findall("testsuite"))
    tests=sum(int(s.attrib["tests"]) for s in suites)
    bad=sum(int(s.attrib.get(k,0)) for s in suites for k in ("failures","errors","skipped"))
    assert tests>0 and bad==0
    build=["uv","build","--wheel","--offline"]
    if os.environ.get("LAR_ALLOW_BUILD_NETWORK")=="1":
        build.remove("--offline")
    run(build)
    expected=sha(wheel)
    # Rebuild the same source and require identical bytes. For review of a
    # supplied wheel, LAR_EXPECTED_WHEEL_SHA256 can bind the exact known artifact.
    run(build)
    assert sha(wheel)==expected,"wheel_not_reproducible"
    if os.environ.get("LAR_EXPECTED_WHEEL_SHA256"):
        assert expected==os.environ["LAR_EXPECTED_WHEEL_SHA256"],"wheel_review_sha_mismatch"
    with zipfile.ZipFile(wheel) as z:
        names=z.namelist()
        assert "runtime/mcp_server.py" in names and "runtime/adapters/gateway_server.py" in names
        assert any("licenses/agent-audit-kit-MIT.txt" in x for x in names)
        assert not any(x.startswith(("tests/","evidence/","local/","examples/")) for x in names)
    venv=tmp/"venv"
    run(["uv","venv","--python",sys.executable,venv])
    python=venv/"bin/python"
    run(["uv","pip","install","--offline","--no-deps","--python",python,wheel])
    run([python,"-I",ROOT/"scripts/verify_installed_wheel.py",wheel,expected],cwd=tmp)
    help_text=run([venv/"bin/local-agent-gate","--help"],cwd=tmp)
    assert "usage: local-agent-gate" in help_text
    cfg=tmp/"docker-config";cfg.mkdir()
    docker=["docker","--config",str(cfg),"--host","unix:///var/run/docker.sock"]
    image=run([*docker,"image","inspect","--format","{{.Id}}","python:3.11.15-slim-bookworm"]).strip().splitlines()[-1]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}",image)
    # Mount only the wheel and exact two acceptance scripts; no source tree.
    # Synthetic certificates are generated in the disposable container's /tmp.
    tls_bootstrap="""set -eu
python -m pip --disable-pip-version-check install --no-index --no-deps --no-cache-dir --target /tmp/wheel-site "/wheel/$LAR_TEST_WHEEL_NAME"
python -I -c 'import os,sys,runpy;sys.path.insert(0,"/tmp/wheel-site");sys.argv=["verify","/wheel/"+os.environ["LAR_TEST_WHEEL_NAME"],os.environ["LAR_TEST_WHEEL_SHA"]];runpy.run_path("/tests/verify.py",run_name="__main__")'
python -I -c 'import sys,runpy;sys.path.insert(0,"/tmp/wheel-site");runpy.run_path("/tests/tls.py",run_name="__main__")'
"""
    tls=run([*docker,"run","--rm","--pull=never","--network=none","--read-only","--cap-drop=ALL",
        "--security-opt=no-new-privileges","--user=65534:65534",
        "--tmpfs","/tmp:rw,nosuid,nodev,size=64m",
        "--mount",f"type=bind,src={wheel},dst=/wheel/{wheel.name},readonly",
        "--mount",f"type=bind,src={ROOT/'scripts/tls_acceptance.py'},dst=/tests/tls.py,readonly",
        "--mount",f"type=bind,src={ROOT/'scripts/verify_installed_wheel.py'},dst=/tests/verify.py,readonly",
        "-e","PYTHONDONTWRITEBYTECODE=1", "-e",f"LAR_TEST_WHEEL_NAME={wheel.name}", "-e",f"LAR_TEST_WHEEL_SHA={expected}",image,"/bin/sh","-c",tls_bootstrap])
    m=re.search(r"Ran (\d+) tests? in ",tls)
    assert m and re.search(r"^OK$",tls,re.M) and "Installed wheel package byte comparison PASS" in tls
    tls_count=int(m.group(1))
    sdk=run([client,ROOT/"scripts/mcp_acceptance.py",python,image],cwd=tmp)
    sdk_checks=["SDK offline: actual wheel + MCP initialize/list/call + Docker isolation + role deny PASS",
        "SDK broker: exact registered resource + unauthorized URL denied + unavailable gateway blocked PASS",
        "Per-instance metadata ledger isolation and settlement PASS"]
    assert all(x in sdk for x in sdk_checks)
    leftovers=run([*docker,"ps","-a","--filter","label=local-agent-runtime.managed=offline","--format","{{.Names}}"]).strip()
    assert not leftovers,"managed_container_cleanup_unconfirmed"
    assert sha(wheel)==expected,"wheel_changed_during_acceptance"
    assert source_hash()==source_before,"source_changed_during_acceptance"
    receipt={"release":version,"recorded_at":datetime.now(timezone.utc).isoformat(),
        "scope":"local synthetic acceptance, not production certification",
        "platform":{"system":platform.system(),"machine":platform.machine(),"python":platform.python_version()},
        "source_sha256":source_before,"pytest_passed":tests,"isolated_mtls_tests_passed":tls_count,
        "wheel":{"filename":wheel.name,"sha256":expected,"entries":len(names),
                 "rebuild_sha_match":True,"installed_mac_and_container_byte_match":True},
        "sdk_acceptance":sdk_checks,"managed_container_cleanup":"pass",
        "live_provider_or_account_tested":False,"independent_review":"pending_for_this_release"}
    # Store only generated count/summary, never fixture fingerprint/address logs.
    lines=[l for l in unit.splitlines() if re.fullmatch(r"[0-9]+ passed in [0-9.]+s",l)]
    assert lines
    (evidence/"unit-tests.txt").write_text("\n".join(lines)+"\n")
    atomic_json(evidence/f"acceptance-{version}.json",receipt)
    print("Managed container cleanup PASS")
    print("Generated evidence: "+f"evidence/acceptance-{version}.json")
    print(json.dumps({"pytest":tests,"tls":tls_count,"wheel_sha256":expected,"wheel_reproducible":True},indent=2))
