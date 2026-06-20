from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from spatialscope.agent.llm import LLMClient, llm_config_status
from spatialscope.agent.planner import fallback_parse_query, make_analysis_plan, merge_with_mode_baseline
from spatialscope.domain.evidence import (
    EvidenceArtifact,
    EvidenceClaim,
    EvidencePack,
    ScientificFinding,
    validate_claim_evidence,
    validate_finding_evidence,
)
from spatialscope.domain.run_models import ResearchBrief, RepairDecision, V2AnalysisPlan, V2PlanStep
from spatialscope.llm.context import safe_for_llm
from spatialscope.llm.prompts import (
    contextual_copilot_prompt,
    findings_prompt,
    interpretation_prompt,
    plan_prompt,
    repair_prompt,
    research_brief_prompt,
)
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


def _safe_for_llm(value: Any) -> Any:
    return safe_for_llm(value)


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


def _pack_metric_lines(pack: EvidencePack, *, limit: int = 4) -> list[str]:
    lines: list[str] = []
    for key, value in pack.summary_metrics.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"{key}: {value}")
        elif isinstance(value, dict):
            compact = ", ".join(f"{k}={v}" for k, v in list(value.items())[:4])
            if compact:
                lines.append(f"{key}: {compact}")
        elif isinstance(value, list):
            lines.append(f"{key}: {len(value)} records")
        if len(lines) >= limit:
            break
    return lines


def _first_pack(packs: list[EvidencePack], *tools: str) -> EvidencePack | None:
    wanted = set(tools)
    return next((pack for pack in packs if pack.tool in wanted), None)


def _pack_ids(packs: list[EvidencePack], *tools: str) -> list[str]:
    wanted = set(tools)
    return list(dict.fromkeys(pack.evidence_id for pack in packs if pack.tool in wanted))


def _compact_tool_contracts(tool_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in tool_contracts:
        contract = item.get("contract", {}) if isinstance(item.get("contract"), dict) else {}
        compact.append(
            {
                "name": item.get("name"),
                "category": item.get("category"),
                "description": item.get("description"),
                "optional_fields": contract.get("optional_fields", [])[:8],
                "preconditions": contract.get("preconditions", [])[:4],
                "common_failures": contract.get("common_failures", [])[:4],
            }
        )
    return compact


def _compact_pack_for_llm(pack: EvidencePack) -> dict[str, Any]:
    return {
        "evidence_id": pack.evidence_id,
        "kind": pack.kind,
        "title": pack.title,
        "tool": pack.tool,
        "data_layer": pack.data_layer,
        "caption": pack.caption[:280],
        "summary_metrics": _safe_for_llm(pack.summary_metrics),
        "table_excerpt": pack.table_excerpt[:4],
        "caveats": pack.caveats[:4],
    }


COMPACT_PLAN_SCHEMA = {
    "type": "object",
    "required": ["research_question", "rationale", "steps"],
    "properties": {
        "research_question": {"type": "string"},
        "rationale": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "tool", "params", "rationale"],
                "properties": {
                    "id": {"type": "string"},
                    "tool": {"type": "string"},
                    "params": {"type": "object"},
                    "rationale": {"type": "string"},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "expected_evidence": {"type": "array", "items": {"type": "string"}},
                    "optional": {"type": "boolean"},
                },
            },
        },
    },
}


COMPACT_FINDINGS_SCHEMA = {
    "type": "object",
    "required": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "title", "statement", "evidence_ids", "caveats"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "title": {"type": "string"},
                    "statement": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "quantitative_support": {"type": "array", "items": {"type": "string"}},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "suggested_next_step": {"type": "string"},
                },
            },
        }
    },
}


