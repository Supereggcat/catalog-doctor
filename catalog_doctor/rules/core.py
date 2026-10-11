"""Structural rules: required attributes, vocabulary, units, barcodes, price."""

from __future__ import annotations

import difflib
import math
import re
import statistics

from ..models import Issue, Product
from ..taxonomy import convert, format_number, parse_measurement
from .context import RuleContext

_PUNCT_RE = re.compile(r"[\s\-_/,，。.、()（）\[\]【】:：;；'\"`]+")

# Attributes the platform manages itself and that are therefore never reported as
# "undeclared" even though they are absent from the category template.
RESERVED_ATTRIBUTE_KEYS = {"image_alt"}

BOOL_TRUE = {"是", "支持", "有", "yes", "y", "true", "1", "√", "available"}
BOOL_FALSE = {"否", "不支持", "无", "no", "n", "false", "0", "×", "x"}


def _canonical_key(raw: str) -> str:
    text = (raw or "").strip().lower()
    text = _PUNCT_RE.sub("", text)
    return text


def canonical_enum_value(spec, raw: str) -> tuple[str | None, bool]:
    """Return ``(canonical_value, was_rewritten)`` for an enum attribute value."""

    key = _canonical_key(raw)
    if not key:
        return None, False
    for value in spec.enum_values:
        if _canonical_key(value) == key:
            return value, False
    for alias_key, canonical in spec.aliases.items():
        if _canonical_key(alias_key) == key:
            return canonical, True
    return None, False


def rule_required_attribute(ctx: RuleContext, product: Product) -> list[Issue]:
    spec = ctx.category(product.category_id)
    if spec is None:
        return []
    issues: list[Issue] = []
    for attr in spec.attributes:
        if not attr.required or product.attr(attr.key):
            continue
        issues.append(
            Issue(
                code="completeness.required_attribute",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="completeness",
                severity="major",
                field=attr.key,
                message=f"{attr.label}（{attr.key}）缺失，但它是{spec.name}类目的必填属性",
                evidence="字段为空",
                suggestion=f"按类目模板补充「{attr.label}」，建议取值参考：{attr.hint or '见类目属性模板'}",
                auto_fixable=False,
                confidence=1.0,
                repair={"kind": "fill_required", "field": attr.key, "before": "", "after": None},
            )
        )
    return issues


def rule_enum_conformance(ctx: RuleContext, product: Product) -> list[Issue]:
    spec = ctx.category(product.category_id)
    if spec is None:
        return []
    issues: list[Issue] = []
    for attr in spec.attributes:
        raw = product.attr(attr.key)
        if not raw:
            continue
        if attr.dtype == "bool":
            token = _canonical_key(raw)
            if token in BOOL_TRUE or token in BOOL_FALSE:
                continue
            issues.append(
                Issue(
                    code="conformance.enum_value_invalid",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="conformance",
                    severity="minor",
                    field=attr.key,
                    message=f"{attr.label} 取值「{raw}」不是布尔值",
                    evidence=raw,
                    suggestion="改为 是 / 否",
                    auto_fixable=False,
                )
            )
            continue
        if attr.dtype != "enum" or not attr.enum_values:
            continue
        canonical, rewritten = canonical_enum_value(attr, raw)
        if canonical is None:
            closest = difflib.get_close_matches(raw, attr.enum_values, n=3, cutoff=0.2)
            issues.append(
                Issue(
                    code="conformance.enum_value_invalid",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="conformance",
                    severity="major",
                    field=attr.key,
                    message=f"{attr.label} 取值「{raw}」不在允许词表中",
                    evidence=raw,
                    suggestion=(
                        f"改用标准词表取值：{ '、'.join(closest) }" if closest
                        else f"可用取值：{ '、'.join(attr.enum_values[:6]) }"
                    ),
                    auto_fixable=False,
                    confidence=0.9,
                )
            )
        elif rewritten:
            issues.append(
                Issue(
                    code="conformance.enum_value_invalid",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="conformance",
                    severity="minor",
                    field=attr.key,
                    message=f"{attr.label} 使用了非标准写法「{raw}」，标准值为「{canonical}」",
                    evidence=f"{raw} -> {canonical}",
                    suggestion=f"归一化为「{canonical}」",
                    auto_fixable=True,
                    confidence=0.97,
                    repair={
                        "kind": "replace_value",
                        "field": attr.key,
                        "before": raw,
                        "after": canonical,
                    },
                )
            )
    return issues


