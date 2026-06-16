from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolContract:
    name: str
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    common_failures: list[str] = field(default_factory=list)
    repair_strategy: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    status: str
    summary: str
    figures: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "figures": self.figures,
            "tables": self.tables,
            "observations": self.observations,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def missing_dependency(package: str, purpose: str) -> ImportError:
    return ImportError(
        f"{package} is required for {purpose}. Install the conda environment with "
        "`conda env create -f environment.yml` and activate `spatialscope-agent`."
    )


def safe_tool_call(func: Callable[..., ToolResult], *args: Any, **kwargs: Any) -> ToolResult:
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the agent records failures instead of crashing
        return ToolResult(
            status="failed",
            summary=f"{func.__name__} failed: {exc}",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

