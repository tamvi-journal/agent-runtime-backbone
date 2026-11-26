"""Role definitions are trusted operator configuration, not worker claims."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from importlib.resources import files
import json

OPERATIONS = frozenset({"offline_diagnostics", "offline_compute", "offline_analyze", "read_registered_resource"})

@dataclass(frozen=True)
class RoleProfile:
    role: str
    operations: frozenset[str]
    network: str = "deny"
    external_mutation: bool = False

    def __post_init__(self):
        if (not isinstance(self.role, str) or not self.role.strip()
                or not isinstance(self.operations, frozenset)
                or not self.operations <= OPERATIONS
                or self.network not in {"deny","brokered_read"} or self.external_mutation is not False
                or ("read_registered_resource" in self.operations) != (self.network == "brokered_read")):
            raise ValueError("unsupported_role_capability")

    @classmethod
    def from_mapping(cls, value: Mapping) -> RoleProfile:
        if not isinstance(value, Mapping) or set(value) != {"role", "operations", "network", "external_mutation"}:
            raise ValueError("invalid_role_fields")
        ops = value["operations"]
        if not isinstance(ops, list) or not all(isinstance(x, str) for x in ops):
            raise ValueError("invalid_operations")
        return cls(value["role"], frozenset(ops), value["network"], value["external_mutation"])

def load_profile(name: str) -> RoleProfile:
    if name not in {"research", "analyst", "reviewer"}:
        raise ValueError("unknown_builtin_role")
    data = json.loads(files("runtime").joinpath("profiles", name + ".json").read_text())
    profile = RoleProfile.from_mapping(data)
    if profile.role != name:
        raise ValueError("profile_name_mismatch")
    return profile

PROFILES = {name: load_profile(name) for name in ("research", "analyst", "reviewer")}
