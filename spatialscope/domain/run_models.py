from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from spatialscope.agent.state import RunMode


class ResearchBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    normalized_question: str
    research_goals: list[str] = Field(default_factory=list)
    requested_analyses: list[str] = Field(default_factory=list)
    requested_genes: list[str] = Field(default_factory=list)
    requested_comparisons: list[str] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    dataset_facts: list[str] = Field(default_factory=list)
    dataset_assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: Literal["llm", "fallback", "mock"] = "fallback"

    @field_validator(
        "research_goals",
        "requested_analyses",
        "requested_genes",
        "requested_comparisons",
        "user_constraints",
        "dataset_facts",
        "dataset_assumptions",
        "ambiguities",
        "unsupported_requests",
        mode="before",
    )
    @classmethod
    def _listify(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class ClarificationChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    label: str
    evidence: str = ""


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clarification_id: str
    type: Literal[
        "gene_resolution",
        "expression_source",
        "missing_spatial",
        "ambiguous_parameter",
        "unsafe_repair",
        "unsupported_request",
    ]
    question: str
    reason: str
    choices: list[ClarificationChoice] = Field(default_factory=list)
    recommended_value: str | None = None
    blocking: bool = True


class V2PlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_visible_title: str = ""
    tool: str
    scientific_purpose: str = ""
    dependencies: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    parameter_origins: dict[str, str] = Field(default_factory=dict)
    expected_evidence: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    optional: bool = False
    max_attempts: int = Field(default=2, ge=1, le=5)
    rationale: str = ""

    @model_validator(mode="after")
    def _fill_rationale(self) -> "V2PlanStep":
        if not self.rationale:
            self.rationale = self.scientific_purpose
        if not self.user_visible_title:
            self.user_visible_title = self.tool
        return self


class V2AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    research_question: str
    profile_summary: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    rationale: str = ""
    steps: list[V2PlanStep] = Field(default_factory=list)
    source: str = "fallback"
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    revision: int = 1
    mode: RunMode = "quick"


class RepairDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["retry_with_patch", "ask_user", "skip_optional", "abort"]
    failed_step_id: str
    failure_category: str = "unknown"
    likely_cause: str = ""
    parameter_patch: dict[str, Any] = Field(default_factory=dict)
    tool_replacement: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    user_facing_message: str = ""
    evidence: list[str] = Field(default_factory=list)
    retry_safe: bool = False
