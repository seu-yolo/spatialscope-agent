from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from spatialscope.agent.state import RunMode


PlanSource = Literal["llm", "rule_based", "user_edited"]


class ParsedRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: str = "spatial transcriptomics exploration"
    requested_steps: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list, max_length=12)
    preferred_mode: RunMode = "quick"
    constraints: list[str] = Field(default_factory=list)
    notes: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("requested_steps", "genes", "constraints", mode="before")
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=96)
    params: dict[str, Any] = Field(default_factory=dict)
    parameter_origins: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    scientific_purpose: str = ""
    rationale: str = ""
    optional: bool = False
    max_attempts: int = Field(default=2, ge=1, le=5)


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: RunMode
    source: PlanSource = "rule_based"
    rationale: str = ""
    steps: list[PlanStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_step_ids(self) -> "AnalysisPlan":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan step ids must be unique.")
        return self


def normalize_plan_steps(steps: list[dict[str, Any]], *, allowed_tools: set[str] | None = None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_step in steps:
        step = PlanStep.model_validate(raw_step)
        if allowed_tools is not None and step.tool not in allowed_tools:
            raise ValueError(f"Unknown analysis tool in plan: {step.tool}")
        normalized.append(step.model_dump())
    AnalysisPlan(mode="quick", steps=[PlanStep.model_validate(step) for step in normalized])
    return normalized


def analysis_plan_json_schema() -> dict[str, Any]:
    return AnalysisPlan.model_json_schema()


def parsed_request_json_schema() -> dict[str, Any]:
    return ParsedRequest.model_json_schema()
