import json
import pytest
from runtime.roles import PROFILES, RoleProfile
from runtime.runner import run_operation
from runtime.offline_executor import DockerOfflineExecutor, ExecutionResult, IsolationError
from runtime.core.verification import completion_claim_allowed

class Fake:
    calls=0
    def execute(self,op):
        self.calls+=1
        return ExecutionResult(op,'{"fixture":true}')

@pytest.mark.parametrize("payload",[
    {"operation":"offline_compute","network_access":True},
    {"operation":"offline_diagnostics","verified_evidence":{}},
    {"operation":"offline_diagnostics","role":"admin"},
    {"operation":"offline_diagnostics","command":"curl example.org"},
    {"operation":"unknown"}, {"operation":None}, {},
])
def test_invalid_requests_do_not_execute(payload):
    f=Fake()
    assert run_operation(PROFILES["research"],payload,f)["status"]=="blocked"
    assert f.calls==0

def test_empty_role_is_deny_all():
    f=Fake()
    assert run_operation(PROFILES["reviewer"],{"operation":"offline_diagnostics"},f)["status"]=="blocked"
    assert f.calls==0

def test_profile_cannot_enable_network():
    with pytest.raises(ValueError):
        RoleProfile.from_mapping({"role":"research","operations":["offline_diagnostics"],"network":"proxy","external_mutation":False})

def test_candidate_not_verified():
    f=Fake()
    r=run_operation(PROFILES["research"],{"operation":"offline_diagnostics"},f)
    assert f.calls==1
    assert r["worker_ran"] is True
    assert r["eligible_for_release"] is False
    assert r["status"] != "approved_candidate"

def test_backend_failure_no_fallback():
    class Broken:
        calls=0
        def execute(self,op):
            self.calls+=1
            raise IsolationError("unavailable")
    b=Broken()
    r=run_operation(PROFILES["research"],{"operation":"offline_diagnostics"},b)
    assert r["status"]=="blocked" and b.calls==1

def test_image_tag_not_accepted():
    with pytest.raises(ValueError):
        DockerOfflineExecutor(image_id="python:latest")

def test_passed_status_without_evidence_not_completion():
    assert not completion_claim_allowed({"verification_status":"passed","observed_outcome":"claimed","evidence_handles":[]})

def test_wrong_daemon_endpoint_rejected():
    with pytest.raises(IsolationError):
        DockerOfflineExecutor(image_id="sha256:"+"a"*64,docker="/usr/bin/docker",socket="tcp://example.test:2375")

def test_inspection_rejects_wrong_network():
    e=DockerOfflineExecutor(image_id="sha256:"+"a"*64,docker="/usr/bin/docker")
    with pytest.raises(IsolationError):
        e._validate_inspection({"HostConfig":{"NetworkMode":"bridge"}})

def test_json_role_profiles_are_authoritative():
    from runtime.roles import load_profile
    assert load_profile("research").operations == frozenset({"offline_diagnostics"})
    assert load_profile("analyst").operations == frozenset({"offline_compute"})
    assert not load_profile("reviewer").operations

def test_unapproved_evidence_never_releases():
    f=Fake()
    r=run_operation(PROFILES["research"],
                    {"operation":"offline_diagnostics","verified_by":"worker"},f)
    assert r["status"]=="blocked" and f.calls==0