def _fallback_findings(
    *,
    evidence_packs: list[EvidencePack],
    dataset_profile: dict[str, Any] | None,
    warnings: list[str] | None,
) -> list[ScientificFinding]:
    if not evidence_packs:
        return []
    findings: list[ScientificFinding] = []
    dataset_pack = _first_pack(evidence_packs, "load_h5ad") or evidence_packs[0]
    n_obs = (dataset_profile or {}).get("n_obs") or dataset_pack.summary_metrics.get("n_obs")
    n_vars = (dataset_profile or {}).get("n_vars") or dataset_pack.summary_metrics.get("n_vars")
    findings.append(
        ScientificFinding(
            finding_id="dataset_readiness",
            title="数据已先被检查，再进入分析",
            statement=f"Agent 在规划前读取了数据概况；当前记录到 {n_obs or 'NA'} 个 observations 与 {n_vars or 'NA'} 个 genes。",
            evidence_ids=[dataset_pack.evidence_id],
            quantitative_support=_pack_metric_lines(dataset_pack),
            caveats=["数据概况来自 AnnData 元数据与工具摘要，不等同于人工审阅完整实验设计。"],
            confidence=0.72,
            source="fallback",
            suggested_next_step="结合 QC 图和运行参数确认阈值是否适合该数据集。",
        )
    )

    qc_pack = _first_pack(evidence_packs, "run_qc")
    if qc_pack:
        retained = qc_pack.summary_metrics.get("retention_fraction")
        support = _pack_metric_lines(qc_pack)
        findings.append(
            ScientificFinding(
                finding_id="qc_boundary",
                title="QC 为下游解释设置了边界",
                statement=(
                    f"QC 步骤记录了过滤前后规模"
                    f"{'，保留比例约 ' + str(retained) if retained is not None else ''}；后续聚类和表达图应在该边界内解释。"
                ),
                evidence_ids=[qc_pack.evidence_id],
                quantitative_support=support,
                caveats=["QC 阈值是启发式默认值；极端样本仍需要人工检查。"],
                confidence=0.7,
                source="fallback",
                suggested_next_step="查看 total counts、detected genes 与 mitochondrial percentage 的分布。",
            )
        )

    structure_ids = _pack_ids(evidence_packs, "run_clustering", "plot_umap", "plot_spatial")
    structure_pack = _first_pack(evidence_packs, "run_clustering", "plot_umap", "plot_spatial")
    if structure_ids and structure_pack:
        clusters = structure_pack.summary_metrics.get("n_clusters")
        findings.append(
            ScientificFinding(
                finding_id="linked_structure",
                title="空间结构与 UMAP 可被并排比较",
                statement=(
                    "运行产生了 cluster/embedding/spatial 相关证据；"
                    f"{clusters} 个 cluster 被记录。" if clusters else "运行产生了 cluster/embedding/spatial 相关证据，可用于并排比较空间与表达空间结构。"
                ),
                evidence_ids=structure_ids[:4],
                quantitative_support=_pack_metric_lines(structure_pack),
                caveats=["聚类是探索性结构，不自动等同于细胞类型或发育谱系注释。"],
                confidence=0.68,
                source="fallback",
                suggested_next_step="在 Explore 中用相同 cluster 调色板同时查看 Spatial 与 UMAP。",
            )
        )

    gene_ids = _pack_ids(evidence_packs, "plot_gene_panel")
    gene_pack = _first_pack(evidence_packs, "plot_gene_panel")
    if gene_ids and gene_pack:
        genes = gene_pack.summary_metrics.get("resolved_genes") or gene_pack.summary_metrics.get("requested_genes")
        findings.append(
            ScientificFinding(
                finding_id="gene_panel_expression",
                title="请求基因的空间表达已有证据",
                statement=f"Gene panel 使用安全表达来源生成；涉及基因：{', '.join(map(str, genes[:8])) if isinstance(genes, list) else genes or '见证据表'}。",
                evidence_ids=gene_ids[:3],
                quantitative_support=_pack_metric_lines(gene_pack),
                caveats=["表达强弱受 layer、percentile clipping 和基因匹配结果影响。"],
                confidence=0.66,
                source="fallback",
                suggested_next_step="把基因空间表达与 cluster 空间图和 UMAP cluster 图联动查看。",
            )
        )

    marker_ids = _pack_ids(evidence_packs, "rank_markers")
    marker_pack = _first_pack(evidence_packs, "rank_markers")
    if marker_ids and marker_pack:
        findings.append(
            ScientificFinding(
                finding_id="marker_ranking_guardrail",
                title="Marker 排名只能作为候选线索",
                statement="Marker ranking 已产生可追溯表格和热图，但其结论应保持为候选差异表达线索。",
                evidence_ids=marker_ids[:3],
                quantitative_support=_pack_metric_lines(marker_pack),
                caveats=["Marker 排名不提供确认的细胞类型标签，也不证明机制。"],
                confidence=0.62,
                source="fallback",
                suggested_next_step="将 top markers 与已知生物学背景或外部注释流程交叉验证。",
            )
        )

    if warnings:
        warning_pack = evidence_packs[-1]
        findings.append(
            ScientificFinding(
                finding_id="interpretation_caveat",
                title="Warnings 定义了当前解释的上限",
                statement=str(warnings[0]),
                evidence_ids=[warning_pack.evidence_id],
                quantitative_support=[],
                caveats=["解决 warnings 前不应做强结论。"],
                confidence=0.58,
                source="fallback",
                suggested_next_step="优先处理 warning 中提到的输入、layer 或参数问题。",
            )
        )
    return findings[:5]


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
                            "content": research_brief_prompt(
                                schema=ResearchBrief.model_json_schema(),
                                query=query,
                                mode=mode,
                                dataset_profile=safe_profile,
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
        direct_llm_plan = os.getenv("SPATIALSCOPE_DIRECT_LLM_PLAN", "").lower() in {"1", "true", "yes"}
        if self.enabled and not direct_llm_plan:
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
                rationale=(
                    "LLM parsed the research question; deterministic baseline planner produced a validated, "
                    "mode-appropriate tool plan for latency and safety."
                ),
                steps=[V2PlanStep.model_validate(step.model_dump()) for step in legacy_plan.steps],
                source="llm_brief_baseline" if brief.source == "llm" else "fallback",
                model_metadata=self.safe_status(),
                warnings=["Direct LLM plan generation is disabled by default; set SPATIALSCOPE_DIRECT_LLM_PLAN=1 to enable."],
                mode=mode,  # type: ignore[arg-type]
            )
            self._record(
                purpose="propose_plan",
                started_at=started,
                success=True,
                schema="V2AnalysisPlan",
                validation="llm_brief_baseline",
                input_summary=input_summary,
                fallback_reason="direct_llm_plan_disabled_for_latency",
            )
            return plan
        if self.enabled:
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": plan_prompt(
                                schema=COMPACT_PLAN_SCHEMA,
                                research_brief=brief.model_dump_json(),
                                mode=mode,
                                dataset_profile=safe_profile,
                                tool_contracts=_compact_tool_contracts(tool_contracts),
                            ),
                        }
                    ]
                )
                plan = V2AnalysisPlan.model_validate({**payload, "source": "llm", "mode": mode})
                parsed_for_baseline = {
                    "genes": brief.requested_genes,
                    "requested_steps": brief.requested_analyses,
                    "intent": brief.normalized_question,
                }
                merged_steps = merge_with_mode_baseline(
                    [step.model_dump() for step in plan.steps],
                    parsed_for_baseline,
                    mode,  # type: ignore[arg-type]
                )
                plan.steps = [V2PlanStep.model_validate(step) for step in merged_steps]
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
                            "content": repair_prompt(
                                schema=RepairDecision.model_json_schema(),
                                failed_step=failed_step,
                                tool_result=safe_result,
                                tool_contract=tool_contract or {},
                                dataset_profile=safe_profile,
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

    def synthesize_findings(
        self,
        *,
        query: str,
        dataset_profile: dict[str, Any] | None = None,
        evidence_packs: list[dict[str, Any]] | list[EvidencePack] | None = None,
        warnings: list[str] | None = None,
    ) -> list[ScientificFinding]:
        packs = [
            item if isinstance(item, EvidencePack) else EvidencePack.model_validate(item)
            for item in (evidence_packs or [])
        ]
        if not packs:
            return []
        started = now_iso()
        safe_profile = _safe_for_llm(dataset_profile or {})
        safe_packs = [_compact_pack_for_llm(pack) for pack in packs[:18]]
        input_summary = {"packs": len(packs), "warnings": len(warnings or []), "query_chars": len(query)}
        direct_llm_findings = os.getenv("SPATIALSCOPE_DIRECT_LLM_FINDINGS", "").lower() in {"1", "true", "yes"}
        if self.enabled and not direct_llm_findings:
            findings = _fallback_findings(evidence_packs=packs, dataset_profile=dataset_profile, warnings=warnings)
            for finding in findings:
                finding.source = "tool"
            self._record(
                purpose="synthesize_findings",
                started_at=started,
                success=True,
                schema="ScientificFinding[]",
                validation="tool_evidence_synthesis",
                input_summary=input_summary,
                fallback_reason="direct_llm_findings_disabled_for_latency",
            )
            validate_finding_evidence(findings, packs)
            return findings
        if self.enabled:
            try:
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": findings_prompt(
                                schema=COMPACT_FINDINGS_SCHEMA,
                                query=query,
                                dataset_profile=safe_profile,
                                evidence_packs=safe_packs,
                                warnings=list(map(str, warnings or [])),
                            ),
                        }
                    ],
                    temperature=0.08,
                )
                raw_findings = payload.get("findings", payload if isinstance(payload, list) else [])
                findings = [ScientificFinding.model_validate({**item, "source": "llm"}) for item in raw_findings[:5]]
                valid_ids = {pack.evidence_id for pack in packs}
                for finding in findings:
                    finding.evidence_ids = [evidence_id for evidence_id in finding.evidence_ids if evidence_id in valid_ids]
                findings = [finding for finding in findings if finding.evidence_ids and finding.statement.strip()]
                validate_finding_evidence(findings, packs)
                if len(findings) >= 2:
                    self._record(
                        purpose="synthesize_findings",
                        started_at=started,
                        success=True,
                        schema="ScientificFinding[]",
                        validation="passed",
                        input_summary=input_summary,
                    )
                    return findings[:5]
                raise ValueError("LLM returned too few evidence-grounded findings.")
            except Exception as exc:  # noqa: BLE001
                self._record(
                    purpose="synthesize_findings",
                    started_at=started,
                    success=False,
                    schema="ScientificFinding[]",
                    validation="failed",
                    input_summary=input_summary,
                    fallback_reason=str(exc),
                )
        findings = _fallback_findings(evidence_packs=packs, dataset_profile=dataset_profile, warnings=warnings)
        self._record(
            purpose="synthesize_findings",
            started_at=started,
            success=True,
            schema="ScientificFinding[]",
            validation="fallback",
            input_summary=input_summary,
            fallback_reason="" if self.enabled else "llm_disabled",
        )
        validate_finding_evidence(findings, packs)
        return findings

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
        findings: list[dict[str, Any]] | list[ScientificFinding] | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        started = now_iso()
        safe_profile = _safe_for_llm(dataset_profile or {})
        finding_payload = [
            item.model_dump() if isinstance(item, ScientificFinding) else dict(item)
            for item in (findings or [])
        ]
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
            prompt = (
                interpretation_prompt(
                    schema=schema,
                    query=query,
                    dataset_profile=safe_profile,
                    findings=_safe_for_llm(finding_payload),
                    warnings=list(map(str, warnings or [])),
                )
                if finding_payload
                else (
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
                )
            )
            payload = self.client.complete_json(
                [
                    {
                        "role": "user",
                        "content": prompt,
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

    def answer_contextual_question(
        self,
        *,
        context: dict[str, Any],
        question: str = "Explain this view",
        conversation_memory: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
                prompt = contextual_copilot_prompt(
                    schema=schema,
                    question=question,
                    conversation_memory=conversation_memory or [],
                    selected_context=safe_context,
                    focus=focus,
                )
                payload = self.client.complete_json(
                    [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    temperature=0.05,
                )
                used_ids = [str(item) for item in payload.get("evidence_ids", []) if str(item)]
                selected_set = set(evidence_ids)
                used_ids = [evidence_id for evidence_id in used_ids if evidence_id in selected_set]
                if not used_ids and evidence_ids:
                    used_ids = evidence_ids
                answer = {
                    "answer": str(payload.get("answer") or "").strip(),
                    "evidence_ids": used_ids,
                    "caveat": str(payload.get("caveat") or focus_caveat).strip(),
                    "next_step": str(payload.get("next_step") or focus_next_step).strip(),
                    "source": "llm",
                }
                if not answer["answer"]:
                    raise ValueError("LLM returned an empty copilot answer.")
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
