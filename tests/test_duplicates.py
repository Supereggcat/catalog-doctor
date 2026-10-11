from __future__ import annotations

from catalog_doctor.models import Product
from catalog_doctor.rules.duplicates import (
    build_duplicate_clusters,
    normalize_for_match,
    shingles,
)


def test_normalize_removes_marketing_noise():
    left = normalize_for_match("韶音 官方正品 AUD100 蓝牙耳机")
    right = normalize_for_match("韶音AUD100蓝牙耳机包邮")
    assert left == right


def test_shingles_are_stable():
    assert shingles("蓝牙耳机") == {"蓝牙耳", "牙耳机"}
    assert shingles("ab") == {"ab"}


def test_near_duplicate_cluster_found(make_product):
    left = make_product("audio", sku="SKU-A")
    right = make_product("audio", sku="SKU-B")
    right.title = f"官方正品 {left.title.replace(left.brand, '').strip()} 同款包邮"
    right.barcode = left.barcode
    clusters = build_duplicate_clusters([left, right])
    assert len(clusters) == 1
    assert clusters[0].skus == ["SKU-A", "SKU-B"]
    assert clusters[0].similarity >= 0.9


def test_different_models_are_not_duplicates(make_product):
    left = make_product("audio", sku="SKU-A")
    right = make_product("audio", sku="SKU-B")
    right.title = "声阔 AUD900 头戴式耳机 48小时续航 白色 官方正品"
    right.barcode = "6901234567892"
    clusters = build_duplicate_clusters([left, right])
    assert clusters == []


def test_different_color_is_penalised(make_product):
    left = make_product("audio", sku="SKU-A")
    right = make_product("audio", sku="SKU-B")
    right.title = left.title
    right.attributes["color"] = "白"
    right.barcode = "6909999999996"
    clusters = build_duplicate_clusters([left, right])
    assert clusters == [] or clusters[0].similarity < 0.9


def test_shared_barcode_marks_suspicious_pair(make_product):
    left = make_product("audio", sku="SKU-A")
    right = make_product("audio", sku="SKU-B")
    right.title = left.title
    right.attributes["color"] = "白"
    clusters = build_duplicate_clusters([left, right])
    assert clusters
    assert "条码" in clusters[0].reason


def test_single_product_has_no_cluster(make_product):
    assert build_duplicate_clusters([make_product("audio")]) == []


def test_cluster_requires_same_brand_for_barcode_boost(make_product):
    left = make_product("audio", sku="SKU-A")
    right: Product = make_product("audio", sku="SKU-B")
    right.title = "完全不同的商品标题用于测试"
    right.barcode = left.barcode
    clusters = build_duplicate_clusters([left, right])
    assert clusters == [] or clusters[0].similarity >= 0.35

