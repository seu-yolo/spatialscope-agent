from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    kind: Literal["figure", "table", "metric", "text"]
    title: str
    path: str = ""
    relpath: str = ""
    producer_step_id: str = ""
    tool: str = ""
    data_layer: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    caption: str = ""
    scientific_caveats: list[str] = Field(default_factory=list)


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    cautious_interpretation: str = ""
    caveat: str = ""
    suggested_next_step: str = ""
    review_status: str = "unreviewed"


def validate_claim_evidence(claims: list[EvidenceClaim], artifacts: list[EvidenceArtifact]) -> None:
    valid = {artifact.evidence_id for artifact in artifacts}
    for claim in claims:
        missing = [evidence_id for evidence_id in claim.evidence_ids if evidence_id not in valid]
        if missing:
            raise ValueError(f"Evidence claim references missing evidence IDs: {', '.join(missing)}")


DEFINITIVE_LANGUAGE = [
    "proves",
    "proved",
    "definitively identifies",
    "definitively identify",
    "reveals the mechanism",
    "causes",
    "causal",
    "establishes mechanism",
]


def flag_unsupported_definitive_language(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in DEFINITIVE_LANGUAGE if phrase in lowered]
