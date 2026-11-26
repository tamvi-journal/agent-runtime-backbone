"""Generate, never install, a role-scoped Hermes MCP fragment."""
from __future__ import annotations
from pathlib import Path
import argparse,json,sys
from runtime.instance import load_instance

def fragment(config: Path,state_root: Path,python: Path):
    if not all(p.is_absolute() for p in (config,state_root,python)):
        raise ValueError("absolute_paths_required")
    cfg=load_instance(config)
    return {"mcp_servers":{"local_agent_runtime":{
        "command":str(python),
        "args":["-I","-m","runtime.mcp_server","--config",str(config),"--state-root",str(state_root)],
        "enabled":True,"protocol":"legacy","supports_parallel_tool_calls":False,
        "timeout":60,"tools":{"include":sorted(cfg.role.operations),"resources":False,"prompts":False},
        "sampling":{"enabled":False},"elicitation":{"enabled":False}
    }}}

def main():
    p=argparse.ArgumentParser(description="Print JSON/YAML-compatible Hermes MCP config; do not edit existing agent.")
    p.add_argument("--config",required=True,type=Path)
    p.add_argument("--state-root",required=True,type=Path)
    p.add_argument("--python",default=Path(sys.executable),type=Path)
    a=p.parse_args()
    print(json.dumps(fragment(a.config,a.state_root,a.python),indent=2))

if __name__=="__main__":
    main()