def rule_numeric_conformance(ctx: RuleContext, product: Product) -> list[Issue]:
    spec = ctx.category(product.category_id)
    if spec is None:
        return []
    issues: list[Issue] = []
    for attr in spec.attributes:
        raw = product.attr(attr.key)
        if not raw or attr.dtype not in {"number", "dimension"}:
            continue
        parsed = parse_measurement(raw)
        if parsed is None:
            issues.append(
                Issue(
                    code="conformance.numeric_not_parseable",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="conformance",
                    severity="major",
                    field=attr.key,
                    message=f"{attr.label} 的值「{raw}」无法解析为数值",
                    evidence=raw,
                    suggestion="填写纯数字" + (f"，单位统一为 {attr.unit}" if attr.unit else ""),
                    auto_fixable=False,
                )
            )
            continue
        value, unit = parsed
        if unit and attr.unit:
            converted = convert(value, unit, attr.unit)
            if converted is not None and unit != attr.unit.lower():
                canonical_text = f"{format_number(converted)}{attr.unit}"
                issues.append(
                    Issue(
                        code="conformance.unit_mismatch",
                        sku=product.sku,
                        product_id=product.product_id,
                        category_id=product.category_id,
                        dimension="conformance",
                        severity="minor",
                        field=attr.key,
                        message=f"{attr.label} 使用了 {unit}，类目模板要求 {attr.unit}",
                        evidence=f"{raw} -> {canonical_text}",
                        suggestion=f"统一为 {canonical_text}",
                        auto_fixable=True,
                        confidence=0.98,
                        repair={
                            "kind": "convert_unit",
                            "field": attr.key,
                            "before": raw,
                            "after": canonical_text,
                        },
                    )
                )
                value = converted
            elif converted is None and unit not in {"", attr.unit.lower()}:
                issues.append(
                    Issue(
                        code="conformance.unit_mismatch",
                        sku=product.sku,
                        product_id=product.product_id,
                        category_id=product.category_id,
                        dimension="conformance",
                        severity="major",
                        field=attr.key,
                        message=f"{attr.label} 的单位「{unit}」无法换算为 {attr.unit}",
                        evidence=raw,
                        suggestion=f"改用 {attr.unit} 计量单位重新填写",
                        auto_fixable=False,
                        confidence=0.85,
                    )
                )
                continue
        if attr.min_value is not None and value < attr.min_value:
            issues.append(_range_issue(product, attr, raw, value, "低于", attr.min_value))
        elif attr.max_value is not None and value > attr.max_value:
            issues.append(_range_issue(product, attr, raw, value, "高于", attr.max_value))
    return issues


def _range_issue(product: Product, attr, raw: str, value: float, direction: str, bound: float) -> Issue:
    return Issue(
        code="conformance.numeric_out_of_range",
        sku=product.sku,
        product_id=product.product_id,
        category_id=product.category_id,
        dimension="conformance",
        severity="major",
        field=attr.key,
        message=f"{attr.label} 为 {raw}，{direction}行业合理区间上限/下限 {bound}{attr.unit or ''}",
        evidence=f"{format_number(value)}{attr.unit or ''}",
        suggestion=f"核对规格后填入 {bound}{attr.unit or ''} 附近的真实值",
        auto_fixable=False,
        confidence=0.8,
    )


def gtin_checksum_ok(code: str) -> bool:
    digits = [int(char) for char in code if char.isdigit()]
    if len(digits) not in {8, 12, 13, 14}:
        return False
    body, check = digits[:-1], digits[-1]
    total = 0
    for index, digit in enumerate(reversed(body)):
        total += digit * (3 if index % 2 == 0 else 1)
    return (10 - total % 10) % 10 == check


