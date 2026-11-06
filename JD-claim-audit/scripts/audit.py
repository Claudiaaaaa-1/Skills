#!/usr/bin/env python3
"""End-to-end CLI for sku-claim-audit.

Runs parse -> align -> gap detection -> four-state routing and validates the
resulting ledger. No API key or network access is required.

Usage:
    python3 scripts/audit.py evals/files/case-01-silk.json --out out.json
    python3 scripts/audit.py evals/files/case-01-silk.json --quiet
"""

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from align import align, detect_gaps  # noqa: E402
from parse_page import parse_page, public_page  # noqa: E402
from route import decide  # noqa: E402
from validate_output import validate  # noqa: E402

BOUNDARY = (
    "未核验检测报告在官方库中的真伪；未覆盖主图与 SKU 的图文关系；"
    "未核验实物；单模态文本输入。"
)


def audit(raw: dict) -> dict:
    """Build a complete ledger from one input case."""
    page = parse_page(raw)
    claims = copy.deepcopy(raw.get("claims", []))
    evidence = copy.deepcopy(raw.get("evidence", []))

    align(claims, evidence, page)
    gaps = detect_gaps(claims, evidence)
    decision = decide(
        claims,
        gaps,
        page,
        hard_redline=bool(raw.get("hard_redline", False)),
    )

    return {
        "page": public_page(page),
        "claims": claims,
        "evidence": evidence,
        "gaps": gaps,
        "decision": decision,
        "boundary": raw.get("boundary", BOUNDARY),
    }


def summary(ledger: dict) -> str:
    """Human-readable one-screen summary, useful for screenshots and review."""
    decision = ledger["decision"]
    lines = [
        "=== 主张—证据一致性核验台账 ===",
        f"类目        : {decision['category']}",
        f"页面级状态  : {decision['state']}  (confidence {decision['confidence']})",
        f"理由        : {decision['reason']}",
        "",
        "主张级结果:",
    ]
    gaps_by_claim = {}
    for gap in ledger["gaps"]:
        gaps_by_claim.setdefault(gap["claim_id"], []).append(gap["gap_type"])
    for claim in ledger["claims"]:
        types = ", ".join(gaps_by_claim.get(claim["claim_id"], [])) or "无"
        lines.append(
            f"  [{claim['state']:<17}] {claim['claim_id']} "
            f"{claim['text']}  断裂: {types}"
        )
    lines += [
        "",
        f"主张 {len(ledger['claims'])} 条 / 证据 {len(ledger['evidence'])} 条 / "
        f"断裂记录 {len(ledger['gaps'])} 条",
        f"能力边界    : {ledger['boundary']}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run one sku-claim-audit case")
    parser.add_argument("input", help="Path to input case JSON")
    parser.add_argument("--out", help="Write the ledger JSON to this path")
    parser.add_argument("--quiet", action="store_true", help="Only print the JSON")
    args = parser.parse_args()

    path = Path(args.input)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read input case: {exc}", file=sys.stderr)
        return 2

    ledger = audit(raw)
    valid, errors = validate(ledger)
    payload = json.dumps(ledger, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.quiet:
        print(payload if not args.out else "")
    else:
        print(summary(ledger))
        print(f"\n契约校验    : {'PASS' if valid else 'FAIL'}")
        for error in errors:
            print(f"  - {error}")
        if args.out:
            print(f"完整台账    : {args.out}")

    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
