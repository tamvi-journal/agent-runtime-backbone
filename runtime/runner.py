"""Trusted orchestration: role policy -> gate -> isolated execution -> candidate."""
from __future__ import annotations
from collections.abc import Mapping
from agent_audit_kit import PreflightPolicy, run_guarded_task
from runtime.roles import RoleProfile
from runtime.offline_executor import DockerOfflineExecutor, IsolationError

def run_operation(profile: RoleProfile, request: Mapping, executor: DockerOfflineExecutor) -> dict:
    # A worker cannot declare its own effective role, change network policy,
    # grant permission, provide executable arguments or supply verification.
    if not isinstance(request, Mapping) or set(request) != {"operation"}:
        return {"status":"blocked","reason":"invalid_request_fields","worker_ran":False}
    op=request["operation"]
    if not isinstance(op,str) or op not in profile.operations or profile.network != "deny":
        return {"status":"blocked","reason":"role_operation_not_allowed","worker_ran":False}
    envelope = {"worker_id": "isolated-worker", "requested_tools": ["sandbox_compute"],
                "requested_actions": [op], "network_access": False,
                "shell_access": False, "external_mutation": False,
                "money_touching": False, "completion_authority": False}
    policy = PreflightPolicy(allowed_tools=("sandbox_compute",),
                             allowed_actions=(op,))
    def worker(_):
        result = executor.execute(op)
        return {"worker_id":"isolated-worker","content":result.output,
                "sources":["isolated-process-output"],
                "checks_run":["prestart-isolation-inspection"],
                "evidence_handles":[]}
    try:
        result=run_guarded_task(envelope,policy,worker)
    except IsolationError:
        # An attempt might have started; never pretend the worker did not run.
        return {"status":"blocked","reason":"isolation_or_execution_failed",
                "worker_ran":"unknown","eligible_for_release":False}
    out=result.to_dict()
    # M0 never auto-releases: there is no external independent verifier configured.
    out["eligible_for_release"]=False
    return out
