"""Application service: owns the in-memory catalog and orchestrates a scan."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .eval import evaluate as evaluate_result
from .ingest import generate_demo_dataset, parse_csv, to_csv
from .models import (
    DIMENSION_LABELS,
    GRADE_BANDS,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    Issue,
    Product,
    ScanResult,
)
from .repair import apply_repairs, repair_plan
from .rules import (
    RULE_BY_CODE,
    RuleContext,
    build_duplicate_clusters,
    evaluate_products,
    rule_catalog,
)
from .scoring import score_products
from .taxonomy import CATEGORIES, CATEGORY_MAP


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class CatalogNotFound(KeyError):
    pass


class CatalogService:
    """Holds one active catalog.

    The engine is deliberately storage-agnostic: a scan is a pure function over a
    list of products, so the same code path serves the demo dataset, an uploaded
    CSV and (in a future deployment) a database-backed repository.
    """

    def __init__(self) -> None:
        self.products: list[Product] = []
        self.labels: dict[str, list[str]] = {}
        self.duplicate_labels: list[list[str]] = []
        self.distractors: list[str] = []
        self.resolved_clusters: list[dict[str, Any]] = []
        self.dataset_name: str = "demo-catalog"
        self.result: ScanResult | None = None
        self.history: list[dict[str, Any]] = []
        self.applied_repairs: list[dict[str, Any]] = []

    # -- loading ----------------------------------------------------------- #
    def load_demo(self, **kwargs: Any) -> ScanResult:
        products, labels, duplicate_labels, distractors = generate_demo_dataset(**kwargs)
        self.products = products
        self.labels = labels
        self.duplicate_labels = duplicate_labels
        self.distractors = distractors
        self.resolved_clusters = []
        self.dataset_name = f"示例数据集 demo-catalog（{len(products)} SKU，含人工标注缺陷）"
        self.history = []
        self.applied_repairs = []
        return self.scan()

    def load_csv(self, text: str, name: str = "uploaded-catalog") -> ScanResult:
        products = parse_csv(text)
        if not products:
            raise ValueError("CSV 中没有解析到任何商品，请检查是否包含 sku 表头")
        self.products = products
        self.labels = {}
        self.duplicate_labels = []
        self.distractors = []
        self.resolved_clusters = []
        self.dataset_name = f"{name}（{len(products)} SKU）"
        self.history = []
        self.applied_repairs = []
        return self.scan()

    # -- scanning ---------------------------------------------------------- #
    def scan(self) -> ScanResult:
        if not self.products:
            self.load_demo()
        duplicates = [
            cluster
            for cluster in build_duplicate_clusters(self.products)
            if not self._is_resolved(cluster.skus)
        ]
        ctx = RuleContext(self.products, self.dataset_name, duplicates)
        issues = evaluate_products(ctx)
        scores = score_products(self.products, issues)
        result = ScanResult(
            products=self.products,
            issues=issues,
            duplicates=duplicates,
            scores=scores,
            categories=CATEGORIES,
            generated_at=_now(),
            dataset_name=self.dataset_name,
            labels=self.labels,
            duplicate_labels=self.duplicate_labels,
            distractors=self.distractors,
        )
        self.result = result
        self.history.append(
            {
                "at": result.generated_at,
                "averageScore": result.to_summary()["averageScore"],
                "issueCount": len(issues),
                "productCount": len(self.products),
            }
        )
        return result

    def _is_resolved(self, skus: list[str]) -> bool:
        signature = tuple(sorted(skus))
        return any(tuple(sorted(item["skus"])) == signature for item in self.resolved_clusters)

    def _require(self) -> ScanResult:
        if self.result is None:
            return self.scan()
        return self.result

    # -- read models ------------------------------------------------------- #
    def meta(self) -> dict[str, Any]:
        result = self._require()
        return {
            "datasetName": result.dataset_name,
            "generatedAt": result.generated_at,
            "productCount": len(result.products),
            "ruleCount": len(RULE_BY_CODE),
            "categories": [
                {
                    **category.to_dict(),
                    "productCount": len(list(result.products_in_category(category.category_id))),
                }
                for category in CATEGORIES
            ],
            "rules": rule_catalog(),
            "dimensions": [
                {"key": key, "label": label} for key, label in DIMENSION_LABELS.items()
            ],
            "severities": [
                {"key": key, "label": SEVERITY_LABELS[key]} for key in SEVERITY_ORDER
            ],
        }

    def summary(self) -> dict[str, Any]:
        result = self._require()
        base = result.to_summary()
        issues = result.issues
        severity_counts = result.severity_counts()
        dimension_counts = result.dimension_counts()

        category_rows: list[dict[str, Any]] = []
        for category in CATEGORIES:
            products = list(result.products_in_category(category.category_id))
            if not products:
                continue
            skus = {product.sku for product in products}
            category_issues = [issue for issue in issues if issue.sku in skus]
            scores = [result.scores[product.sku].score for product in products if product.sku in result.scores]
            category_rows.append(
                {
                    "categoryId": category.category_id,
                    "name": category.name,
                    "path": category.path,
                    "productCount": len(products),
                    "issueCount": len(category_issues),
                    "criticalCount": sum(1 for i in category_issues if i.severity == "critical"),
                    "majorCount": sum(1 for i in category_issues if i.severity == "major"),
                    "averageScore": round(sum(scores) / max(len(scores), 1), 1),
                    "completeness": round(
                        sum(result.scores[product.sku].completeness for product in products if product.sku in result.scores)
                        / max(len(products), 1),
                        3,
                    ),
                }
            )
        category_rows.sort(key=lambda row: row["averageScore"])

        histogram = {f"{start}-{start + 9}": 0 for start in range(0, 100, 10)}
        for score in result.scores.values():
            bucket = min(int(score.score // 10) * 10, 90)
            histogram[f"{bucket}-{bucket + 9}"] += 1

        plan = repair_plan(result.products, issues)
        auto_fixable = len(plan)
        fixable_skus = {item["sku"] for item in plan}
        gain = 0.0
        for sku in fixable_skus:
            product = result.product_map()[sku]
            sku_issues = result.issues_for(sku)
            ids = {item["issueId"] for item in plan if item["sku"] == sku}
            from .scoring import projected_score

            gain += max(0.0, projected_score(product, sku_issues, ids) - result.scores[sku].score)

        dimension_breakdown = [
            {
                "key": key,
                "label": DIMENSION_LABELS.get(key, key),
                "count": dimension_counts.get(key, 0),
                "critical": sum(1 for i in issues if i.dimension == key and i.severity == "critical"),
                "major": sum(1 for i in issues if i.dimension == key and i.severity == "major"),
                "minor": sum(1 for i in issues if i.dimension == key and i.severity == "minor"),
                "info": sum(1 for i in issues if i.dimension == key and i.severity == "info"),
            }
            for key in DIMENSION_LABELS
            if dimension_counts.get(key, 0) > 0
        ]
        dimension_breakdown.sort(key=lambda row: row["count"], reverse=True)

        top_issues = sorted(
            (issue for issue in issues if issue.severity in {"critical", "major"}),
            key=lambda issue: (SEVERITY_ORDER[issue.severity], -issue.confidence),
        )[:12]

        return {
            **base,
            "severityCounts": severity_counts,
            "dimensionBreakdown": dimension_breakdown,
            "categoryHealth": category_rows,
            "scoreHistogram": histogram,
            "autoFixableCount": auto_fixable,
            "projectedScoreGain": round(gain / max(len(fixable_skus), 1), 1),
            "projectedCatalogGain": round(gain / max(len(result.products), 1), 2),
            "topIssues": [self._issue_payload(issue) for issue in top_issues],
            "history": self.history,
            "appliedRepairCount": len(self.applied_repairs),
        }

    def _issue_payload(self, issue: Issue) -> dict[str, Any]:
        payload = issue.to_dict()
        result = self._require()
        product = result.product_map().get(issue.sku)
        if product is not None:
            payload["productTitle"] = product.title
            payload["brand"] = product.brand
            payload["score"] = result.scores[product.sku].score if product.sku in result.scores else None
        return payload

    def products_page(
        self,
        *,
        query: str = "",
        category_id: str = "",
        grade: str = "",
        severity: str = "",
        sort: str = "score",
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        result = self._require()
        issues_by_sku: dict[str, list[Issue]] = defaultdict(list)
        for issue in result.issues:
            issues_by_sku[issue.sku].append(issue)
        needle = query.strip().lower()
        rows: list[dict[str, Any]] = []
        for product in result.products:
            score = result.scores[product.sku]
            sku_issues = issues_by_sku.get(product.sku, [])
            if category_id and product.category_id != category_id:
                continue
            if grade and score.grade != grade:
                continue
            if severity and not any(issue.severity == severity for issue in sku_issues):
                continue
            if needle and needle not in product.title.lower() and needle not in product.sku.lower() and needle not in (product.brand or "").lower():
                continue
            rows.append(
                {
                    **product.to_dict(),
                    "categoryName": CATEGORY_MAP[product.category_id].name if product.category_id in CATEGORY_MAP else product.category_id,
                    "score": round(score.score, 1),
                    "grade": score.grade,
                    "completeness": round(score.completeness, 3),
                    "issueCount": len(sku_issues),
                    "criticalCount": sum(1 for issue in sku_issues if issue.severity == "critical"),
                    "majorCount": sum(1 for issue in sku_issues if issue.severity == "major"),
                    "autoFixableCount": sum(1 for issue in sku_issues if issue.auto_fixable),
                    "issueCodes": sorted({issue.code for issue in sku_issues}),
                    "duplicateCluster": result.duplicates and next(
                        (cluster.cluster_id for cluster in result.duplicates if product.sku in cluster.skus), None
                    ),
                }
            )
        reverse = sort.startswith("-")
        key = sort.lstrip("-") or "score"
        key_map = {
            "score": lambda row: row["score"],
            "issues": lambda row: row["issueCount"],
            "title": lambda row: row["title"],
            "price": lambda row: row["price"] or 0,
            "completeness": lambda row: row["completeness"],
        }
        rows.sort(key=key_map.get(key, key_map["score"]), reverse=reverse if sort.startswith("-") else False)
        if key == "score" and not sort.startswith("-"):
            rows.reverse()
        total = len(rows)
        page = max(1, page)
        size = max(1, min(size, 200))
        start = (page - 1) * size
        return {"total": total, "page": page, "size": size, "items": rows[start : start + size]}

    def product_detail(self, sku: str) -> dict[str, Any]:
        result = self._require()
        product = result.product_map().get(sku)
        if product is None:
            raise CatalogNotFound(sku)
        issues = result.issues_for(sku)
        score = result.scores.get(sku)
        spec = CATEGORY_MAP.get(product.category_id)
        attribute_rows = []
        for attr in spec.attributes if spec else []:
            value = product.attr(attr.key)
            attribute_rows.append(
                {
                    "key": attr.key,
                    "label": attr.label,
                    "value": value,
                    "required": attr.required,
                    "dtype": attr.dtype,
                    "unit": attr.unit,
                    "enumValues": attr.enum_values,
                    "status": "ok" if value and not any(i.field == attr.key for i in issues) else ("missing" if not value and attr.required else ("issue" if value else "optional")),
                    "issues": [i.to_dict() for i in issues if i.field == attr.key],
                }
            )
        return {
            **product.to_dict(),
            "categoryName": spec.name if spec else product.category_id,
            "score": round(score.score, 1) if score else 0.0,
            "scoreDetail": score.to_dict() if score else None,
            "grade": score.grade if score else "E",
            "completeness": round(score.completeness, 3) if score else 0.0,
            "issueCount": len(issues),
            "criticalCount": sum(1 for issue in issues if issue.severity == "critical"),
            "majorCount": sum(1 for issue in issues if issue.severity == "major"),
            "autoFixableCount": sum(1 for issue in issues if issue.auto_fixable),
            "issueCodes": sorted({issue.code for issue in issues}),
            "issues": [self._issue_payload(issue) for issue in issues],
            "attributes": {"values": product.attributes, "rows": attribute_rows},
            "duplicateCluster": next(
                (cluster.to_dict() for cluster in result.duplicates if sku in cluster.skus), None
            ),
        }

    def issues_page(
        self,
        *,
        query: str = "",
        severity: str = "",
        dimension: str = "",
        category_id: str = "",
        auto_fixable: bool | None = None,
        page: int = 1,
        size: int = 25,
    ) -> dict[str, Any]:
        result = self._require()
        product_map = result.product_map()
        needle = query.strip().lower()
        rows: list[dict[str, Any]] = []
        for issue in result.issues:
            if severity and issue.severity != severity:
                continue
            if dimension and issue.dimension != dimension:
                continue
            if category_id and issue.category_id != category_id:
                continue
            if auto_fixable is not None and issue.auto_fixable != auto_fixable:
                continue
            if needle:
                haystack = f"{issue.sku} {issue.code} {issue.message} {issue.field}".lower()
                product = product_map.get(issue.sku)
                if product is not None:
                    haystack += f" {product.title} {product.brand}".lower()
                if needle not in haystack:
                    continue
            rows.append(self._issue_payload(issue))
        rows.sort(key=lambda row: (SEVERITY_ORDER.get(row["severity"], 9), -row["confidence"], row["sku"]))
        total = len(rows)
        page = max(1, page)
        size = max(1, min(size, 200))
        start = (page - 1) * size
        return {"total": total, "page": page, "size": size, "items": rows[start : start + size]}

    def duplicates_view(self) -> dict[str, Any]:
        result = self._require()
        product_map = result.product_map()
        clusters = []
        for cluster in result.duplicates:
            members = []
            for sku in cluster.skus:
                product = product_map.get(sku)
                if product is None:
                    continue
                members.append(
                    {
                        **product.to_dict(),
                        "score": round(result.scores[sku].score, 1),
                        "grade": result.scores[sku].grade,
                        "issueCount": len(result.issues_for(sku)),
                        "supplier": product.supplier,
                    }
                )
            gold = any(set(cluster.skus) == set(label) for label in result.duplicate_labels)
            clusters.append({**cluster.to_dict(), "members": members, "matchesGroundTruth": gold})
        return {
            "total": len(clusters),
            "threshold": 0.72,
            "clusters": clusters,
            "labelledClusters": len(result.duplicate_labels),
            "resolved": self.resolved_clusters[-20:],
        }

    def resolve_duplicate(
        self, cluster_id: str, action: str, keep_sku: str | None = None
    ) -> dict[str, Any]:
        result = self._require()
        cluster = next((item for item in result.duplicates if item.cluster_id == cluster_id), None)
        if cluster is None:
            raise CatalogNotFound(cluster_id)
        record = {
            "clusterId": cluster_id,
            "skus": list(cluster.skus),
            "action": action,
            "keepSku": keep_sku or cluster.skus[0],
            "similarity": cluster.similarity,
            "resolvedAt": _now(),
        }
        self.resolved_clusters.append(record)
        self.scan()
        return {"clusterId": cluster_id, "action": action, "resolvedCount": 1, "record": record}

    def repairs_view(self) -> dict[str, Any]:
        result = self._require()
        plan = repair_plan(result.products, result.issues)
        grouped: dict[str, int] = defaultdict(int)
        for item in plan:
            grouped[item["code"]] += 1
        return {
            "total": len(plan),
            "applied": self.applied_repairs[-50:],
            "byCode": [
                {
                    "code": code,
                    "name": RULE_BY_CODE[code].name if code in RULE_BY_CODE else code,
                    "count": count,
                }
                for code, count in sorted(grouped.items(), key=lambda item: -item[1])
            ],
            "items": plan[:400],
        }

    def apply_repairs(self, sku: str, issue_ids: list[str]) -> dict[str, Any]:
        result = self._require()
        product = result.product_map().get(sku)
        if product is None:
            raise CatalogNotFound(sku)
        before_score = result.scores[sku].score
        updated, applied = apply_repairs(product, result.issues_for(sku), set(issue_ids))
        if not applied:
            return {"applied": [], "beforeScore": round(before_score, 1), "afterScore": round(before_score, 1)}
        self.products = [updated if item.sku == sku else item for item in self.products]
        self.applied_repairs.extend(applied)
        self.scan()
        after_score = self._require().scores[sku].score
        return {
            "applied": applied,
            "skus": [sku],
            "beforeScore": round(before_score, 1),
            "afterScore": round(after_score, 1),
            "delta": round(after_score - before_score, 1),
            "appliedCount": len(applied),
        }

    def apply_bulk(self, issue_ids: list[str]) -> dict[str, Any]:
        result = self._require()
        by_sku: dict[str, list[str]] = defaultdict(list)
        index = {issue.issue_id: issue for issue in result.issues}
        for issue_id in issue_ids:
            issue = index.get(issue_id)
            if issue is not None:
                by_sku[issue.sku].append(issue_id)
        total_applied: list[dict[str, Any]] = []
        before = sum(result.scores[sku].score for sku in by_sku)
        for sku, ids in by_sku.items():
            outcome = self.apply_repairs(sku, ids)
            total_applied.extend(outcome["applied"])
        after_result = self._require()
        after = sum(after_result.scores[sku].score for sku in by_sku if sku in after_result.scores)
        return {
            "applied": total_applied,
            "skus": sorted(by_sku),
            "appliedCount": len(total_applied),
            "beforeScore": round(before / max(len(by_sku), 1), 1),
            "afterScore": round(after / max(len(by_sku), 1), 1),
            "delta": round((after - before) / max(len(by_sku), 1), 1),
        }

    def evaluation(self) -> dict[str, Any]:
        result = self._require()
        if not result.labels:
            return {
                "available": False,
                "reason": "当前数据集没有人工标注（labels），无法计算 precision / recall。上传自有数据后可运行规则命中统计，但需要标注才能评估准确率。",
                "rules": rule_catalog(),
            }
        return {"available": True, **evaluate_result(result)}

    def export_csv(self) -> str:
        result = self._require()
        return to_csv(result.products)

    def grade_bands(self) -> list[tuple[str, float]]:
        return GRADE_BANDS

