from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from spatialscope.agent.llm import LLMClient, llm_config_status
from spatialscope.agent.planner import fallback_parse_query, make_analysis_plan
from spatialscope.domain.evidence import EvidenceArtifact, EvidenceClaim, validate_claim_evidence
from spatialscope.domain.run_models import ResearchBrief, RepairDecision, V2AnalysisPlan, V2PlanStep
from spatialscope.llm.telemetry import LLMCallRecord, now_iso


def _safe_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    status = llm_config_status(env)
    return {
        "provider": status.get("provider"),
        "enabled": status.get("enabled"),
        "model": status.get("model"),
        "timeout_seconds": status.get("timeout_seconds"),
        "missing": status.get("missing", []),
        "fallback": status.get("fallback"),
    }


_RAW_PAYLOAD_KEYS = {
    "x",
    "adata_x",
    "raw_x",
    "raw_matrix",
    "matrix_values",
    "expression_matrix",
    "count_matrix",
    "coordinate_matrix",
    "coordinates",
    "spatial_coordinates",
    "obsm_spatial",
}


def _safe_for_llm(value: Any) -> Any:
    """Redact accidental matrix-like payloads before prompt assembly."""

    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace(".", "_").replace(" ", "_")
            if normalized in _RAW_PAYLOAD_KEYS or normalized.endswith("_matrix"):
                safe[str(key)] = "[redacted matrix-like payload]"
            else:
                safe[str(key)] = _safe_for_llm(item)
        return safe
    if isinstance(value, list):
        if len(value) > 12 and any(isinstance(item, (list, tuple, dict)) for item in value):
            return f"[redacted nested sequence with {len(value)} items]"
        return [_safe_for_llm(item) for item in value]
    if isinstance(value, tuple):
        return _safe_for_llm(list(value))
    return value


def _question_focus(question: str) -> str:
    lower = question.lower()
    if any(term in lower for term in ["marker", "rank", "cell type", "annotation", "解读", "细胞类型"]):
        return "marker_risk"
    if any(term in lower for term in ["caveat", "limitation", "uncertain", "risk", "trust", "局限", "风险", "可靠"]):
        return "caveat"
    if any(term in lower for term in ["gene", "expression", "表达", "基因"]):
        return "gene_expression"
    if any(term in lower for term in ["spatial", "umap", "cluster", "embedding", "空间", "聚类"]):
        return "spatial_structure"
    if any(term in lower for term in ["qc", "quality", "mitochondrial", "counts", "质量"]):
        return "qc"
    return "general"


def _focus_frame(
    *,
    focus: str,
    title: str,
    layer: str,
    table_text: str,
    warning_count: int,
) -> tuple[str, str, str]:
    if focus == "marker_risk":
        return (
            "For marker interpretation, the selected evidence should be treated as a guardrail: it can show whether QC "
            f"context is available for `{title}`, but it does not by itself validate marker ranking, cell identity, or "
            "biological mechanism. Marker claims should remain blocked or cautious unless the run has a safe expression "
            f"source (`{layer}`) plus linked marker tables.",
            "QC and figure/table evidence bound marker interpretation; they do not prove cell types or mechanisms.",
            "Open the marker table and expression-source record, then compare marker ranking with spatial and UMAP views.",
        )
    if focus == "caveat":
        return (
            f"The uncertainty is that `{title}` is selected evidence from `{layer}` rather than a definitive biological "
            f"claim. It should be interpreted with run warnings ({warning_count}) and linked tables ({table_text}).",
            "Grounded only in selected evidence, captions, table previews, and run warnings.",
            "Check whether the same signal appears in an independent linked figure or table.",
        )
    if focus == "gene_expression":
        return (
            f"For gene expression, `{title}` supports only a cautious spatial-expression read using `{layer}`. It does "
            "not infer mechanisms, cell identities, or unobserved genes beyond the selected evidence.",
            "Gene-level claims depend on gene matching and the recorded expression source.",
            "Compare the gene panel with marker ranking and cluster-colored spatial views.",
        )
    if focus == "spatial_structure":
        return (
            f"For spatial structure, `{title}` can support comparison between spatial organization and embedding/table "
            f"evidence ({table_text}), while keeping the selected palette and warnings visible.",
            "Spatial/UMAP agreement is exploratory and does not establish biological annotation by itself.",
            "Inspect linked Spatial and UMAP views side by side, then verify with marker evidence.",
        )
    if focus == "qc":
        return (
            f"For QC, `{title}` supports review of quality distributions and table summaries ({table_text}) before "
            "downstream interpretation.",
            "QC evidence supports data-quality review, not biological interpretation on its own.",
            "Inspect threshold choices and outliers before trusting downstream marker or spatial patterns.",
        )
    return (
        f"`{title}` is the selected evidence context. It can be used to compare figures, tables ({table_text}), and "
        "warnings without claiming more than the run produced.",
        "Grounded only in selected evidence, captions, table previews, and run warnings.",
        "Ask a narrower question about a cluster, gene, caveat, or table row.",
    )


