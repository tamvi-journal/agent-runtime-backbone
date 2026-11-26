"""Local operator CLI; not a remotely accessible or worker-facing execution API."""
import argparse
import json
from runtime.roles import PROFILES
from runtime.offline_executor import DockerOfflineExecutor, IsolationError
from runtime.runner import run_operation

def main():
    p=argparse.ArgumentParser(description="Run a registered offline fixture")
    p.add_argument("--role",choices=PROFILES,required=True)
    p.add_argument("--operation",required=True)
    p.add_argument("--image-id",required=True,help="Reviewed local immutable Docker image ID")
    a=p.parse_args()
    try:
        result=run_operation(PROFILES[a.role],{"operation":a.operation},
                             DockerOfflineExecutor(image_id=a.image_id))
    except (ValueError, IsolationError):
        result={"status":"blocked","reason":"backend_configuration_invalid"}
    print(json.dumps(result,indent=2))
    return 3 if result.get("status") in ("blocked","blocked_candidate") else 2

if __name__=="__main__":
    raise SystemExit(main())
