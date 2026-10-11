from __future__ import annotations

from catalog_doctor.models import Issue
from catalog_doctor.repair import apply_repairs, is_applicable, repair_plan
from catalog_doctor.scoring import score_product


def issue(code, dimension, severity, **kwargs):
    payload = {
        "code": code,
        "sku": "SKU-0001",
        "product_id": "P0001",
        "category_id": "audio",
        "dimension": dimension,
        "severity": severity,
        "field": kwargs.pop("field", "title"),
        "message": "测试问题",
    }
    payload.update(kwargs)
    return Issue(**payload)


def test_clean_product_scores_100(make_product):
    score = score_product(make_product("audio"), [])
    assert score.score == 100
    assert score.grade == "A"
    assert score.completeness == 1.0


def test_critical_issue_caps_grade(make_product):
    product = make_product("audio")
    score = score_product(product, [issue("accuracy.price_invalid", "accuracy", "critical", field="price")])
    assert score.score <= 60
    assert score.grade in {"C", "D", "E"}


def test_major_issue_caps_grade_at_b(make_product):
    product = make_product("audio")
    score = score_product(product, [issue("text.title_length", "text", "major")])
    assert score.grade == "B"


def test_dimension_penalty_is_capped(make_product):
    product = make_product("audio")
    issues = [issue(f"text.rule_{index}", "text", "critical") for index in range(10)]
    score = score_product(product, issues)
    assert score.score >= 30


def test_completeness_reflects_missing_required(make_product):
    product = make_product("audio")
    product.attributes.pop("color")
    score = score_product(product, [])
    assert score.completeness < 1.0


def test_repair_plan_only_contains_applicable_items(make_product):
    product = make_product("audio")
    issues = [
        issue("text.banned_word", "text", "major", auto_fixable=True, repair={"kind": "replace_value", "field": "title", "before": "a", "after": "b"}),
        issue("completeness.required_attribute", "completeness", "major", field="color"),
    ]
    plan = repair_plan([product], issues)
    assert len(plan) == 1
    assert plan[0]["code"] == "text.banned_word"
    assert not is_applicable(issues[1])


def test_apply_repair_updates_field_and_logs(make_product):
    product = make_product("audio")
    product.title = f"{product.title} 全网最低"
    target = issue(
        "text.banned_word",
        "text",
        "major",
        auto_fixable=True,
        repair={"kind": "replace_value", "field": "title", "before": product.title, "after": "韶音 AUD100 蓝牙耳机"},
    )
    updated, log = apply_repairs(product, [target], {target.issue_id})
    assert updated.title == "韶音 AUD100 蓝牙耳机"
    assert product.title.endswith("全网最低")
    assert log[0]["field"] == "title"


def test_apply_repair_can_write_attribute(make_product):
    product = make_product("audio")
    target = issue(
        "media.image_alt_missing",
        "media",
        "info",
        auto_fixable=True,
        repair={"kind": "replace_value", "field": "image_alt", "before": "", "after": "主图"},
    )
    updated, _ = apply_repairs(product, [target], {target.issue_id})
    assert updated.attributes["image_alt"] == "主图"


def test_apply_repair_ignores_non_applicable(make_product):
    product = make_product("audio")
    target = issue("completeness.required_attribute", "completeness", "major", field="color")
    updated, log = apply_repairs(product, [target], {target.issue_id})
    assert log == []
    assert updated.attributes == product.attributes

