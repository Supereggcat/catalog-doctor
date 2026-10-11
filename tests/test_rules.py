from __future__ import annotations

import pytest

from catalog_doctor.ingest import ean13
from catalog_doctor.models import Variant
from catalog_doctor.rules import RuleContext, evaluate_products
from catalog_doctor.rules.core import gtin_checksum_ok
from catalog_doctor.rules.duplicates import build_duplicate_clusters


def run(product, products=None):
    items = products or [product]
    ctx = RuleContext(items, "unit-test", build_duplicate_clusters(items))
    return [issue for issue in evaluate_products(ctx) if issue.sku == product.sku]


def codes(issues):
    return {issue.code for issue in issues}


def test_clean_product_produces_no_issues(make_product):
    for category_id in ["audio", "kitchen", "sportswear", "skincare", "mobile", "outdoor"]:
        product = make_product(category_id, sku=f"SKU-{category_id}")
        assert run(product) == [], f"{category_id} 干净样本不应产生问题"


def test_missing_required_attribute_is_reported(make_product):
    product = make_product("audio")
    product.attributes.pop("impedance")
    issues = run(product)
    assert "completeness.required_attribute" in codes(issues)
    assert any(issue.field == "impedance" for issue in issues)


def test_enum_alias_is_auto_fixable(make_product):
    product = make_product("audio")
    product.attributes["color"] = "黑色"
    issues = [issue for issue in run(product) if issue.code == "conformance.enum_value_invalid"]
    assert len(issues) == 1
    assert issues[0].auto_fixable is True
    assert issues[0].repair["after"] == "黑"


def test_unknown_enum_value_is_not_auto_fixable(make_product):
    product = make_product("audio")
    product.attributes["connectivity"] = "神秘协议"
    issues = [issue for issue in run(product) if issue.code == "conformance.enum_value_invalid"]
    assert len(issues) == 1
    assert issues[0].auto_fixable is False
    assert "词表" in issues[0].message


def test_unit_mismatch_is_converted(make_product):
    product = make_product("audio")
    product.attributes["weight"] = "0.35kg"
    issues = [issue for issue in run(product) if issue.code == "conformance.unit_mismatch"]
    assert len(issues) == 1
    assert issues[0].repair["after"] == "350g"


def test_numeric_out_of_range(make_product):
    product = make_product("audio")
    product.attributes["battery_hours"] = "9000h"
    assert "conformance.numeric_out_of_range" in codes(run(product))


def test_unparseable_numeric_value(make_product):
    product = make_product("audio")
    product.attributes["impedance"] = "三十二"
    assert "conformance.numeric_not_parseable" in codes(run(product))


@pytest.mark.parametrize("code", ["6901234567892", "6901234567893"])
def test_gtin_checksum(code):
    assert gtin_checksum_ok(code) is (code == ean13("690123456789"))


def test_bad_barcode_is_reported(make_product):
    product = make_product("audio")
    digits = list(product.barcode)
    digits[2] = str((int(digits[2]) + 1) % 10)
    product.barcode = "".join(digits)
    assert "conformance.barcode_checksum" in codes(run(product))


def test_missing_barcode_is_reported(make_product):
    product = make_product("audio")
    product.barcode = ""
    assert "completeness.missing_barcode" in codes(run(product))


def test_invalid_price_is_critical(make_product):
    product = make_product("audio")
    product.price = 0
    issues = [issue for issue in run(product) if issue.code == "accuracy.price_invalid"]
    assert issues and issues[0].severity == "critical"


def test_price_out_of_band(make_product):
    product = make_product("audio")
    product.price = 999999
    assert "accuracy.price_out_of_band" in codes(run(product))


def test_banned_word_is_auto_fixable(make_product):
    product = make_product("audio")
    product.title = f"{product.title} 全网最低"
    issues = [issue for issue in run(product) if issue.code == "text.banned_word"]
    assert issues and issues[0].auto_fixable
    assert "全网最低" not in issues[0].repair["after"]
    assert "全网最低" == issues[0].evidence