def rule_barcode(ctx: RuleContext, product: Product) -> list[Issue]:
    raw = (product.barcode or "").strip()
    if not raw:
        return [
            Issue(
                code="completeness.missing_barcode",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="completeness",
                severity="minor",
                field="barcode",
                message="缺少条码（GTIN/EAN/UPC），渠道对账与比价会失效",
                evidence="字段为空",
                suggestion="补充 13 位 EAN 或 12 位 UPC 条码",
                auto_fixable=False,
                confidence=1.0,
            )
        ]
    digits = re.sub(r"\D", "", raw)
    if len(digits) not in {8, 12, 13, 14}:
        return [
            Issue(
                code="conformance.barcode_checksum",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="conformance",
                severity="major",
                field="barcode",
                message=f"条码「{raw}」长度不是 8/12/13/14 位，不是合法 GTIN",
                evidence=f"解析出 {len(digits)} 位数字",
                suggestion="核对条码位数后重新录入",
                auto_fixable=False,
                confidence=0.99,
            )
        ]
    if not gtin_checksum_ok(digits):
        return [
            Issue(
                code="conformance.barcode_checksum",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="conformance",
                severity="major",
                field="barcode",
                message=f"条码「{raw}」校验位错误，扫描枪会识别失败",
                evidence=f"GTIN 校验位应为 {(10 - sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed([int(c) for c in digits[:-1]]))) % 10) % 10}",
                suggestion="用条码生成器重新导出校验位正确的 GTIN",
                auto_fixable=False,
                confidence=1.0,
            )
        ]
    return []


def rule_price(ctx: RuleContext, product: Product) -> list[Issue]:
    issues: list[Issue] = []
    price = product.price
    if price is None or price <= 0:
        issues.append(
            Issue(
                code="accuracy.price_invalid",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="accuracy",
                severity="critical",
                field="price",
                message=f"售价为 {price!r}，无法上架",
                evidence=str(price),
                suggestion="填写大于 0 的含税售价",
                auto_fixable=False,
                confidence=1.0,
            )
        )
        return issues
    spec = ctx.category(product.category_id)
    if spec and (price < spec.price_floor or price > spec.price_ceiling):
        issues.append(
            Issue(
                code="accuracy.price_out_of_band",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="accuracy",
                severity="major" if price > spec.price_ceiling * 3 else "minor",
                field="price",
                message=(
                    f"售价 ¥{format_number(price)} 超出{spec.name}类目常见区间 "
                    f"¥{spec.price_floor} - ¥{spec.price_ceiling}"
                ),
                evidence=f"{price}",
                suggestion=f"确认是否填错单位或小数点，类目常见价格中位数约 ¥{format_number(ctx.category_median(product.category_id))}",
                auto_fixable=False,
                confidence=0.75,
            )
        )
    # Statistical outliers are compared in log space: merchandise prices are
    # roughly log-distributed, so a linear z-score would flag every premium SKU.
    log_stats = ctx.category_log_stats(product.category_id)
    if log_stats and price > 0:
        median, mad = log_stats
        robust_z = 0.6745 * (math.log(price) - median) / mad
        if abs(robust_z) >= 2.5:
            direction = "高于" if robust_z > 0 else "低于"
            issues.append(
                Issue(
                    code="accuracy.price_outlier",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="accuracy",
                    severity="minor",
                    field="price",
                    message=f"售价 ¥{format_number(price)} 显著{direction}同类目价格分布（对数稳健 z={robust_z:.1f}）",
                    evidence=f"类目价格对数中位数 {median:.2f}，MAD {mad:.2f}",
                    suggestion="确认促销价与吊牌价是否填反，或补充价格说明",
                    auto_fixable=False,
                    confidence=0.68,
                )
            )
    if not (product.currency or "").strip():
        issues.append(
            Issue(
                code="accuracy.price_invalid",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="accuracy",
                severity="minor",
                field="currency",
                message="缺少币种，跨境渠道会按错误币种解析价格",
                evidence="字段为空",
                suggestion="补充币种，如 CNY",
                auto_fixable=True,
                confidence=0.95,
                repair={"kind": "replace_value", "field": "currency", "before": "", "after": "CNY"},
            )
        )
    return issues


_KNOWN_BRANDS = [
    "韶音", "声阔", "漫步者", "小米", "华为", "苹果", "三星",
    "苏泊尔", "九阳", "美的", "摩飞", "小熊",
    "迪卡侬", "安踏", "李宁", "耐克", "阿迪达斯", "lululemon",
    "珀莱雅", "薇诺娜", "修丽可", "玉泽", "理肤泉",
    "安克", "绿联", "倍思", "紫米", "罗马仕",
    "牧高笛", "挪客", "凯乐石", "北面",
]


