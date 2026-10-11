"""Domain model for catalog diagnostics.

The model is deliberately transport-agnostic: the HTTP layer in ``api.py`` maps
these dataclasses to plain dictionaries. Nothing in this module imports FastAPI
or any persistence library, which keeps the rule engine unit-testable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "major": 1, "minor": 2, "info": 3}
SEVERITY_LABELS: dict[str, str] = {
    "critical": "致命",
    "major": "严重",
    "minor": "轻微",
    "info": "提示",
}

# Points removed from a 100-point score for a single issue of each severity.
SEVERITY_PENALTY: dict[str, float] = {
    "critical": 18.0,
    "major": 9.0,
    "minor": 4.0,
    "info": 1.5,
}

# Relative importance of each quality dimension when rolling up a score.
DIMENSION_WEIGHTS: dict[str, float] = {
    "completeness": 1.00,
    "conformance": 0.95,
    "accuracy": 0.90,
    "consistency": 0.75,
    "text": 0.70,
    "media": 0.55,
    "pricing": 0.70,
    "seo": 0.40,
    "duplication": 0.85,
}

DIMENSION_LABELS: dict[str, str] = {
    "completeness": "完整性",
    "conformance": "规范性",
    "accuracy": "准确性",
    "consistency": "一致性",
    "text": "文案质量",
    "media": "媒体素材",
    "pricing": "价格库存",
    "seo": "搜索健壮性",
    "duplication": "重复商品",
}

# A single dimension may not cost more than this many points, so one badly
# maintained field group cannot pin a SKU at zero on its own.
DIMENSION_PENALTY_CAP = 42.0
MAX_DUPLICATE_PENALTY = 24.0

GRADE_BANDS: list[tuple[str, float]] = [
    ("A", 90.0),
    ("B", 78.0),
    ("C", 64.0),
    ("D", 48.0),
    ("E", 0.0),
]


def grade_for(score: float) -> str:
    for grade, floor in GRADE_BANDS:
        if score >= floor:
            return grade
    return "E"


@dataclass(slots=True)
class AttributeSpec:
    """Declared expectation for one product attribute inside a category."""

    key: str
    label: str
    dtype: str = "text"  # text | number | enum | bool | dimension
    required: bool = True
    unit: str | None = None
    enum_values: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    aliases: dict[str, str] = field(default_factory=dict)
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "dtype": self.dtype,
            "required": self.required,
            "unit": self.unit,
            "enumValues": self.enum_values,
            "minValue": self.min_value,
            "maxValue": self.max_value,
            "hint": self.hint,
        }


@dataclass(slots=True)
class CategorySpec:
    category_id: str
    name: str
    path: str
    attributes: list[AttributeSpec]
    price_floor: float
    price_ceiling: float
    keywords: list[str] = field(default_factory=list)

    @property
    def required_keys(self) -> list[str]:
        return [spec.key for spec in self.attributes if spec.required]

    def attribute(self, key: str) -> AttributeSpec | None:
        for spec in self.attributes:
            if spec.key == key:
                return spec
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "categoryId": self.category_id,
            "name": self.name,
            "path": self.path,
            "priceFloor": self.price_floor,
            "priceCeiling": self.price_ceiling,
            "keywords": self.keywords,
            "attributes": [spec.to_dict() for spec in self.attributes],
        }


@dataclass(slots=True)
class Variant:
    variant_id: str
    axes: dict[str, str] = field(default_factory=dict)
    price: float | None = None
    stock: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "variantId": self.variant_id,
            "axes": dict(self.axes),
            "price": self.price,
            "stock": self.stock,
        }


@dataclass(slots=True)
class Product:
    product_id: str
    sku: str
    title: str
    brand: str
    category_id: str
    price: float | None = None
    currency: str = "CNY"
    stock: int | None = None
    barcode: str = ""
    images: list[str] = field(default_factory=list)
    description: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    variants: list[Variant] = field(default_factory=list)
    supplier: str = ""
    seo_keywords: str = ""

    def attr(self, key: str) -> str:
        value = self.attributes.get(key, "")
        return "" if value is None else str(value).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "productId": self.product_id,
            "sku": self.sku,
            "title": self.title,
            "brand": self.brand,
            "categoryId": self.category_id,
            "price": self.price,
            "currency": self.currency,
            "stock": self.stock,
            "barcode": self.barcode,
            "images": list(self.images),
            "description": self.description,
            "attributes": dict(self.attributes),
            "variants": [variant.to_dict() for variant in self.variants],
            "supplier": self.supplier,
            "seoKeywords": self.seo_keywords,
        }


@dataclass(slots=True)
class Issue:
    code: str
    sku: str
    product_id: str
    category_id: str
    dimension: str
    severity: str
    field: str
    message: str
    evidence: str = ""
    suggestion: str = ""
    auto_fixable: bool = False
    confidence: float = 1.0
    repair: dict[str, Any] | None = None

    @property
    def issue_id(self) -> str:
        repair_key = ""
        if self.repair:
            repair_key = str(self.repair.get("after", ""))[:24]
        return f"{self.sku}:{self.code}:{self.field}:{repair_key}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.issue_id,
            "code": self.code,
            "sku": self.sku,
            "productId": self.product_id,
            "categoryId": self.category_id,
            "dimension": self.dimension,
            "dimensionLabel": DIMENSION_LABELS.get(self.dimension, self.dimension),
            "severity": self.severity,
            "severityLabel": SEVERITY_LABELS.get(self.severity, self.severity),
            "field": self.field,
            "message": self.message,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "autoFixable": self.auto_fixable,
            "confidence": round(self.confidence, 3),
            "repair": self.repair,
        }


@dataclass(slots=True)
class DuplicateCluster:
    cluster_id: str
    skus: list[str]
    similarity: float
    reason: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clusterId": self.cluster_id,
            "skus": list(self.skus),
            "similarity": round(self.similarity, 4),
            "reason": self.reason,
            "evidence": list(self.evidence),
        }


@dataclass(slots=True)
class ProductScore:
    sku: str
    score: float
    grade: str
    dimension_scores: dict[str, float]
    issue_counts: dict[str, int]
    completeness: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "score": round(self.score, 1),
            "grade": self.grade,
            "dimensionScores": {k: round(v, 1) for k, v in self.dimension_scores.items()},
            "issueCounts": dict(self.issue_counts),
            "completeness": round(self.completeness, 3),
        }


@dataclass(slots=True)
class ScanResult:
    products: list[Product]
    issues: list[Issue]
    duplicates: list[DuplicateCluster]
    scores: dict[str, ProductScore]
    categories: list[CategorySpec]
    generated_at: str
    dataset_name: str = "unknown"
    labels: dict[str, list[str]] = field(default_factory=dict)
    duplicate_labels: list[list[str]] = field(default_factory=list)
    distractors: list[str] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "datasetName": self.dataset_name,
            "generatedAt": self.generated_at,
            "productCount": len(self.products),
            "issueCount": len(self.issues),
            "duplicateClusterCount": len(self.duplicates),
            "averageScore": round(
                sum(score.score for score in self.scores.values()) / max(len(self.scores), 1), 1
            ),
            "gradeDistribution": self.grade_distribution(),
        }

    def grade_distribution(self) -> dict[str, int]:
        buckets = {grade: 0 for grade, _ in GRADE_BANDS}
        for score in self.scores.values():
            buckets[score.grade] = buckets.get(score.grade, 0) + 1
        return buckets

    def severity_counts(self) -> dict[str, int]:
        counts = {key: 0 for key in SEVERITY_ORDER}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts

    def dimension_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.dimension] = counts.get(issue.dimension, 0) + 1
        return counts

    def issues_for(self, sku: str) -> list[Issue]:
        return [issue for issue in self.issues if issue.sku == sku]

    def product_map(self) -> dict[str, Product]:
        return {product.sku: product for product in self.products}

    def products_in_category(self, category_id: str) -> Iterable[Product]:
        return [product for product in self.products if product.category_id == category_id]

