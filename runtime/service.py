"""One role-bound tool registry and Gate; never grant model-controlled authority."""
from __future__ import annotations
from collections.abc import Mapping
import json, math
from agent_audit_kit import PreflightPolicy, run_guarded_task
from runtime.broker import LocalReadBroker, BrokerError
from runtime.offline_executor import DockerOfflineExecutor, IsolationError
from runtime.instance import InstanceConfig, Ledger
from runtime.allocator.effort_allocator import allocate_effort
from runtime.monitor.commit import evaluate_commit
from runtime.monitor.observability import build_observability_mirror

SCHEMAS={
    "offline_diagnostics":{"type":"object","properties":{},"additionalProperties":False},
    "offline_compute":{"type":"object","properties":{},"additionalProperties":False},
    "offline_analyze":{"type":"object","properties":{"numbers":{"type":"array","items":{"type":"number","minimum":-1e12,"maximum":1e12},"minItems":1,"maxItems":256}},"required":["numbers"],"additionalProperties":False},
    "read_registered_resource":{"type":"object","properties":{"resource":{"type":"string","maxLength":64}},"required":["resource"],"additionalProperties":False},
}
DESCRIPTIONS={
    "offline_diagnostics":"Check offline worker isolation; candidate output only.",
    "offline_compute":"Run an offline deterministic computation fixture.",
    "offline_analyze":"Summarize a bounded list of numeric values offline.",
    "read_registered_resource":"Read one registered resource via the configured gateway. No arbitrary URL or remote execution.",
}

def blocked(reason):
    return {"status":"blocked","reason":reason,"eligible_for_release":False,"worker_ran":False}

def valid_args(op,args):
    if not isinstance(args,Mapping):
        return False
    if op in ("offline_compute","offline_diagnostics"):
        return not args
    if op=="offline_analyze":
        if set(args)!={"numbers"} or not isinstance(args["numbers"],list) or not 1<=len(args["numbers"])<=256:
            return False
        return all(type(n) in (int,float) and -1e12<=n<=1e12 and math.isfinite(n) for n in args["numbers"])
    if op=="read_registered_resource":
        return set(args)=={"resource"} and isinstance(args["resource"],str) and len(args["resource"])<=64
    return False

class AgentService:
    def __init__(self,config: InstanceConfig,ledger: Ledger|None=None):
        self.config=config
        self.ledger=ledger
        try:self.executor=DockerOfflineExecutor(image_id=config.image_id) if config.image_id else None
        except IsolationError:self.executor=None
        self.broker=LocalReadBroker(config.broker) if config.broker else None

    def tools(self):
        return [{"name":op,"description":DESCRIPTIONS[op],"inputSchema":SCHEMAS[op]}
                for op in sorted(self.config.role.operations)]

    def _recorded(self,op,action):
        try:
            receipt=self.ledger.begin(op) if self.ledger else None
        except Exception:
            return blocked("ledger_unavailable")
        try:
            result=action()
        except Exception:
            result={"status":"blocked","reason":"internal_execution_error",
                    "eligible_for_release":False,"worker_ran":"unknown"}
        if receipt:
            try:
                self.ledger.settle(receipt,result["status"],result.get("reason"))
            except Exception:
                return {"status":"blocked","reason":"ledger_settlement_unconfirmed",
                        "eligible_for_release":False,"worker_ran":result.get("worker_ran","unknown"),
                        "invocation_id":receipt}
            result["invocation_id"]=receipt
        return result

    def record_denial(self,op):
        return self._recorded(op,lambda:blocked("invalid_tool_call"))

    def invoke(self,op,args):
        return self._recorded(op,lambda:self._invoke(op,args))

    def _invoke(self,op,args):
        if not isinstance(op,str) or op not in self.config.role.operations:
            return blocked("role_operation_not_allowed")
        if not valid_args(op,args):
            return blocked("invalid_arguments")
        connected=op=="read_registered_resource"
        if connected and (self.broker is None or args["resource"] not in self.broker.config.resources):
            return blocked("resource_not_allowed")
        if not connected and self.executor is None:
            return blocked("offline_backend_unavailable")
        tool="broker_read" if connected else "sandbox_compute"
        envelope={"worker_id":"registered-worker","requested_tools":[tool],
                  "requested_actions":[op],"network_access":connected,
                  "shell_access":False,"external_mutation":False,"money_touching":False,
                  "completion_authority":False}
        # Policy is compiled independently from the owner-bound role. The
        # preflight is a declaration/consistency check, not OS enforcement.
        allowed=self.config.role.operations
        tools=tuple(t for t,enabled in (("broker_read","read_registered_resource" in allowed),
            ("sandbox_compute",any(x.startswith("offline_") for x in allowed))) if enabled)
        policy=PreflightPolicy(allowed_tools=tools,allowed_actions=tuple(sorted(allowed)),
                               network_allowed=self.config.role.network=="brokered_read")
        def execute(_):
            if connected:
                out=self.broker.read(args["resource"])
                source="registered-gateway-resource"
                checks=["registered-resource","gateway-response-shape"]
            else:
                out=(self.executor.analyze(args["numbers"]) if op=="offline_analyze"
                     else self.executor.execute(op)).output
                source="isolated-process-output"
                checks=["prestart-isolation-inspection"]
            return {"worker_id":"registered-worker","content":out,"sources":[source],
                    "checks_run":checks,"evidence_handles":[]}
        try:
            result=run_guarded_task(envelope,policy,execute).to_dict()
            result["eligible_for_release"]=False
            if not result.get("worker_ran") and result["status"] in {"blocked","needs_approval"}:
                result["reason"]="preflight_denied"
            elif result["status"]=="blocked_candidate":
                result["reason"]="candidate_blocked"
        except (IsolationError,BrokerError,ValueError):
            result={"status":"blocked","reason":"execution_or_broker_failed",
                    "eligible_for_release":False,"worker_ran":"unknown"}
        except Exception:
            result={"status":"blocked","reason":"internal_execution_error",
                    "eligible_for_release":False,"worker_ran":"unknown"}
        try:
            # Allocator and monitor are observers only; neither grants authority.
            result["effort"]=allocate_effort({
                "task_type":"execution","active_mode":"execute","ambiguity_score":0.0,
                "risk_score":0.7 if connected else 0.2,"stakes_signal":0.5,
                "action_required":True,"memory_commit_possible":False,
                "disagreement_likelihood":0.0,"mode_confidence":1.0,
                "verification_gap_estimate":1.0,"high_risk_domain":False,
                "unanswerable_likelihood":0.0,"cue_strength":0.0})
            denied=result["status"] in {"blocked","blocked_candidate"}
            commit=evaluate_commit(intended_action=op,executed_action="registered_operation_attempt",
                observed_outcome="operation_blocked_or_unknown" if denied else "candidate_received",
                evidence_handles=[],verification_status="unknown" if denied else "pending",
                mainbrain_verified=False,completion_claim_requested=False,
                worker_claim_present=not denied,work_artifact_present=False)
            result["monitor"]=build_observability_mirror(
                route_class="kernel_capability_path",gate_decision="deny" if denied else "allow",
                commit_result=commit)
        except Exception:
            return {"status":"blocked","reason":"postprocess_failed","eligible_for_release":False,
                    "worker_ran":result.get("worker_ran","unknown")}
        return result
