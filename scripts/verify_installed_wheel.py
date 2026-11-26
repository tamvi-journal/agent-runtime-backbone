"""Compare installed package bytes with the exact wheel under test."""
import hashlib,sys,zipfile
from pathlib import Path
import runtime,agent_audit_kit

def verify(wheel,expected_sha):
    wheel=Path(wheel)
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()==expected_sha
    roots={"runtime":Path(runtime.__file__).parent,
           "agent_audit_kit":Path(agent_audit_kit.__file__).parent}
    with zipfile.ZipFile(wheel) as z:
        count=0
        for name in z.namelist():
            parts=name.split("/")
            if parts[0] in roots and not name.endswith("/"):
                target=roots[parts[0]].joinpath(*parts[1:])
                assert target.read_bytes()==z.read(name),name
                count+=1
    assert count>20
    print("Installed wheel package byte comparison PASS",flush=True)

if __name__=="__main__":
    verify(sys.argv[1],sys.argv[2])
