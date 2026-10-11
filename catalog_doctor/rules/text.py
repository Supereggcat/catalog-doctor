"""Content rules: titles, descriptions, promotional noise, SEO and media."""

from __future__ import annotations

import re
from collections import Counter

from ..models import Issue, Product
from ..taxonomy import BANNED_WORDS, GENERIC_IMAGE_HINTS, PLACEHOLDER_PATTERNS, PROMO_NOISE_CHARS
from .context import RuleContext

HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]{0,120}>")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
MULTISPACE_RE = re.compile(r"\s{2,}")

TITLE_MIN = 8
TITLE_MAX = 90
DESCRIPTION_MIN = 40


def _visible_length(text: str) -> int:
    return len(re.sub(r"\s", "", text or ""))


def rule_title_length(ctx: RuleContext, product: Product) -> list[Issue]:
    title = (product.title or "").strip()
    length = _visible_length(title)
    if length == 0:
        return [
            Issue(
                code="text.title_length",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="text",
                severity="critical",
                field="title",
                message="商品标题为空，搜索与列表页都无法展示",
                evidence="长度 0",
                suggestion="按「品牌 + 核心卖点 + 规格」结构重写标题",
                auto_fixable=False,
            )
        ]
    if length < TITLE_MIN:
        return [
            Issue(
                code="text.title_length",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="text",
                severity="major",
                field="title",
                message=f"标题仅 {length} 个有效字符，低于建议下限 {TITLE_MIN}",
                evidence=title,
                suggestion="补充品牌、型号、核心规格等可检索信息",
                auto_fixable=False,
            )
        ]
    if length > TITLE_MAX:
        return [
            Issue(
                code="text.title_length",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="text",
                severity="minor",
                field="title",
                message=f"标题 {length} 个有效字符，超过建议上限 {TITLE_MAX}，列表页会被截断",
                evidence=title[:80] + "...",
                suggestion="把次要卖点移到卖点区或详情页",
                auto_fixable=False,
            )
        ]
    return []


def rule_banned_word(ctx: RuleContext, product: Product) -> list[Issue]:
    text = f"{product.title} {product.description}"
    for word in BANNED_WORDS:
        if word.lower() in text.lower():
            cleaned = (product.title or "")
            for candidate in BANNED_WORDS:
                cleaned = re.sub(re.escape(candidate), "", cleaned, flags=re.IGNORECASE)
            cleaned = MULTISPACE_RE.sub(" ", cleaned).strip(" -|,，、")
            return [
                Issue(
                    code="text.banned_word",
                    sku=product.sku,
                    product_id=product.product_id,
                    category_id=product.category_id,
                    dimension="text",
                    severity="major",
                    field="title" if word.lower() in (product.title or "").lower() else "description",
                    message=f"文案包含广告法高风险绝对化用语「{word}」",
                    evidence=word,
                    suggestion=f"删除「{word}」并改用可验证的客观描述",
                    auto_fixable=bool(cleaned) and cleaned != product.title,
                    confidence=0.96,
                    repair={
                        "kind": "replace_value",
                        "field": "title",
                        "before": product.title,
                        "after": cleaned,
                    }
                    if cleaned and cleaned != product.title
                    else None,
                )
            ]
    return []


def rule_promo_noise(ctx: RuleContext, product: Product) -> list[Issue]:
    title = product.title or ""
    hits = [char for char in title if char in PROMO_NOISE_CHARS]
    if not hits:
        return []
    severity = "minor" if len(hits) <= 2 else "major"
    cleaned = title
    for char in set(hits):
        cleaned = cleaned.replace(char, "")
    cleaned = MULTISPACE_RE.sub(" ", cleaned).strip()
    return [
        Issue(
            code="text.promo_noise",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="text",
            severity=severity,
            field="title",
            message=f"标题含 {len(hits)} 个促销符号（{''.join(sorted(set(hits)))}），影响搜索分词与专业感",
            evidence="".join(sorted(set(hits))),
            suggestion="移除促销符号，把优惠信息留给营销标签位",
            auto_fixable=bool(cleaned),
            confidence=0.93,
            repair={"kind": "replace_value", "field": "title", "before": title, "after": cleaned},
        )
    ]


def rule_keyword_stuffing(ctx: RuleContext, product: Product) -> list[Issue]:
    title = product.title or ""
    compact = re.sub(r"[\s\-_/|,，。.、]+", "", title)
    if len(compact) < 8:
        return []
    counter: Counter[str] = Counter()
    for size in (2, 3, 4):
        for index in range(len(compact) - size + 1):
            counter[compact[index : index + size]] += 1
    candidates = [(token, count) for token, count in counter.items() if count >= 3]
    if not candidates:
        return []
    candidates.sort(key=lambda item: (item[1], len(item[0])), reverse=True)
    token, count = candidates[0]
    return [
        Issue(
            code="text.keyword_stuffing",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="text",
            severity="minor",
            field="title",
            message=f"标题中「{token}」重复 {count} 次，疑似关键词堆砌",
            evidence=title,
            suggestion="保留一次核心关键词，其余替换为差异化卖点",
            auto_fixable=False,
            confidence=0.72,
        )
    ]


