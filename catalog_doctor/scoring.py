"""Quality scoring.

A SKU starts at 100 points. Each issue removes points according to its severity,
scaled by the importance of the dimension it belongs to, and capped per dimension
so that a single noisy field group cannot drive a SKU to zero on its own.
"""

from __future__ import annotations

from collections import defaultdict

from .models import (
    DIMENSION_PENALTY_CAP,
    DIMENSION_WEIGHTS,
    MAX_DUPLICATE_PENALTY,
    SEVERITY_PENALTY,
    Issue,
    Product,
    ProductScore,
    grade_for,
)
from .taxonomy import CATEGORY_MAP

# A single severe defect must visibly move the grade, otherwise a SKU that is
# literally unsellable (no images, negative price) would still report as "A".
SEVERITY_GRADE_CEILING = {"critical": 60.0, "major": 82.0, "minor": 92.0}


def _grade_from(score: float) -> str:
    return grade_for(score)


def score_product(product: Product, issues: list[Issue]) -> ProductScore:
    raw_penalty: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        raw_penalty[issue.dimension] += SEVERITY_PENALTY.get(issue.severity, 0.0)
        counts[issue.severity] += 1

    dimension_scores: dict[str, float] = {}
    total_deduction = 0.0
    for dimension, penalty in raw_penalty.items():
        weight = DIMENSION_WEIGHTS.get(dimension, 0.5)
        cap = MAX_DUPLICATE_PENALTY if dimension == "duplication" else DIMENSION_PENALTY_CAP
        scaled = min(penalty, cap) * weight
        dimension_scores[dimension] = max(0.0, 100.0 - scaled)
        total_deduction += scaled

    spec = CATEGORY_MAP.get(product.category_id)
    completeness = 1.0
    if spec is not None and spec.required_keys:
        present = sum(1 for key in spec.required_keys if product.attr(key))
        completeness = present / len(spec.required_keys)

    score = max(0.0, min(100.0, 100.0 - total_deduction))
    for severity in ("critical", "major", "minor"):
        if counts.get(severity):
            score = min(score, SEVERITY_GRADE_CEILING[severity])
            break
    return ProductScore(
        sku=product.sku,
        score=score,
        grade=_grade_from(score),
        dimension_scores=dimension_scores,
        issue_counts=dict(counts),
        completeness=completeness,
    )


def score_products(products: list[Product], issues: list[Issue]) -> dict[str, ProductScore]:
    grouped: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        grouped[issue.sku].append(issue)
    return {
        product.sku: score_product(product, grouped.get(product.sku, [])) for product in products
    }


def projected_score(product: Product, issues: list[Issue], applied_ids: set[str]) -> float:
    """Score the SKU as if the given issues were repaired."""

    remaining = [issue for issue in issues if issue.issue_id not in applied_ids]
    return score_product(product, remaining).score

