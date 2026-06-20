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


class EvidencePack(BaseModel):
    """Compact, LLM-safe evidence unit derived from one tool artifact."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    kind: Literal["figure", "table", "metric", "text"]
    title: str
    tool: str = ""
    path: str = ""
    data_layer: str = ""
    caption: str = ""
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    table_excerpt: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)
    safe_for_llm: bool = True

    @model_validator(mode="after")
    def _bound_payload(self) -> "EvidencePack":
        if len(self.table_excerpt) > 8:
            self.table_excerpt = self.table_excerpt[:8]
        if len(self.caveats) > 8:
            self.caveats = self.caveats[:8]
        return self


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    cautious_interpretation: str = ""
    caveat: str = ""
    suggested_next_step: str = ""
    review_status: str = "unreviewed"


class ScientificFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    title: str
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    quantitative_support: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: Literal["llm", "fallback", "tool"] = "fallback"
    suggested_next_step: str = ""


def validate_claim_evidence(claims: list[EvidenceClaim], artifacts: list[EvidenceArtifact]) -> None:
    valid = {artifact.evidence_id for artifact in artifacts}
    for claim in claims:
        missing = [evidence_id for evidence_id in claim.evidence_ids if evidence_id not in valid]
        if missing:
            raise ValueError(f"Evidence claim references missing evidence IDs: {', '.join(missing)}")


def validate_finding_evidence(findings: list[ScientificFinding], evidence_packs: list[EvidencePack]) -> None:
    valid = {pack.evidence_id for pack in evidence_packs}
    for finding in findings:
        missing = [evidence_id for evidence_id in finding.evidence_ids if evidence_id not in valid]
        if missing:
            raise ValueError(f"Scientific finding references missing evidence IDs: {', '.join(missing)}")


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