def rule_all_caps(ctx: RuleContext, product: Product) -> list[Issue]:
    title = product.title or ""
    latin = LATIN_RE.findall(title)
    if len(latin) < 8:
        return []
    upper = sum(1 for char in latin if char.isupper())
    ratio = upper / len(latin)
    if ratio <= 0.6:
        return []
    return [
        Issue(
            code="text.all_caps",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="text",
            severity="minor",
            field="title",
            message=f"标题中 {ratio * 100:.0f}% 的拉丁字母为大写，可读性差",
            evidence=title,
            suggestion="改为正常大小写，仅保留商标与型号的大写形式",
            auto_fixable=False,
            confidence=0.8,
        )
    ]


def rule_placeholder_text(ctx: RuleContext, product: Product) -> list[Issue]:
    haystacks = {"title": product.title or "", "description": product.description or ""}
    for field, text in haystacks.items():
        lowered = text.lower()
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in lowered:
                return [
                    Issue(
                        code="text.placeholder_text",
                        sku=product.sku,
                        product_id=product.product_id,
                        category_id=product.category_id,
                        dimension="text",
                        severity="major" if field == "title" else "minor",
                        field=field,
                        message=f"{'标题' if field == 'title' else '详情'}中残留占位文案「{pattern}」",
                        evidence=text[:80],
                        suggestion="替换为真实商品信息后再上架",
                        auto_fixable=False,
                        confidence=0.95,
                    )
                ]
    return []


def rule_description_quality(ctx: RuleContext, product: Product) -> list[Issue]:
    description = product.description or ""
    length = _visible_length(description)
    if length == 0:
        return [
            Issue(
                code="text.description_too_short",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="text",
                severity="major",
                field="description",
                message="详情描述为空，转化率与售后成本都会受影响",
                evidence="长度 0",
                suggestion="补充 3 段式详情：核心卖点 / 规格参数 / 使用与保养",
                auto_fixable=False,
            )
        ]
    if length < DESCRIPTION_MIN:
        return [
            Issue(
                code="text.description_too_short",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="text",
                severity="minor",
                field="description",
                message=f"详情仅 {length} 个有效字符，低于建议下限 {DESCRIPTION_MIN}",
                evidence=description,
                suggestion="补充卖点与规格说明，降低客服咨询量",
                auto_fixable=False,
            )
        ]
    return []


def rule_raw_html(ctx: RuleContext, product: Product) -> list[Issue]:
    description = product.description or ""
    tags = HTML_TAG_RE.findall(description)
    if not tags:
        return []
    cleaned = MULTISPACE_RE.sub(" ", HTML_TAG_RE.sub("", description)).strip()
    return [
        Issue(
            code="text.raw_html",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="text",
            severity="minor",
            field="description",
            message=f"详情中含 {len(tags)} 个未渲染的 HTML 标签（如 {tags[0][:20]}）",
            evidence=tags[0],
            suggestion="清洗标签，或确认详情字段是否支持富文本",
            auto_fixable=bool(cleaned),
            confidence=0.9,
            repair={
                "kind": "replace_value",
                "field": "description",
                "before": description,
                "after": cleaned,
            },
        )
    ]


def rule_seo_keywords(ctx: RuleContext, product: Product) -> list[Issue]:
    keywords = (product.seo_keywords or "").strip()
    if len(keywords) >= 4 and len(re.split(r"[,，;；\s]+", keywords)) >= 2:
        return []
    spec = ctx.category(product.category_id)
    parts = [product.brand, *(spec.keywords[:2] if spec else [])]
    compact_title = re.sub(r"[\s\-_/|,，。.、]+", " ", product.title or "")
    parts.extend([token for token in compact_title.split(" ") if len(token) > 1][:3])
    after = ",".join(dict.fromkeys(part for part in parts if part))[:60]
    return [
        Issue(
            code="seo.keywords_missing",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="seo",
            severity="minor",
            field="seo_keywords",
            message="缺少搜索关键词，站内搜索与外部投放都会丢量",
            evidence=keywords or "字段为空",
            suggestion=f"补充 3-5 个精准关键词，例如：{after}",
            auto_fixable=bool(after),
            confidence=0.7,
            repair={
                "kind": "replace_value",
                "field": "seo_keywords",
                "before": keywords,
                "after": after,
            }
            if after
            else None,
        )
    ]


