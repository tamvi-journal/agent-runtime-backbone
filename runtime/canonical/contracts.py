from __future__ import annotations

from typing import Literal, TypedDict

PromotionTarget = Literal["candidate", "canonical_reference", "non_authoritative"]
PromotionDecisionName = Literal[
    "allow_candidate",
    "stay_non_authoritative",
    "promotion_blocked",
    "needs_approval",
]
PromotionOriginKind = Literal["mainbrain", "worker", "delegate"]
DisplayState = Literal["success", "warning", "failure"]


class PromotionRequest(TypedDict):
    verification_status: str
    completion_claim_allowed: bool
    commit_status: str
    display_state: DisplayState | str
    evidence_handles: list[str]
    reasons: list[str]
    current_canonical_status: str
    requested_target: PromotionTarget | str
    origin_kind: PromotionOriginKind | str


class PromotionDecision(TypedDict):
    decision: PromotionDecisionName | str
    target_status: str
    promotion_allowed: bool
    reasons: list[str]
    message: str
