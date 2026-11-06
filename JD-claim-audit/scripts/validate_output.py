#!/usr/bin/env python3
"""Output contract validation for sku-claim-audit ledgers."""

import json
import sys
from pathlib import Path

TOP_LEVEL = ("page", "claims", "evidence", "gaps", "decision", "boundary")
STATES = {"PASS", "BLOCK", "REQUEST_EVIDENCE", "HUMAN_REVIEW"}
CLAIM_TYPES = {"可验证事实", "主观修辞", "受约束承诺"}
EVIDENCE_LEVELS = {"强事实", "需交叉验证", "纯表达"}
EVIDENCE_STATUS = {"valid", "expired", "unverified", "missing"}
ALIGNMENT_STATUS = {"matched", "missing", "scope_mismatch", "not_required"}
GAP_TYPES = {
    "数值冲突", "对象错位", "范围越界", "时间或批次失效", "资质缺失",
    "证据未核验", "因果无据", "条件泛化", "图文不一致", "无断裂",
}
SEVERITY = {"PASS": 0, "REQUEST_EVIDENCE": 1, "HUMAN_REVIEW": 2, "BLOCK": 3}


def validate(ledger: dict) -> tuple:
    """Return (is_valid, errors). Errors is empty when the contract holds."""
    errors = []

    for key in TOP_LEVEL:
        if key not in ledger:
            errors.append(f"缺少顶层字段: {key}")
    if errors:
        return False, errors

    if not isinstance(ledger["boundary"], str) or not ledger["boundary"].strip():
        errors.append("boundary 必须是非空字符串")

    claim_ids = set()
    for index, claim in enumerate(ledger["claims"]):
        cid = claim.get("claim_id", f"<index {index}>")
        claim_ids.add(cid)
        for key in ("claim_id", "text", "type", "subject", "alignment", "state"):
            if key not in claim:
                errors.append(f"{cid}: 缺少 {key}")
        if claim.get("type") not in CLAIM_TYPES:
            errors.append(f"{cid}: 非法 claim.type = {claim.get('type')}")
        if claim.get("state") not in STATES:
            errors.append(f"{cid}: 非法 state = {claim.get('state')}")
        alignment = claim.get("alignment", {})
        if alignment.get("status") not in ALIGNMENT_STATUS:
            errors.append(f"{cid}: 非法 alignment.status = {alignment.get('status')}")

    evidence_ids = set()
    for index, item in enumerate(ledger["evidence"]):
        eid = item.get("evidence_id", f"<index {index}>")
        evidence_ids.add(eid)
        for key in ("evidence_id", "source", "level", "status", "verified_against"):
            if key not in item:
                errors.append(f"{eid}: 缺少 {key}")
        if item.get("level") not in EVIDENCE_LEVELS:
            errors.append(f"{eid}: 非法 level = {item.get('level')}")
        if item.get("status") not in EVIDENCE_STATUS:
            errors.append(f"{eid}: 非法 status = {item.get('status')}")

    for gap in ledger["gaps"]:
        if gap.get("claim_id") not in claim_ids:
            errors.append(f"gap 引用了不存在的 claim_id: {gap.get('claim_id')}")
        if gap.get("gap_type") not in GAP_TYPES:
            errors.append(f"非法 gap_type = {gap.get('gap_type')}")
        for key in ("fact", "explanation", "judgement"):
            if not gap.get(key):
                errors.append(f"gap {gap.get('claim_id')}: {key} 不能为空")
        for ref in gap.get("evidence_refs", []):
            if ref not in evidence_ids:
                errors.append(f"gap 引用了不存在的 evidence_id: {ref}")

    decision = ledger["decision"]
    if decision.get("state") not in STATES:
        errors.append(f"非法 decision.state = {decision.get('state')}")
    claim_states = decision.get("claim_states", {})
    if set(claim_states) != claim_ids:
        errors.append("decision.claim_states 与 claims 列表不一致")
    for cid, state in claim_states.items():
        if state not in STATES:
            errors.append(f"{cid}: claim_states 中出现非法状态 {state}")
    if claim_states and decision.get("state") in STATES:
        expected = max(claim_states.values(), key=lambda s: SEVERITY[s])
        if decision["state"] != expected:
            errors.append(
                f"页面级状态 {decision['state']} 与主张级最严重状态 {expected} 不一致"
            )
    for claim in ledger["claims"]:
        cid = claim.get("claim_id")
        if claim_states.get(cid) != claim.get("state"):
            errors.append(f"{cid}: decision.claim_states 与 claim.state 不一致")

    return len(errors) == 0, errors


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 validate_output.py <ledger.json>")
        return 2
    path = Path(sys.argv[1])
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read ledger: {exc}")
        return 2

    valid, errors = validate(ledger)
    if valid:
        print(f"PASS: {path.name} 符合输出契约")
        return 0
    print(f"FAIL: {path.name} 有 {len(errors)} 个问题")
    for error in errors:
        print(f"  - {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
