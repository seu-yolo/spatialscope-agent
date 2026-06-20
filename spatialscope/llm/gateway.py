from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from spatialscope.agent.llm import LLMClient, llm_config_status
from spatialscope.agent.planner import fallback_parse_query, make_analysis_plan, validate_plan_steps
from spatialscope.domain.evidence import (
    CopilotAnswer,
    UIAction,
    EvidenceArtifact,
    EvidenceClaim,
    EvidencePack,
    ScientificFinding,
    flag_unsupported_definitive_language,
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
        "requested_mode": status.get("requested_mode"),
        "active_mode": status.get("active_mode"),
        "mode_label": status.get("mode_label"),
        "mode_reason": status.get("mode_reason"),
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


def _context_packs(context: dict[str, Any]) -> list[EvidencePack]:
    packs: list[EvidencePack] = []
    for item in context.get("evidence_packs", []) or []:
        try:
            packs.append(item if isinstance(item, EvidencePack) else EvidencePack.model_validate(item))
        except Exception:
            continue
    return packs


def _first_context_pack(packs: list[EvidencePack], kind: str) -> EvidencePack | None:
    return next((pack for pack in packs if pack.kind == kind), None)


def _fallback_contextual_answer(
    *,
    context: dict[str, Any],
    question: str,
    evidence_ids: list[str],
    focus: str,
) -> dict[str, Any]:
    packs = _context_packs(context)
    gene_pack = _first_context_pack(packs, "gene")
    cluster_pack = _first_context_pack(packs, "cluster")
    selection_pack = _first_context_pack(packs, "selection")
    q = question.lower()
    observations: list[str] = []
    caveats: list[str] = []
    actions: list[UIAction] = []
    direct = "规则解释（未调用外部 LLM）：当前回答只使用已生成的结构化证据。"

    if gene_pack and any(term in q for term in ["最高", "highest", "top", "cluster", "聚类", "平均"]):
        metrics = gene_pack.summary_metrics
        top = (metrics.get("top_clusters_by_mean") or [None])[0]
        by_cluster = metrics.get("by_cluster") or {}
        resolved = metrics.get("resolved_gene") or metrics.get("requested_gene") or context.get("selected_gene") or "selected gene"
        if top is not None and str(top) in by_cluster:
            top_stats = by_cluster[str(top)]
            mean_value = top_stats.get("mean")
            nonzero = top_stats.get("nonzero_fraction")
            direct = f"规则解释（未调用外部 LLM）：{resolved} 平均表达最高的是 cluster {top}，mean={mean_value}。"
            observations.append(f"cluster {top}: mean={mean_value}, nonzero_fraction={nonzero}")
            actions.append(
                UIAction(
                    action_id=f"focus_cluster_{top}",
                    type="highlight_cluster",
                    label=f"高亮 cluster {top}",
                    payload={"cluster": str(top)},
                )
            )

    if selection_pack and any(term in q for term in ["选择", "selected", "区域", "selection", "全局", "global", "差异"]):
        metrics = selection_pack.summary_metrics
        selected_count = metrics.get("selected_count")
        selected_mean = metrics.get("selected_mean")
        global_mean = metrics.get("global_mean")
        delta = metrics.get("selected_minus_global_mean")
        composition = metrics.get("cluster_composition") or {}
        direct = (
            "规则解释（未调用外部 LLM）：当前选择区域包含 "
            f"{selected_count} 个 observations；selected_mean={selected_mean}, global_mean={global_mean}, 差值={delta}。"
        )
        observations.append(f"cluster composition: {composition}")
        observations.append(f"selected/global mean difference: {delta}")
        actions.append(UIAction(action_id="clear_selection", type="clear_selection", label="清除选择", payload={}))

    if any(term in q for term in ["局限", "limitation", "caveat", "风险", "可靠"]):
        relevant = gene_pack or selection_pack or cluster_pack or (packs[0] if packs else None)
        caveats = list(relevant.caveats if relevant else [])
        direct = (
            "规则解释（未调用外部 LLM）：主要局限是这些观察来自当前视图和证据包，"
            "受表达来源、基因匹配、clipping 和选择区域影响。"
        )
        if caveats:
            observations.append(caveats[0])

    if any(term in q for term in ["下一步", "next", "worth", "运行", "分析"]):
        direct = "规则解释（未调用外部 LLM）：下一步最值得做的是围绕当前信号补充一个可验证的证据层。"
        if gene_pack:
            resolved = str(gene_pack.summary_metrics.get("resolved_gene") or context.get("selected_gene") or "")
            observations.append(f"当前 gene evidence: {resolved}")
            actions.append(UIAction(action_id="run_svg", type="run_svg", label="运行 SVG", payload={"gene": resolved}))
        if cluster_pack:
            cluster = str(cluster_pack.summary_metrics.get("cluster") or context.get("selected_cluster") or "")
            actions.append(
                UIAction(
                    action_id="run_neighborhood",
                    type="run_neighborhood",
                    label="运行 neighborhood",
                    payload={"cluster": cluster},
                )
            )

    if not actions:
        actions.append(UIAction(action_id="clear_selection", type="clear_selection", label="清除选择", payload={}))
    actions.append(UIAction(action_id="add_to_report", type="add_finding_to_report", label="加入报告", payload={}))
    if not caveats:
        caveats = [
            "解释只基于当前 EvidencePack 的数值摘要；没有使用原始矩阵、完整坐标或外部生物学事实。",
            "空间表达趋势不能单独证明机制或细胞类型。",
        ]
    if not observations and packs:
        observations = _pack_metric_lines(packs[0], limit=3)
    return CopilotAnswer(
        direct_answer=direct,
        observations=observations[:4],
        evidence_ids=evidence_ids,
        caveats=caveats[:3],
        suggested_actions=actions[:4],
        source="fallback",
    ).model_dump()


def _policy_quantitative_override(
    *,
    context: dict[str, Any],
    question: str,
) -> dict[str, Any] | None:
    packs = _context_packs(context)
    gene_pack = _first_context_pack(packs, "gene")
    selection_pack = _first_context_pack(packs, "selection")
    q = question.lower()
    if gene_pack and any(term in q for term in ["最高", "highest", "top", "cluster", "聚类", "平均"]):
        metrics = gene_pack.summary_metrics
        top = (metrics.get("top_clusters_by_mean") or [None])[0]
        by_cluster = metrics.get("by_cluster") or {}
        resolved = metrics.get("resolved_gene") or metrics.get("requested_gene") or context.get("selected_gene") or "selected gene"
        if top is not None and str(top) in by_cluster:
            stats = by_cluster[str(top)]
            mean_value = stats.get("mean")
            nonzero = stats.get("nonzero_fraction")
            return {
                "direct_answer": f"{resolved} 平均表达最高的是 cluster {top}，mean={mean_value}。",
                "observations": [f"cluster {top}: mean={mean_value}, nonzero_fraction={nonzero}"],
                "actions": [
                    UIAction(
                        action_id=f"focus_cluster_{top}",
                        type="highlight_cluster",
                        label=f"高亮 cluster {top}",
                        payload={"cluster": str(top)},
                    )
                ],
            }
    if selection_pack and any(term in q for term in ["选择", "selected", "区域", "selection", "全局", "global", "差异"]):
        metrics = selection_pack.summary_metrics
        return {
            "direct_answer": (
                f"当前选择区域包含 {metrics.get('selected_count')} 个 observations；"
                f"selected_mean={metrics.get('selected_mean')}, global_mean={metrics.get('global_mean')}, "
                f"差值={metrics.get('selected_minus_global_mean')}。"
            ),
            "observations": [
                f"cluster composition: {metrics.get('cluster_composition') or {}}",
                f"selected/global mean difference: {metrics.get('selected_minus_global_mean')}",
            ],
            "actions": [UIAction(action_id="clear_selection", type="clear_selection", label="清除选择", payload={})],
        }
    return None


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
        return bool(status.get("active_mode") == "full" and status.get("enabled") and self.client.enabled)

    @property
    def active_mode(self) -> str:
        return str(self.safe_status().get("active_mode") or "fallback")

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
            research_goals=parsed.get("requested_steps", []),
            requested_analyses=parsed.get("requested_steps", []),
            requested_genes=parsed.get("genes", []),
            user_constraints=parsed.get("constraints", []),
            dataset_facts=[
                f"observations={safe_profile.get('n_obs', 'NA')}",
                f"genes={safe_profile.get('n_vars', 'NA')}",
                f"spatial={safe_profile.get('has_spatial', False)}",
                f"matrix_state={safe_profile.get('matrix_state', 'unknown')}",
            ],
            dataset_assumptions=safe_profile.get("scientific_warnings", []),
            clarification_required=False,
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
                validated_steps = validate_plan_steps([step.model_dump() for step in plan.steps])
                if not validated_steps:
                    raise ValueError("LLM returned an empty validated plan.")
                plan.steps = [V2PlanStep.model_validate(step) for step in validated_steps]
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
        evidence_ids = [str(item) for item in context.get("evidence_ids", []) if str(item)]
        focus = _question_focus(question)
        started = now_iso()
        schema = {
            "type": "object",
            "properties": {
                "direct_answer": {"type": "string"},
                "answer": {"type": "string"},
                "observations": {"type": "array", "items": {"type": "string"}},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "caveats": {"type": "array", "items": {"type": "string"}},
                "caveat": {"type": "string"},
                "next_step": {"type": "string"},
                "suggested_actions": {
                    "type": "array",
                    "items": UIAction.model_json_schema(),
                },
            },
            "required": ["evidence_ids"],
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
                direct = str(payload.get("direct_answer") or payload.get("answer") or "").strip()
                caveats = [str(item).strip() for item in payload.get("caveats", []) if str(item).strip()]
                if not caveats and payload.get("caveat"):
                    caveats = [str(payload.get("caveat"))]
                flagged = flag_unsupported_definitive_language(direct)
                if flagged:
                    caveats.append(
                        "回答包含可能过度确定的措辞，界面已将其标记为需要谨慎复核："
                        + ", ".join(flagged[:4])
                    )
                actions: list[UIAction] = []
                for item in payload.get("suggested_actions", []) or []:
                    try:
                        actions.append(UIAction.model_validate(item))
                    except Exception:
                        continue
                policy = _policy_quantitative_override(context=context, question=question)
                if policy and (
                    not direct
                    or any(term in direct for term in ["无法确定", "不能确定", "无法判断", "not determine", "cannot determine"])
                ):
                    direct = str(policy["direct_answer"])
                    actions = [*policy.get("actions", []), *actions]
                    payload["observations"] = [*policy.get("observations", []), *payload.get("observations", [])]
                    caveats.append("直接数值结论由 deterministic EvidencePack policy 校正，LLM 只负责解释语境。")
                if not any(action.type == "add_finding_to_report" for action in actions):
                    actions.append(
                        UIAction(
                            action_id="add_to_report",
                            type="add_finding_to_report",
                            label="加入报告",
                            payload={},
                        )
                    )
                answer = CopilotAnswer(
                    direct_answer=direct,
                    observations=[str(item).strip() for item in payload.get("observations", []) if str(item).strip()],
                    evidence_ids=used_ids,
                    caveats=caveats
                    or ["回答只使用当前选择的 EvidencePack；没有访问原始矩阵、完整坐标或未提供的外部事实。"],
                    suggested_actions=actions,
                    source="llm",
                ).model_dump()
                answer.update({
                    "answer": direct,
                    "evidence_ids": used_ids,
                    "caveat": (caveats[0] if caveats else "回答只使用当前证据上下文。"),
                    "next_step": str(payload.get("next_step") or "").strip(),
                })
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
        answer = _fallback_contextual_answer(context=context, question=question, evidence_ids=evidence_ids, focus=focus)
        answer.update(
            {
                "answer": answer.get("direct_answer", ""),
                "caveat": (answer.get("caveats") or ["规则解释只使用当前证据。"])[0],
                "next_step": "切换 gene、cluster 或选择区域后重新提问。",
            }
        )
        return answer