def rule_brand_conflict(ctx: RuleContext, product: Product) -> list[Issue]:
    brand = (product.brand or "").strip()
    title = product.title or ""
    if not brand or not title:
        return []
    for known in _KNOWN_BRANDS:
        if known.lower() in title.lower() and known.lower() not in brand.lower():
            return [
                Issue(
                    code="consistency.brand_conflict",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="consistency",
                    severity="critical",
                    field="brand",
                    message=f"标题出现「{known}」，但商品品牌是「{brand}」",
                    evidence=f"title={title[:60]}",
                    suggestion=f"确认品牌归属；若非官方授权，请从标题移除「{known}」",
                    auto_fixable=False,
                    confidence=0.88,
                )
            ]
    return []


def rule_variant_consistency(ctx: RuleContext, product: Product) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[tuple, str] = {}
    for index, variant in enumerate(product.variants, start=1):
        if not (variant.variant_id or "").strip():
            issues.append(
                Issue(
                    code="completeness.required_attribute",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="completeness",
                    severity="major",
                    field="variants",
                    message=f"第 {index} 个规格缺少规格编码",
                    evidence="variantId 为空",
                    suggestion="为每个规格分配唯一 SKU 后缀",
                    auto_fixable=False,
                )
            )
        empty_axes = [key for key, value in variant.axes.items() if not str(value).strip()]
        if empty_axes or not variant.axes:
            issues.append(
                Issue(
                    code="consistency.variant_axis_missing",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="consistency",
                    severity="major",
                    field="variants",
                    message=f"规格 {variant.variant_id or index} 缺少规格轴取值",
                    evidence=f"空轴：{', '.join(empty_axes) or '全部'}",
                    suggestion="补齐规格轴（如颜色、尺码），否则前台会生成重复按钮",
                    auto_fixable=False,
                )
            )
        signature = tuple(sorted((key, str(value).strip().lower()) for key, value in variant.axes.items()))
        if signature in seen:
            issues.append(
                Issue(
                    code="consistency.variant_axis_missing",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="consistency",
                    severity="major",
                    field="variants",
                    message=f"规格 {variant.variant_id or index} 与 {seen[signature]} 的规格取值完全重复",
                    evidence=str(dict(signature)),
                    suggestion="合并重复规格或修正规格轴取值",
                    auto_fixable=False,
                )
            )
        else:
            seen[signature] = variant.variant_id or str(index)
        if variant.price is not None and product.price and product.price > 0:
            ratio = variant.price / product.price
            if ratio > 1.35 or ratio < 0.65:
                issues.append(
                    Issue(
                        code="consistency.variant_price_inconsistent",
                        sku=product.sku,
                        product_id=product.product_id,
                        category_id=product.category_id,
                        dimension="consistency",
                        severity="minor",
                        field="variants",
                        message=(
                            f"规格 {variant.variant_id or index} 价格 ¥{format_number(variant.price)} "
                            f"与主售价 ¥{format_number(product.price)} 偏差 {abs(ratio - 1) * 100:.0f}%"
                        ),
                        evidence=f"ratio={ratio:.2f}",
                        suggestion="确认规格加价是否符合定价策略，偏差过大请同步价格表",
                        auto_fixable=False,
                        confidence=0.7,
                    )
                )
    return issues


def rule_attribute_coverage(ctx: RuleContext, product: Product) -> list[Issue]:
    """Flag attributes that exist in the payload but are not declared anywhere."""

    spec = ctx.category(product.category_id)
    if spec is None:
        return []
    known = {attr.key for attr in spec.attributes} | RESERVED_ATTRIBUTE_KEYS
    unknown = [key for key in product.attributes if key not in known and product.attr(key)]
    if not unknown:
        return []
    return [
        Issue(
            code="conformance.unknown_attribute",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="conformance",
            severity="info",
            field="attributes",
            message=f"发现 {len(unknown)} 个未在类目模板中声明的属性：{', '.join(unknown[:5])}",
            evidence=", ".join(unknown),
            suggestion="若属性长期使用，请补充到类目属性模板，或从商品数据中清理",
            auto_fixable=False,
            confidence=0.9,
        )
    ]


def category_median(prices: list[float]) -> float | None:
    clean = [value for value in prices if value and value > 0]
    return statistics.median(clean) if clean else None


def category_mad(prices: list[float]) -> float | None:
    clean = [value for value in prices if value and value > 0]
    if len(clean) < 3:
        return None
    median = statistics.median(clean)
    deviations = [abs(value - median) for value in clean]
    mad = statistics.median(deviations)
    return mad or None

