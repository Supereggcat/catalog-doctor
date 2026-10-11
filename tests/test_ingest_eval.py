from __future__ import annotations

from catalog_doctor.eval import evaluate
from catalog_doctor.ingest import generate_demo_dataset, parse_csv, to_csv
from catalog_doctor.models import ScanResult
from catalog_doctor.rules import RuleContext, build_duplicate_clusters, evaluate_products
from catalog_doctor.scoring import score_products


def build_result(seed: int = 20261011) -> ScanResult:
    products, labels, duplicate_labels, distractors = generate_demo_dataset(seed=seed)
    duplicates = build_duplicate_clusters(products)
    ctx = RuleContext(products, "demo", duplicates)
    issues = evaluate_products(ctx)
    return ScanResult(
        products=products,
        issues=issues,
        duplicates=duplicates,
        scores=score_products(products, issues),
        categories=[],
        generated_at="2026-10-11T00:00:00+08:00",
        dataset_name="demo",
        labels=labels,
        duplicate_labels=duplicate_labels,
        distractors=distractors,
    )


def test_csv_round_trip(make_product):
    products = [make_product("audio", sku="SKU-A"), make_product("kitchen", sku="SKU-B")]
    text = to_csv(products)
    parsed = parse_csv(text)
    assert [item.sku for item in parsed] == ["SKU-A", "SKU-B"]
    assert parsed[0].attributes["color"] == products[0].attributes["color"]
    assert parsed[0].variants[0].variant_id == products[0].variants[0].variant_id


def test_parse_csv_skips_rows_without_sku():
    text = "sku,title\n,空标题\nSKU-1,正常标题\n"
    assert [item.sku for item in parse_csv(text)] == ["SKU-1"]


def test_demo_dataset_shape():
    products, labels, duplicate_labels, distractors = generate_demo_dataset()
    assert len(products) == 532
    assert len(duplicate_labels) == 40
    assert len(distractors) == 40
    assert sum(1 for codes in labels.values() if codes) >= 260


def test_demo_dataset_is_deterministic():
    left = [product.sku for product in generate_demo_dataset(seed=7)[0]]
    right = [product.sku for product in generate_demo_dataset(seed=7)[0]]
    assert left == right


def test_evaluation_metrics_are_high_but_scoped():
    report = evaluate(build_result())
    assert report["overall"]["precision"] >= 0.98
    assert report["overall"]["recall"] >= 0.98
    assert report["duplicates"]["f1"] >= 0.95
    assert report["stress"]["falsePositiveSkus"] == 0
    assert report["capability"]["uncoveredDefects"] == 12
    assert report["baseline"]["recall"] < 0.1


def test_evaluation_is_stable_across_seeds():
    for seed in (1, 2, 3):
        report = evaluate(build_result(seed))
        assert report["overall"]["f1"] >= 0.98, seed
        assert report["duplicates"]["f1"] >= 0.95, seed