@dataclass
class LLMGateway:
    client: LLMClient = field(default_factory=LLMClient.from_env)
    telemetry: list[dict[str, Any]] = field(default_factory=list)
    provider: str = ""

    @classmethod
    def from_env(cls) -> "LLMGateway":
        gateway = cls()
        gateway.provider = str(_safe_config().get("provider") or "disabled")
        return gateway

    @property
    def enabled(self) -> bool:
        status = llm_config_status()
        return bool(status.get("enabled") and self.client.enabled)

    def safe_status(self) -> dict[str, Any]:
        return _safe_config()

    def _record(
        self,
        *,
        purpose: str,
        started_at: str,
        success: bool,
        schema: str,
        validation: str,
        input_summary: dict[str, Any],
        fallback_reason: str = "",
    ) -> None:
        finished = now_iso()
        try:
            started_ts = time.mktime(time.strptime(started_at, "%Y-%m-%dT%H:%M:%S"))
            finished_ts = time.mktime(time.strptime(finished, "%Y-%m-%dT%H:%M:%S"))
            latency = round(finished_ts - started_ts, 3)
        except Exception:
            latency = None
        record = LLMCallRecord(
            purpose=purpose,
            provider=str(self.safe_status().get("provider") or "disabled"),
            model=str(self.safe_status().get("model") or ""),
            started_at=started_at,
            finished_at=finished,
            latency_sec=latency,
            success=success,
            structured_schema=schema,
            validation_outcome=validation,
            fallback_reason=fallback_reason,
            input_summary=input_summary,
        )
        self.telemetry.append(record.model_dump())

    def parse_research_brief(self, query: str, *, mode: str, dataset_profile: dict[str, Any] | None = None) -> ResearchBrief:
        started = now_iso()
        input_summary = {
            "query_chars": len(query),
            "mode": mode,
            "profile_keys": sorted((dataset_profile or {}).keys())[:20],
        }
        safe_profile = _safe_for_llm(dataset_profile or {})
        if self.enabled:
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Parse the user request into a ResearchBrief JSON object. "
                                "Only include genes explicitly requested. Do not include raw data.\n"
                                f"Schema: {json.dumps(ResearchBrief.model_json_schema(), ensure_ascii=False)}\n"
                                f"Dataset profile summary: {json.dumps(safe_profile, ensure_ascii=False)[:3000]}\n"
                                f"Request: {query}"
                            ),
                        }
                    ]
                )
                brief = ResearchBrief.model_validate({**payload, "source": "llm"})
                self._record(
                    purpose="parse_research_brief",
                    started_at=started,
                    success=True,
                    schema="ResearchBrief",
                    validation="passed",
                    input_summary=input_summary,
                )
                return brief
            except Exception as exc:  # noqa: BLE001
                self._record(
                    purpose="parse_research_brief",
                    started_at=started,
                    success=False,
                    schema="ResearchBrief",
                    validation="failed",
                    input_summary=input_summary,
                    fallback_reason=str(exc),
                )
        parsed = fallback_parse_query(query, mode)  # type: ignore[arg-type]
        brief = ResearchBrief(
            normalized_question=query.strip(),
            requested_analyses=parsed.get("requested_steps", []),
            requested_genes=parsed.get("genes", []),
            user_constraints=parsed.get("constraints", []),
            dataset_assumptions=safe_profile.get("scientific_warnings", []),
            confidence=float(parsed.get("confidence", 0.35)),
            source="fallback",
        )
        self._record(
            purpose="parse_research_brief",
            started_at=started,
            success=True,
            schema="ResearchBrief",
            validation="fallback",
            input_summary=input_summary,
            fallback_reason="" if self.enabled else "llm_disabled",
        )
        return brief

    def propose_plan(
        self,
        brief: ResearchBrief | dict[str, Any],
        *,
        mode: str,
        dataset_profile: dict[str, Any],
        tool_contracts: list[dict[str, Any]],
    ) -> V2AnalysisPlan:
        brief = ResearchBrief.model_validate(brief)
        started = now_iso()
        input_summary = {
            "mode": mode,
            "genes": brief.requested_genes[:8],
            "analyses": brief.requested_analyses[:8],
            "n_tools": len(tool_contracts),
        }
        safe_profile = _safe_for_llm(dataset_profile)
        if self.enabled:
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Propose a minimal dependency-valid SpatialScope plan as V2AnalysisPlan JSON. "
                                "Respect explicit requested genes and do not add annotation unless requested.\n"
                                f"Schema: {json.dumps(V2AnalysisPlan.model_json_schema(), ensure_ascii=False)}\n"
                                f"Research brief: {brief.model_dump_json()}\n"
                                f"Dataset profile: {json.dumps(safe_profile, ensure_ascii=False)[:3000]}\n"
                                f"Tool contracts: {json.dumps(tool_contracts, ensure_ascii=False)[:5000]}"
                            ),
                        }
                    ]
                )
                plan = V2AnalysisPlan.model_validate({**payload, "source": "llm", "mode": mode})
                self._record(
                    purpose="propose_plan",
                    started_at=started,
                    success=True,
                    schema="V2AnalysisPlan",
                    validation="passed",
                    input_summary=input_summary,
                )
                return plan
            except Exception as exc:  # noqa: BLE001
                self._record(
                    purpose="propose_plan",
                    started_at=started,
                    success=False,
                    schema="V2AnalysisPlan",
                    validation="failed",
                    input_summary=input_summary,
                    fallback_reason=str(exc),
                )
        parsed = {
            "genes": brief.requested_genes,
            "requested_steps": brief.requested_analyses,
            "intent": brief.normalized_question,
        }
        legacy_plan = make_analysis_plan(parsed, mode, dataset_summary=dataset_profile)  # type: ignore[arg-type]
        plan = V2AnalysisPlan(
            research_question=brief.normalized_question,
            profile_summary=dataset_profile,
            assumptions=brief.dataset_assumptions,
            rationale=legacy_plan.rationale,
            steps=[V2PlanStep.model_validate(step.model_dump()) for step in legacy_plan.steps],
            source="fallback",
            model_metadata=self.safe_status(),
            warnings=[],
            mode=mode,  # type: ignore[arg-type]
        )
        self._record(
            purpose="propose_plan",
            started_at=started,
            success=True,
            schema="V2AnalysisPlan",
            validation="fallback",
            input_summary=input_summary,
            fallback_reason="" if self.enabled else "llm_disabled",
        )
        return plan

    def propose_repair(
        self,
        *,
        failed_step: dict[str, Any],
        tool_result: dict[str, Any],
        tool_contract: dict[str, Any] | None = None,
        dataset_profile: dict[str, Any],
    ) -> RepairDecision:
        safe_profile = _safe_for_llm(dataset_profile)
        safe_result = _safe_for_llm(tool_result)
        if self.enabled:
            started = now_iso()
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Suggest a bounded repair decision as RepairDecision JSON. "
                                "Prefer retry_with_patch only for parameter changes that are safe from the public evidence. "
                                "Do not request raw matrices.\n"
                                f"Schema: {json.dumps(RepairDecision.model_json_schema(), ensure_ascii=False)}\n"
                                f"Failed step: {json.dumps(failed_step, ensure_ascii=False)}\n"
                                f"Tool result: {json.dumps(safe_result, ensure_ascii=False)[:2500]}\n"
                                f"Tool contract: {json.dumps(tool_contract or {}, ensure_ascii=False)[:2500]}\n"
                                f"Dataset profile: {json.dumps(safe_profile, ensure_ascii=False)[:2500]}"
                            ),
                        }
                    ]
                )
                decision = RepairDecision.model_validate(payload)
                self._record(
                    purpose="propose_repair",
                    started_at=started,
                    success=True,
                    schema="RepairDecision",
                    validation="passed",
                    input_summary={"tool": failed_step.get("tool"), "status": tool_result.get("status")},
                )
                return decision
            except Exception as exc:  # noqa: BLE001
                self._record(
                    purpose="propose_repair",
                    started_at=started,
                    success=False,
                    schema="RepairDecision",
                    validation="failed",
                    input_summary={"tool": failed_step.get("tool"), "status": tool_result.get("status")},
                    fallback_reason=str(exc),
                )
        return RepairDecision(
            action="abort",
            failed_step_id=str(failed_step.get("id") or failed_step.get("tool") or "unknown"),
            failure_category="rule_based",
            likely_cause=str(tool_result.get("summary") or "Tool failed."),
            recommended_actions=["Inspect the failed step and adjust parameters."],
            user_facing_message=str(tool_result.get("summary") or "Tool failed."),
            evidence=list(map(str, tool_result.get("errors", []) or [])),
            retry_safe=False,
        )

    def synthesize_evidence_claims(
        self,
        *,
        query: str,
        dataset_profile: dict[str, Any] | None = None,
        evidence_artifacts: list[dict[str, Any]] | list[EvidenceArtifact] | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
    ) -> list[EvidenceClaim]:
        artifacts = [
            item if isinstance(item, EvidenceArtifact) else EvidenceArtifact.model_validate(item)
            for item in (evidence_artifacts or [])
        ]
        if not artifacts:
            return []
        first = artifacts[0]
        claim = EvidenceClaim(
            claim=f"SpatialScope generated {len(artifacts)} evidence artifacts for the research question.",
            evidence_ids=[first.evidence_id],
            cautious_interpretation="These outputs support exploratory review, not definitive biological conclusions.",
            caveat=(
                "Interpretation depends on data quality, expression lineage, and selected parameters. "
                f"Trace records available: {len(execution_trace or [])}."
            ),
            suggested_next_step="Review the linked figure/table and confirm assumptions before making biological claims.",
        )
        validate_claim_evidence([claim], artifacts)
        return [claim]

    def synthesize_interpretation(
        self,
        *,
        query: str,
        dataset_profile: dict[str, Any] | None = None,
        evidence_artifacts: list[dict[str, Any]] | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        started = now_iso()
        safe_profile = _safe_for_llm(dataset_profile or {})
        evidence_summary = [
            {
                "kind": item.get("kind"),
                "title": item.get("title"),
                "caption": item.get("caption"),
                "data_layer": item.get("data_layer"),
                "tool": item.get("tool"),
            }
            for item in (evidence_artifacts or [])[:24]
        ]
        trace_summary = [
            {
                "node": item.get("node"),
                "tool": item.get("tool"),
                "status": item.get("status"),
                "summary": item.get("summary"),
                "warnings": item.get("warnings", []),
                "errors": item.get("errors", []),
            }
            for item in (execution_trace or [])[:32]
        ]
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "caveats": {"type": "array", "items": {"type": "string"}},
                "suggested_next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary"],
        }
        try:
            payload = self.client.complete_json(
                [
                    {
                        "role": "user",
                        "content": (
                            "Write a concise, cautious SpatialScope interpretation as JSON. "
                            "Use only the provided dataset profile, trace summaries, and evidence artifacts. "
                            "Do not invent biological conclusions, cell types, marker facts, p-values, or mechanisms. "
                            "Do not ask for or reference raw matrices.\n"
                            f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
                            f"Question: {query}\n"
                            f"Dataset profile: {json.dumps(safe_profile, ensure_ascii=False)[:2500]}\n"
                            f"Evidence artifacts: {json.dumps(evidence_summary, ensure_ascii=False)[:4500]}\n"
                            f"Trace summary: {json.dumps(trace_summary, ensure_ascii=False)[:4500]}\n"
                            f"Warnings: {json.dumps(warnings or [], ensure_ascii=False)[:1500]}"
                        ),
                    }
                ]
            )
            summary = str(payload.get("summary") or "").strip()
            caveats = [str(item).strip() for item in payload.get("caveats", []) if str(item).strip()]
            next_steps = [str(item).strip() for item in payload.get("suggested_next_steps", []) if str(item).strip()]
            parts = [summary]
            if caveats:
                parts.append("Caveats: " + " ".join(caveats[:3]))
            if next_steps:
                parts.append("Suggested next steps: " + " ".join(next_steps[:3]))
            self._record(
                purpose="synthesize_interpretation",
                started_at=started,
                success=bool(summary),
                schema="EvidenceInterpretation",
                validation="passed" if summary else "empty_summary",
                input_summary={
                    "artifacts": len(evidence_artifacts or []),
                    "trace_records": len(execution_trace or []),
                    "warnings": len(warnings or []),
                },
            )
            return "\n\n".join(part for part in parts if part)
        except Exception as exc:  # noqa: BLE001
            self._record(
                purpose="synthesize_interpretation",
                started_at=started,
                success=False,
                schema="EvidenceInterpretation",
                validation="failed",
                input_summary={
                    "artifacts": len(evidence_artifacts or []),
                    "trace_records": len(execution_trace or []),
                    "warnings": len(warnings or []),
                },
                fallback_reason=str(exc),
            )
            return None

    def answer_contextual_question(self, *, context: dict[str, Any], question: str = "Explain this view") -> dict[str, Any]:
        title = context.get("title") or context.get("figure") or "selected evidence"
        layer = context.get("data_layer") or context.get("layer") or "selected expression layer"
        tables = context.get("selected_table_titles") or []
        warning_count = len(context.get("warnings") or [])
        table_text = ", ".join(map(str, tables[:4])) if tables else "no selected tables"
        evidence_ids = [str(item) for item in context.get("evidence_ids", []) if str(item)]
        focus = _question_focus(question)
        focus_answer, focus_caveat, focus_next_step = _focus_frame(
            focus=focus,
            title=str(title),
            layer=str(layer),
            table_text=table_text,
            warning_count=warning_count,
        )
        started = now_iso()
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "caveat": {"type": "string"},
                "next_step": {"type": "string"},
            },
            "required": ["answer", "evidence_ids", "caveat"],
        }
        safe_context = _safe_for_llm(context)
        if self.enabled:
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Answer the user's question about selected SpatialScope evidence as JSON. "
                                "The answer must directly address the user's question focus and should not be a generic evidence summary. "
                                "Use only the selected evidence context, captions, table previews, warnings, and evidence IDs. "
                                "Do not invent biological mechanisms, cell types, raw values, p-values, or markers not present in context. "
                                "Always cite the exact evidence_ids you used.\n"
                                f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
                                f"Question focus: {focus}\n"
                                f"Question: {question}\n"
                                f"Selected evidence context: {json.dumps(safe_context, ensure_ascii=False)[:7000]}"
                            ),
                        }
                    ],
                    temperature=0.05,
                )
                used_ids = [str(item) for item in payload.get("evidence_ids", []) if str(item)]
                if not used_ids:
                    used_ids = evidence_ids
                answer = {
                    "answer": (focus_answer + " " + str(payload.get("answer") or "").strip()).strip(),
                    "evidence_ids": used_ids,
                    "caveat": str(payload.get("caveat") or focus_caveat).strip(),
                    "next_step": str(payload.get("next_step") or focus_next_step).strip(),
                    "source": "llm",
                }
                self._record(
                    purpose="contextual_copilot",
                    started_at=started,
                    success=bool(answer["answer"]),
                    schema="ContextualCopilotAnswer",
                    validation="passed" if answer["answer"] else "empty_answer",
                    input_summary={"evidence_ids": evidence_ids, "question_chars": len(question)},
                )
                return answer
            except Exception as exc:  # noqa: BLE001
                self._record(
                    purpose="contextual_copilot",
                    started_at=started,
                    success=False,
                    schema="ContextualCopilotAnswer",
                    validation="failed",
                    input_summary={"evidence_ids": evidence_ids, "question_chars": len(question)},
                    fallback_reason=str(exc),
                )

        self._record(
            purpose="contextual_copilot",
            started_at=started,
            success=True,
            schema="ContextualCopilotAnswer",
            validation="fallback",
            input_summary={"evidence_ids": evidence_ids, "question_chars": len(question)},
            fallback_reason="" if self.enabled else "llm_disabled",
        )
        return {
            "answer": focus_answer,
            "evidence_ids": evidence_ids,
            "caveat": focus_caveat,
            "next_step": focus_next_step,
            "source": "fallback",
        }
