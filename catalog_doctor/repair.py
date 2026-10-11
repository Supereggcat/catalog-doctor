"""Repair application and clean export."""

from __future__ import annotations

import copy
from typing import Any

from .models import Issue, Product

PRODUCT_FIELDS = {
    "title",
    "description",
    "brand",
    "currency",
    "barcode",
    "price",
    "seo_keywords",
    "images",
}

APPLICABLE_KINDS = {"replace_value", "convert_unit", "strip_html"}


def is_applicable(issue: Issue) -> bool:
    repair = issue.repair or {}
    return bool(
        issue.auto_fixable
        and repair.get("kind") in APPLICABLE_KINDS
        and repair.get("after") is not None
    )


def apply_repairs(
    product: Product, issues: list[Issue], issue_ids: set[str]
) -> tuple[Product, list[dict[str, Any]]]:
    """Return a repaired copy of ``product`` plus an audit log of every change."""

    updated = copy.deepcopy(product)
    applied: list[dict[str, Any]] = []
    for issue in issues:
        if issue.sku != product.sku or issue.issue_id not in issue_ids or not is_applicable(issue):
            continue
        repair = issue.repair or {}
        field = str(repair.get("field") or issue.field)
        after = repair.get("after")
        before = repair.get("before")
        if field in PRODUCT_FIELDS:
            if field == "price":
                try:
                    setattr(updated, field, float(after))
                except (TypeError, ValueError):
                    continue
            else:
                setattr(updated, field, after)
        else:
            updated.attributes[field] = str(after)
        applied.append(
            {
                "issueId": issue.issue_id,
                "code": issue.code,
                "field": field,
                "before": before,
                "after": after,
                "kind": repair.get("kind"),
            }
        )
    return updated, applied


def repair_plan(products: list[Product], issues: list[Issue]) -> list[dict[str, Any]]:
    """Group every auto-fixable issue into a reviewable action list."""

    product_map = {product.sku: product for product in products}
    plan: list[dict[str, Any]] = []
    for issue in issues:
        if not is_applicable(issue):
            continue
        product = product_map.get(issue.sku)
        repair = issue.repair or {}
        plan.append(
            {
                "issueId": issue.issue_id,
                "sku": issue.sku,
                "code": issue.code,
                "dimension": issue.dimension,
                "severity": issue.severity,
                "field": repair.get("field") or issue.field,
                "kind": repair.get("kind"),
                "before": repair.get("before"),
                "after": repair.get("after"),
                "confidence": round(issue.confidence, 3),
                "message": issue.message,
                "productTitle": product.title if product else "",
                "categoryId": product.category_id if product else "",
            }
        )
    plan.sort(key=lambda item: (item["severity"], -item["confidence"], item["sku"]))
    return plan

