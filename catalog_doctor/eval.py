"""Evaluation harness.

The synthetic dataset ships with ground-truth labels for every injected defect,
so precision and recall are measured rather than asserted. The harness also
compares against a naive "required fields only" baseline, which is what most
spreadsheet-based catalog audits actually do.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Any

from .models import ScanResult
from .rules import RULE_BY_CODE, RULES

NAIVE_BASELINE_CODES = {"completeness.required_attribute"}


def _prf(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float]:
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _pair_set(clusters: list[list[str]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for cluster in clusters:
        for left, right in itertools.combinations(sorted(set(cluster)), 2):
            pairs.add((left, right))
    return pairs


def evaluate(result: ScanResult) -> dict[str, Any]:
    gold: set[tuple[str, str]] = set()
    for sku, codes in result.labels.items():
        for code in codes:
            gold.add((sku, code))
    predicted: set[tuple[str, str]] = {(issue.sku, issue.code) for issue in result.issues}
    implemented_codes = {rule.code for rule in RULES}
    gold_implemented = {pair for pair in gold if pair[1] in implemented_codes}
    uncovered_gold = gold - gold_implemented

    per_code: list[dict[str, Any]] = []
    for rule in RULES:
        gold_for_code = {sku for sku, code in gold if code == rule.code}
        predicted_for_code = {sku for sku, code in predicted if code == rule.code}
        true_positive = len(gold_for_code & predicted_for_code)
        false_positive = len(predicted_for_code - gold_for_code)
        false_negative = len(gold_for_code - predicted_for_code)
        metrics = _prf(true_positive, false_positive, false_negative)
        per_code.append(
            {
                "code": rule.code,
                "name": rule.name,
                "dimension": rule.dimension,
                "support": len(gold_for_code),
                "predicted": len(predicted_for_code),
                "truePositives": true_positive,
                "falsePositives": false_positive,
                "falseNegatives": false_negative,
                **metrics,
            }
        )

    true_positive = len(gold_implemented & predicted)
    false_positive = len(predicted - gold_implemented)
    false_negative = len(gold_implemented - predicted)
    overall = {
        **_prf(true_positive, false_positive, false_negative),
        "truePositives": true_positive,
        "falsePositives": false_positive,
        "falseNegatives": false_negative,
        "goldCount": len(gold_implemented),
        "predictedCount": len(predicted),
        "scope": "仅统计已实现规则族覆盖的标注缺陷（uncovered.* 单列在 capability 中）",
    }
    scored_codes = [row for row in per_code if row["support"] > 0]
    overall["macroF1"] = round(
        sum(row["f1"] for row in scored_codes) / max(len(scored_codes), 1), 4
    )
    overall["microAccuracy"] = round(
        true_positive / max(true_positive + false_positive + false_negative, 1), 4
    )

    gold_pairs = _pair_set(result.duplicate_labels)
    predicted_pairs = _pair_set([cluster.skus for cluster in result.duplicates])
    duplicate_metrics = {
        **_prf(
            len(gold_pairs & predicted_pairs),
            len(predicted_pairs - gold_pairs),
            len(gold_pairs - predicted_pairs),
        ),
        "truePositives": len(gold_pairs & predicted_pairs),
        "falsePositives": len(predicted_pairs - gold_pairs),
        "falseNegatives": len(gold_pairs - predicted_pairs),
        "goldPairs": len(gold_pairs),
        "predictedPairs": len(predicted_pairs),
        "threshold": 0.72,
    }

    baseline_predicted = {
        (issue.sku, issue.code)
        for issue in result.issues
        if issue.code in NAIVE_BASELINE_CODES
    }
    baseline_hits = sum(1 for pair in baseline_predicted if pair in gold_implemented)
    baseline_false = len(baseline_predicted - gold_implemented)
    baseline_missed = len(gold_implemented - baseline_predicted)
    baseline_recall = baseline_hits / max(baseline_hits + baseline_missed, 1)
    baseline_by_code: dict[str, set[str]] = defaultdict(set)
    for sku, code in gold_implemented:
        baseline_by_code[code].add(sku)
    detectable = sum(len(skus) for code, skus in baseline_by_code.items() if code in NAIVE_BASELINE_CODES)
    baseline = {
        "name": "朴素基线：仅校验必填字段",
        "coveredCodes": sorted(NAIVE_BASELINE_CODES),
        "coveredCodeCount": len(NAIVE_BASELINE_CODES),
        "totalCodeCount": len(RULES),
        "codeCoverage": round(len(NAIVE_BASELINE_CODES) / len(RULES), 4),
        "detected": baseline_hits,
        "falsePositives": baseline_false,
        "recall": round(detectable / max(len(gold_implemented), 1), 4),
        "measuredRecall": round(baseline_recall, 4),
    }

    labeled_families = {code for _, code in gold}
    capability = {
        "labeledFamilies": len(labeled_families),
        "implementedFamilies": len(labeled_families & implemented_codes),
        "ruleFamilies": len(RULES),
        "uncoveredFamilies": sorted(labeled_families - implemented_codes),
        "uncoveredDefects": len(uncovered_gold),
        "uncoveredRecall": 0.0,
        "note": (
            "uncovered.* 是刻意未实现的缺陷族，用于暴露能力边界；"
            "它们不计入上面的 precision/recall，单独在此列出。"
        ),
    }

    auto_fixable = sum(1 for issue in result.issues if issue.auto_fixable)
    auto_fix = {
        "totalIssues": len(result.issues),
        "autoFixableIssues": auto_fixable,
        "coverage": round(auto_fixable / max(len(result.issues), 1), 4),
    }

    # Deliberate false-positive stress test: these SKUs share a brand and a
    # category with a sibling product but differ in model, price and imagery.
    # A human labelled every one of them as defect-free.
    stress_skus = set(result.distractors)
    stress_issues = [issue for issue in result.issues if issue.sku in stress_skus]
    stress_skus_hit = {issue.sku for issue in stress_issues}
    stress = {
        "name": "相似干扰集（同品牌不同型号，人工标注无缺陷）",
        "productCount": len(stress_skus),
        "falsePositiveIssues": len(stress_issues),
        "falsePositiveSkus": len(stress_skus_hit),
        "cleanRate": round(1 - len(stress_skus_hit) / max(len(stress_skus), 1), 4),
    }

    return {
        "dataset": {
            "name": result.dataset_name,
            "generatedAt": result.generated_at,
            "productCount": len(result.products),
            "labeledSkus": len(result.labels),
            "labeledDefects": len(gold),
            "duplicateClusters": len(result.duplicate_labels),
        },
        "overall": overall,
        "perCode": per_code,
        "duplicates": duplicate_metrics,
        "baseline": baseline,
        "autoFix": auto_fix,
        "stress": stress,
        "capability": capability,
        "rules": {
            "total": len(RULES),
            "dimensions": sorted({rule.dimension for rule in RULES}),
            "codes": [RULE_BY_CODE[rule.code].code for rule in RULES],
        },
    }