def test_promo_noise_is_stripped(make_product):
    product = make_product("audio")
    product.title = f"{product.title} 🔥限时"
    issues = [issue for issue in run(product) if issue.code == "text.promo_noise"]
    assert issues and "🔥" not in issues[0].repair["after"]


def test_short_title(make_product):
    product = make_product("audio")
    product.title = "韶音"
    assert "text.title_length" in codes(run(product))


def test_placeholder_description(make_product):
    product = make_product("audio")
    product.description = "待补充"
    assert {"text.placeholder_text", "text.description_too_short"} <= codes(run(product))


def test_raw_html_is_cleaned(make_product):
    product = make_product("audio")
    product.description = f"{product.description}<div>规格</div>"
    issues = [issue for issue in run(product) if issue.code == "text.raw_html"]
    assert issues and "<div>" not in issues[0].repair["after"]


def test_brand_conflict_is_critical(make_product):
    product = make_product("audio")
    product.brand = "漫步者"
    product.title = f"小米 {product.title}"
    issues = [issue for issue in run(product) if issue.code == "consistency.brand_conflict"]
    assert issues and issues[0].severity == "critical"


def test_variant_axis_missing(make_product):
    product = make_product("audio")
    product.variants = [Variant(variant_id="SKU-01", axes={}, price=product.price, stock=1)]
    assert "consistency.variant_axis_missing" in codes(run(product))


def test_variant_price_inconsistency_ignored_when_main_price_invalid(make_product):
    product = make_product("audio")
    product.price = -1
    assert "consistency.variant_price_inconsistent" not in codes(run(product))


def test_duplicate_variant_signature(make_product):
    product = make_product("audio")
    product.variants = [
        Variant(variant_id="A", axes={"color": "黑"}, price=product.price, stock=1),
        Variant(variant_id="B", axes={"color": "黑"}, price=product.price, stock=1),
    ]
    assert "consistency.variant_axis_missing" in codes(run(product))


def test_missing_image_is_critical(make_product):
    product = make_product("audio")
    product.images = []
    issues = [issue for issue in run(product) if issue.code == "completeness.missing_image"]
    assert issues and issues[0].severity == "critical"


def test_low_image_count(make_product):
    product = make_product("audio")
    product.images = product.images[:1]
    assert "media.image_count_low" in codes(run(product))


def test_invalid_image_url(make_product):
    product = make_product("audio")
    product.images[1] = "/local/only.jpg"
    assert "media.image_url_invalid" in codes(run(product))


def test_shared_cover_image_detected(make_product):
    left = make_product("audio", sku="SKU-A")
    right = make_product("audio", sku="SKU-B")
    right.images = list(left.images)
    right.title = "声阔 AUD200 头戴式耳机 12小时续航 白色 官方正品"
    issues = run(right, [left, right])
    assert "media.image_shared_asset" in codes(issues)


def test_unknown_attribute_flagged(make_product):
    product = make_product("audio")
    product.attributes["weird_field"] = "1"
    assert "conformance.unknown_attribute" in codes(run(product))


def test_image_alt_is_reserved_attribute(make_product):
    product = make_product("audio")
    assert "conformance.unknown_attribute" not in codes(run(product))


def test_missing_seo_keywords(make_product):
    product = make_product("audio")
    product.seo_keywords = ""
    issues = [issue for issue in run(product) if issue.code == "seo.keywords_missing"]
    assert issues and issues[0].auto_fixable


def test_brand_missing_in_title_is_suggested(make_product):
    product = make_product("audio")
    product.title = "AUD100 蓝牙耳机 24小时续航"
    issues = [issue for issue in run(product) if issue.code == "seo.brand_missing_in_title"]
    assert issues and issues[0].repair["after"].startswith("韶音")

