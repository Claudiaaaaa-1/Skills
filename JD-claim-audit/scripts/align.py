#!/usr/bin/env python3
"""Evidence alignment and gap detection for sku-claim-audit.

Alignment checks object, scope, value and evidence status. Gap detection only
produces candidates: the model still writes the explanation and the judgement,
keeping facts, explanations and verdicts separable.
"""

import re

CHECKED_DIMS = ["对象", "时间", "范围", "数值", "资质"]

GAP_TYPES = {
    "数值冲突",
    "对象错位",
    "范围越界",
    "时间或批次失效",
    "资质缺失",
    "证据未核验",
    "因果无据",
    "条件泛化",
    "图文不一致",
    "无断裂",
}


def _numeric(value):
    """Extract a comparable number from a value like '100%' or '0%'."""
    if value is None:
        return None
    text = str(value).strip().replace("％", "%")
    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", text)
    return float(match.group(1)) if match else None


def _scope_matches(claim_scope: dict, evidence_scope: dict, sku_id: str) -> bool:
    """Return False when evidence covers a different SKU, batch or validity window."""
    claim_scope = claim_scope or {}
    evidence_scope = evidence_scope or {}

    claim_sku = claim_scope.get("sku")
    evidence_sku = evidence_scope.get("sku")
    if claim_sku and evidence_sku and claim_sku != evidence_sku:
        return False
    if claim_sku and not evidence_sku and claim_sku != sku_id:
        return False

    if claim_scope.get("batch") and evidence_scope.get("batch"):
        if claim_scope["batch"] != evidence_scope["batch"]:
            return False

    if evidence_scope.get("expired") is True:
        return False
    return True


def align(claims: list, evidence: list, page: dict) -> list:
    """Attach evidence to each claim and record the alignment result in place."""
    sku_id = page.get("sku_id", "")

    for claim in claims:
        requires = claim.get("requires_evidence_types", []) or []
        if claim.get("type") == "主观修辞" or not requires:
            claim["evidence_refs"] = []
            claim["alignment"] = {
                "matched": [],
                "status": "not_required",
                "checked_dims": [],
                "note": "纯表达或无需证据，不做对齐",
            }
            continue

        candidates = [e for e in evidence if e.get("subject") == claim.get("subject")]
        matched, mismatched = [], []
        for item in candidates:
            if _scope_matches(claim.get("scope", {}), item.get("scope", {}), sku_id):
                matched.append(item)
            else:
                mismatched.append(item)

        if matched:
            status = "matched"
            note = "对象与范围一致，进入数值与资质核验"
        elif mismatched:
            status = "scope_mismatch"
            note = "存在同对象证据，但规格、批次或有效期不覆盖本主张"
        else:
            status = "missing"
            note = "未找到指向该主张对象的证据"

        claim["evidence_refs"] = [e["evidence_id"] for e in matched]
        claim["alignment"] = {
            "matched": [e["evidence_id"] for e in matched],
            "status": status,
            "checked_dims": CHECKED_DIMS if matched else [],
            "note": note,
        }
    return claims


def detect_gaps(claims: list, evidence: list) -> list:
    """Produce a gap candidate for every claim, including a 'no gap' record.

    Pure expressions and fully aligned claims get an explicit ``无断裂`` record
    rather than no record at all, so the ledger can prove every claim was seen.
    """
    by_id = {e["evidence_id"]: e for e in evidence}
    gaps = []

    for claim in claims:
        alignment = claim.get("alignment", {})
        refs = [by_id[i] for i in alignment.get("matched", []) if i in by_id]
        gap_type = "无断裂"
        fact = "主张无需证据或已与证据对齐"
        explanation = "未发现可解释的信息断裂"
        judgement = "可接受"

        if alignment.get("status") == "not_required":
            fact = "该主张为主观修辞或无需证据的表达"
            explanation = "纯表达不构成可验证主张，不触发证据要求"
            judgement = "无需判断"
        elif alignment.get("status") == "scope_mismatch":
            gap_type = "范围越界"
            fact = "存在同对象证据，但适用规格、批次或有效期不覆盖本主张"
            explanation = "证据不可直接复用，需人审确认适用范围"
            judgement = "待核验"
        elif not refs:
            gap_type = "资质缺失"
            fact = f"主张「{claim.get('text', '')}」要求 {claim.get('requires_evidence_types', [])}，当前无对应证据"
            explanation = "证据不完整时不能判断主张成立，也不能判其虚假"
            judgement = "待补证"
        else:
            claim_number = _numeric(claim.get("value"))
            conflicting = None
            for item in refs:
                evidence_number = _numeric(item.get("value"))
                if (
                    claim_number is not None
                    and evidence_number is not None
                    and claim_number != evidence_number
                ):
                    conflicting = item
                    break

            if conflicting is not None:
                gap_type = "数值冲突"
                fact = f"主张写 {claim.get('value')}，证据 {conflicting['evidence_id']} 写 {conflicting.get('value')}"
                explanation = "同一对象的量化陈述不可同时成立"
                judgement = "不可接受"
            else:
                expired = next((i for i in refs if i.get("status") == "expired"), None)
                unverified = next(
                    (
                        i
                        for i in refs
                        if i.get("status") == "unverified"
                        and i.get("level") == "需交叉验证"
                    ),
                    None,
                )
                if expired is not None:
                    gap_type = "时间或批次失效"
                    fact = f"证据 {expired['evidence_id']} 已过期或被注销"
                    explanation = "编号格式正确不等于资质有效"
                    judgement = "待核验"
                elif unverified is not None:
                    gap_type = "证据未核验"
                    fact = f"证据 {unverified['evidence_id']} 仅校验格式：{unverified.get('verified_against', '')}"
                    explanation = "未查询权威库，不能据此给出确定结论"
                    judgement = "待核验"

        gaps.append(
            {
                "claim_id": claim["claim_id"],
                "gap_type": gap_type,
                "fact": fact,
                "explanation": explanation,
                "judgement": judgement,
                "acceptable": gap_type == "无断裂",
                "evidence_refs": alignment.get("matched", []),
            }
        )
    return gaps