def rule_brand_in_title(ctx: RuleContext, product: Product) -> list[Issue]:
    brand = (product.brand or "").strip()
    if not brand:
        return [
            Issue(
                code="completeness.missing_brand",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="completeness",
                severity="major",
                field="brand",
                message="品牌字段为空",
                evidence="字段为空",
                suggestion="补充品牌；自有品牌请使用已备案名称",
                auto_fixable=False,
            )
        ]
    if brand.lower() not in (product.title or "").lower():
        suggested = f"{brand} {product.title}".strip()[:60]
        return [
            Issue(
                code="seo.brand_missing_in_title",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="seo",
                severity="info",
                field="title",
                message=f"标题未包含品牌「{brand}」，品牌搜索流量会流失",
                evidence=product.title[:60],
                suggestion=f"在标题开头补上品牌：{suggested}",
                auto_fixable=True,
                confidence=0.65,
                repair={
                    "kind": "replace_value",
                    "field": "title",
                    "before": product.title,
                    "after": suggested,
                },
            )
        ]
    return []


def rule_image_quality(ctx: RuleContext, product: Product) -> list[Issue]:
    issues: list[Issue] = []
    images = [url for url in product.images if (url or "").strip()]
    if not images:
        issues.append(
            Issue(
                code="completeness.missing_image",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="media",
                severity="critical",
                field="images",
                message="商品没有任何图片，无法上架",
                evidence="images=[]",
                suggestion="至少上传 1 张主图与 2 张场景图（1200x1200 以上）",
                auto_fixable=False,
            )
        )
    elif len(images) < 3:
        issues.append(
            Issue(
                code="media.image_count_low",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="media",
                severity="minor",
                field="images",
                message=f"仅有 {len(images)} 张图片，建议至少 3 张（主图 + 细节 + 场景）",
                evidence=", ".join(images),
                suggestion="补充细节图与使用场景图，提升转化率",
                auto_fixable=False,
            )
        )
    invalid = [url for url in images if not re.match(r"^https?://[^\s]+$", url)]
    if invalid:
        issues.append(
            Issue(
                code="media.image_url_invalid",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="media",
                severity="major",
                field="images",
                message=f"{len(invalid)} 个图片地址不是绝对 URL，前台会 404",
                evidence=invalid[0],
                suggestion="改为 https 开头的 CDN 绝对地址",
                auto_fixable=False,
                confidence=0.95,
            )
        )
    generic = [
        url
        for url in images
        if any(hint in url.lower() for hint in GENERIC_IMAGE_HINTS)
    ]
    if generic and len(generic) == len(images):
        issues.append(
            Issue(
                code="media.image_generic_filename",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="media",
                severity="info",
                field="images",
                message="所有图片都是默认/临时文件名，缺少可运营的命名规范",
                evidence=generic[0],
                suggestion="按 brand-sku-angle 规则重命名，便于检索与 CDN 缓存管理",
                auto_fixable=False,
                confidence=0.6,
            )
        )
    if not (product.attr("image_alt") or "").strip():
        issues.append(
            Issue(
                code="media.image_alt_missing",
                sku=product.sku,
                product_id=product.product_id,
                category_id=product.category_id,
                dimension="media",
                severity="info",
                field="image_alt",
                message="主图缺少 alt 文本，无障碍与图片搜索均受损",
                evidence="image_alt 为空",
                suggestion=f"填写「{product.brand} {product.title}」的简短描述",
                auto_fixable=True,
                confidence=0.6,
                repair={
                    "kind": "replace_value",
                    "field": "image_alt",
                    "before": "",
                    "after": f"{product.brand} {product.title}".strip()[:60],
                },
            )
        )
    return issues


def rule_shared_asset(ctx: RuleContext, product: Product) -> list[Issue]:
    if not product.images:
        return []
    cover = product.images[0]
    users = [sku for sku in ctx.image_users(cover) if sku != product.sku]
    if not users:
        return []
    return [
        Issue(
            code="media.image_shared_asset",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="media",
            severity="major",
            field="images",
            message=f"主图与 {len(users)} 个其他 SKU 完全相同，疑似套图或重复铺货",
            evidence=f"{cover} 也被 {', '.join(users[:3])} 使用",
            suggestion="为每个 SKU 提供差异化主图，或合并重复商品",
            auto_fixable=False,
            confidence=0.8,
        )
    ]


def rule_title_duplicate_within_catalog(ctx: RuleContext, product: Product) -> list[Issue]:
    title = re.sub(r"[\s\-_/|,，。.、]+", "", (product.title or "").lower())
    if len(title) < 6:
        return []
    matches = [
        other.sku
        for other in ctx.products
        if other.sku != product.sku
        and re.sub(r"[\s\-_/|,，。.、]+", "", (other.title or "").lower()) == title
    ]
    if not matches:
        return []
    return [
        Issue(
            code="duplication.exact_title",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="duplication",
            severity="major",
            field="title",
            message=f"标题与 {len(matches)} 个 SKU 完全一致：{', '.join(matches[:3])}",
            evidence=product.title,
            suggestion="为每个 SKU 补充差异化规格信息，或按重复铺货流程合并",
            auto_fixable=False,
            confidence=1.0,
        )
    ]

