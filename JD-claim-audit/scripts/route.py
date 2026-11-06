#!/usr/bin/env python3
"""Four-state decision routing for sku-claim-audit.

Rules are used for recall and labelling, not for the final verdict. The only
short-circuit is an absolute hard redline. A page-level state is derived from
claim-level states but never replaces them.
"""

GAP_STATE = {
    "无断裂": "PASS",
    "数值冲突": "BLOCK",
    "对象错位": "BLOCK",
    "资质缺失": "REQUEST_EVIDENCE",
    "条件泛化": "REQUEST_EVIDENCE",
    "因果无据": "REQUEST_EVIDENCE",
    "证据未核验": "HUMAN_REVIEW",
    "时间或批次失效": "HUMAN_REVIEW",
    "范围越界": "HUMAN_REVIEW",
    "图文不一致": "HUMAN_REVIEW",
}

SEVERITY = {
    "PASS": 0,
    "REQUEST_EVIDENCE": 1,
    "HUMAN_REVIEW": 2,
    "BLOCK": 3,
}

CONFIDENCE = {
    "PASS": 0.88,
    "REQUEST_EVIDENCE": 0.72,
    "HUMAN_REVIEW": 0.61,
    "BLOCK": 0.94,
}

STATE_REASON = {
    "PASS": "所有主张已对齐或为纯表达，未发现不可接受的信息断裂",
    "REQUEST_EVIDENCE": "存在证据缺失或条件泛化，需商家补充材料后重跑",
    "HUMAN_REVIEW": "存在需外部核验的断裂，当前信息不足以定论",
    "BLOCK": "存在被强事实直接否定的主张",
}


def decide(
    claims: list,
    gaps: list,
    page: dict,
    hard_redline: bool = False,
) -> dict:
    """Compute claim-level states and the derived page-level state.

    Args:
        claims: Claims with alignment results attached.
        gaps: Gap candidates from ``align.detect_gaps``.
        page: Normalized page dict (supplies ``category``).
        hard_redline: Absolute violation short-circuit, e.g. prohibited content.

    Returns:
        Decision object, also writes ``state`` onto each claim in place.
    """
    gaps_by_claim = {}
    for gap in gaps:
        gaps_by_claim.setdefault(gap["claim_id"], []).append(gap)

    claim_states = {}
    for claim in claims:
        states = [
            GAP_STATE.get(gap["gap_type"], "HUMAN_REVIEW")
            for gap in gaps_by_claim.get(claim["claim_id"], [])
        ]
        state = max(states, key=lambda s: SEVERITY[s]) if states else "PASS"
        if hard_redline:
            state = "BLOCK"
        claim["state"] = state
        claim_states[claim["claim_id"]] = state

    page_state = (
        max(claim_states.values(), key=lambda s: SEVERITY[s])
        if claim_states
        else "PASS"
    )
    blocking = [cid for cid, state in claim_states.items() if state == "BLOCK"]

    return {
        "state": page_state,
        "claim_states": claim_states,
        "rule_first": True,
        "confidence": CONFIDENCE[page_state],
        "reason": (
            f"硬红线短路：{', '.join(sorted(claim_states))}"
            if hard_redline
            else f"{STATE_REASON[page_state]}"
            + (f"；触发主张 {', '.join(blocking)}" if blocking else "")
        ),
        "category": page.get("category", ""),
        "hard_redline": hard_redline,
    }
