"""Rule registry.

Every diagnostic in Catalog Doctor is a named rule with a stable machine code.
The evaluation harness compares fired codes against human labels, so the codes
are part of the public contract and must stay stable across releases.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..models import Issue, Product
from . import core, text
from .context import RuleContext
from .duplicates import build_duplicate_clusters, rule_duplicate


@dataclass(frozen=True)
class RuleSpec:
    code: str
    name: str
    dimension: str
    severity: str
    description: str
    func: Callable[[RuleContext, Product], list[Issue]]


RULES: list[RuleSpec] = [
    RuleSpec(
        code="completeness.required_attribute",
        name="类目必填属性缺失",
        dimension="completeness",
        severity="major",
        description="商品缺少所属类目模板声明的必填属性。",
        func=core.rule_required_attribute,
    ),
    RuleSpec(
        code="completeness.missing_brand",
        name="品牌缺失",
        dimension="completeness",
        severity="major",
        description="品牌字段为空，导致品牌搜索与授权校验失效。",
        func=text.rule_brand_in_title,
    ),
    RuleSpec(
        code="completeness.missing_barcode",
        name="条码缺失",
        dimension="completeness",
        severity="minor",
        description="缺少 GTIN/EAN/UPC 条码。",
        func=core.rule_barcode,
    ),
    RuleSpec(
        code="completeness.missing_image",
        name="图片缺失",
        dimension="media",
        severity="critical",
        description="商品没有任何图片。",
        func=text.rule_image_quality,
    ),
    RuleSpec(
        code="conformance.enum_value_invalid",
        name="枚举值不规范",
        dimension="conformance",
        severity="major",
        description="属性值不在标准词表中，或使用了可归一化的别名写法。",
        func=core.rule_enum_conformance,
    ),
    RuleSpec(
        code="conformance.numeric_not_parseable",
        name="数值不可解析",
        dimension="conformance",
        severity="major",
        description="数值型属性包含无法解析的文本。",
        func=core.rule_numeric_conformance,
    ),
    RuleSpec(
        code="conformance.numeric_out_of_range",
        name="数值超出合理区间",
        dimension="conformance",
        severity="major",
        description="数值型属性超出类目声明的物理合理区间。",
        func=core.rule_numeric_conformance,
    ),
    RuleSpec(
        code="conformance.unit_mismatch",
        name="计量单位不统一",
        dimension="conformance",
        severity="minor",
        description="属性使用了与类目模板不同的计量单位。",
        func=core.rule_numeric_conformance,
    ),
    RuleSpec(
        code="conformance.barcode_checksum",
        name="条码校验位错误",
        dimension="conformance",
        severity="major",
        description="条码不符合 GTIN 校验规则。",
        func=core.rule_barcode,
    ),
    RuleSpec(
        code="conformance.unknown_attribute",
        name="未声明属性",
        dimension="conformance",
        severity="info",
        description="商品携带了类目模板中不存在的属性。",
        func=core.rule_attribute_coverage,
    ),
    RuleSpec(
        code="accuracy.price_invalid",
        name="价格非法",
        dimension="accuracy",
        severity="critical",
        description="售价缺失、为零或为负值，或币种缺失。",
        func=core.rule_price,
    ),
    RuleSpec(
        code="accuracy.price_out_of_band",
        name="价格超出类目区间",
        dimension="accuracy",
        severity="major",
        description="价格超出类目声明的常见价格区间。",
        func=core.rule_price,
    ),
    RuleSpec(
        code="accuracy.price_outlier",
        name="价格离群",
        dimension="accuracy",
        severity="major",
        description="价格在对数空间显著偏离同类目价格分布（稳健 z 检验）。",
        func=core.rule_price,
    ),
    RuleSpec(
        code="consistency.brand_conflict",
        name="品牌与标题冲突",
        dimension="consistency",
        severity="critical",
        description="标题中出现与商品品牌不一致的知名品牌。",
        func=core.rule_brand_conflict,
    ),
    RuleSpec(
        code="consistency.variant_axis_missing",
        name="规格轴缺失或重复",
        dimension="consistency",
        severity="major",
        description="多规格商品的规格轴缺失或取值重复。",
        func=core.rule_variant_consistency,
    ),
    RuleSpec(
        code="consistency.variant_price_inconsistent",
        name="规格价格异常",
        dimension="consistency",
        severity="minor",
        description="规格价与主售价偏差过大。",
        func=core.rule_variant_consistency,
    ),
    RuleSpec(
        code="text.title_length",
        name="标题长度异常",
        dimension="text",
        severity="major",
        description="标题过短或过长，影响搜索与展示。",
        func=text.rule_title_length,
    ),
    RuleSpec(
        code="text.banned_word",
        name="广告法禁用词",
        dimension="text",
        severity="major",
        description="文案包含绝对化用语等高风险词汇。",
        func=text.rule_banned_word,
    ),
    RuleSpec(
        code="text.promo_noise",
        name="促销符号污染",
        dimension="text",
        severity="minor",
        description="标题包含促销符号，干扰分词与专业度。",
        func=text.rule_promo_noise,
    ),
    RuleSpec(
        code="text.keyword_stuffing",
        name="关键词堆砌",
        dimension="text",
        severity="minor",
        description="同一关键词在标题中重复出现。",
        func=text.rule_keyword_stuffing,
    ),
    RuleSpec(
        code="text.all_caps",
        name="全大写标题",
        dimension="text",
        severity="minor",
        description="标题大量使用大写拉丁字母。",
        func=text.rule_all_caps,
    ),
    RuleSpec(
        code="text.description_too_short",
        name="详情过短",
        dimension="text",
        severity="major",
        description="详情描述为空或明显过短。",
        func=text.rule_description_quality,
    ),
    RuleSpec(
        code="text.placeholder_text",
        name="占位文案残留",
        dimension="text",
        severity="major",
        description="标题或详情残留占位/测试文案。",
        func=text.rule_placeholder_text,
    ),
    RuleSpec(
        code="text.raw_html",
        name="未渲染 HTML",
        dimension="text",
        severity="minor",
        description="详情字段包含未渲染的 HTML 标签。",
        func=text.rule_raw_html,
    ),
    RuleSpec(
        code="media.image_count_low",
        name="图片数量不足",
        dimension="media",
        severity="minor",
        description="图片数量少于 3 张。",
        func=text.rule_image_quality,
    ),
    RuleSpec(
        code="media.image_url_invalid",
        name="图片地址非法",
        dimension="media",
        severity="major",
        description="图片地址不是绝对 URL。",
        func=text.rule_image_quality,
    ),
    RuleSpec(
        code="media.image_generic_filename",
        name="图片命名不规范",
        dimension="media",
        severity="info",
        description="图片使用默认或临时文件名。",
        func=text.rule_image_quality,
    ),
    RuleSpec(
        code="media.image_alt_missing",
        name="图片缺少 alt",
        dimension="media",
        severity="info",
        description="主图缺少替代文本。",
        func=text.rule_image_quality,
    ),
    RuleSpec(
        code="media.image_shared_asset",
        name="主图复用",
        dimension="media",
        severity="major",
        description="多个 SKU 使用完全相同的图片地址。",
        func=text.rule_shared_asset,
    ),
    RuleSpec(
        code="seo.keywords_missing",
        name="搜索关键词缺失",
        dimension="seo",
        severity="minor",
        description="缺少站内搜索关键词。",
        func=text.rule_seo_keywords,
    ),
    RuleSpec(
        code="seo.brand_missing_in_title",
        name="标题缺少品牌",
        dimension="seo",
        severity="info",
        description="标题未包含商品品牌。",
        func=text.rule_brand_in_title,
    ),
    RuleSpec(
        code="duplication.exact_title",
        name="标题完全重复",
        dimension="duplication",
        severity="major",
        description="存在标题完全一致的其他 SKU。",
        func=text.rule_title_duplicate_within_catalog,
    ),
    RuleSpec(
        code="duplication.near_duplicate",
        name="近似重复商品",
        dimension="duplication",
        severity="major",
        description="标题与规格高度相似，疑似重复铺货。",
        func=rule_duplicate,
    ),
]

RULE_BY_CODE: dict[str, RuleSpec] = {rule.code: rule for rule in RULES}


def rule_catalog() -> list[dict]:
    return [
        {
            "code": rule.code,
            "name": rule.name,
            "dimension": rule.dimension,
            "severity": rule.severity,
            "description": rule.description,
        }
        for rule in RULES
    ]


def evaluate_products(ctx: RuleContext) -> list[Issue]:
    """Run every product-scoped rule, de-duplicating on (sku, code, field)."""

    issues: list[Issue] = []
    seen: set[tuple[str, str, str]] = set()
    for product in ctx.products:
        for func in _unique_rule_functions():
            for issue in func(ctx, product):
                key = (issue.sku, issue.code, issue.field)
                if key in seen:
                    continue
                seen.add(key)
                issues.append(issue)
    return issues


def _unique_rule_functions() -> list[Callable[[RuleContext, Product], list[Issue]]]:
    """Several codes share one implementation; call each implementation once."""

    seen: set[str] = set()
    functions: list[Callable[[RuleContext, Product], list[Issue]]] = []
    for rule in RULES:
        key = f"{rule.func.__module__}.{rule.func.__qualname__}"
        if key in seen:
            continue
        seen.add(key)
        functions.append(rule.func)
    return functions


__all__ = [
    "RULES",
    "RULE_BY_CODE",
    "RuleContext",
    "RuleSpec",
    "build_duplicate_clusters",
    "evaluate_products",
    "rule_catalog",
]

