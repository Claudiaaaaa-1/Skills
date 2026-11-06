#!/usr/bin/env python3
"""Deterministic page parsing for sku-claim-audit.

Splits a raw page snapshot into the six canonical information blocks and
records which blocks are actually present. No judgement is made here: the
source of a block determines the trust level of any evidence derived from it,
so lossy merging at this stage would destroy information needed later.
"""

BLOCK_KEYS = (
    "title",
    "main_image_ocr",
    "attributes",
    "detail_text",
    "rules",
    "certificates",
)


def parse_page(raw: dict) -> dict:
    """Normalize the page section of an input case.

    Args:
        raw: Full input case dictionary containing a ``page`` key.

    Returns:
        A normalized page dict with ``blocks`` and ``blocks_present``.
    """
    page = raw.get("page", {}) or {}
    blocks = page.get("blocks", {}) or {}
    normalized = {key: blocks.get(key) for key in BLOCK_KEYS}
    present = [
        key
        for key, value in normalized.items()
        if value not in (None, "", [], {})
    ]
    return {
        "spu_id": page.get("spu_id", ""),
        "sku_id": page.get("sku_id", ""),
        "category": page.get("category", ""),
        "blocks": normalized,
        "blocks_present": present,
    }


def public_page(page: dict) -> dict:
    """Return the page fields that belong in the output ledger.

    Raw block contents stay in the input side of the pipeline; the ledger only
    records which blocks were available, keeping the artifact small and stable.
    """
    return {
        "spu_id": page.get("spu_id", ""),
        "sku_id": page.get("sku_id", ""),
        "category": page.get("category", ""),
        "blocks_present": page.get("blocks_present", []),
    }
