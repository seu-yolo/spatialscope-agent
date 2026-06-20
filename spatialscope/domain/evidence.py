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
    kind: Literal[
        "dataset",
        "qc",
        "cluster",
        "gene",
        "selection",
        "marker",
        "svg",
        "neighborhood",
        "figure",
        "table",
        "metric",
        "text",
    ]
    title: str
    tool: str = ""
    path: str = ""
    data_layer: str | None = ""
    figure_ids: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)
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
    review_status: Literal["unreviewed", "accepted", "edited", "rejected"] = "unreviewed"


class UIAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    type: Literal[
        "set_gene",
        "highlight_cluster",
        "set_expression_source",
        "select_observations",
        "clear_selection",
        "open_marker_table",
        "run_svg",
        "run_neighborhood",
        "compare_gene",
        "add_finding_to_report",
    ]
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CopilotContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    research_question: str = ""
    selected_gene: str | None = None
    selected_cluster: str | None = None
    selected_obs_ids: list[str] = Field(default_factory=list)
    expression_source: str | None = None
    clip_percentiles: tuple[float, float] = (1.0, 99.0)
    active_view: str = "gene"
    evidence_packs: list[EvidencePack] = Field(default_factory=list)
    recent_turns: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CopilotAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direct_answer: str
    observations: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    suggested_actions: list[UIAction] = Field(default_factory=list)
    source: Literal["llm", "fallback", "mock"] = "fallback"


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    turn_id: str
    role: Literal["user", "assistant", "system"]
    stage: Literal["project", "plan", "run", "explore", "report"]
    content: str
    source: Literal["user", "llm", "fallback", "tool"]
    evidence_ids: list[str] = Field(default_factory=list)
    ui_actions: list[UIAction] = Field(default_factory=list)
    created_at: str


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
    "证明",
    "确定说明",
    "因果导致",
    "揭示机制",
]


def flag_unsupported_definitive_language(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in DEFINITIVE_LANGUAGE if phrase in lowered]
