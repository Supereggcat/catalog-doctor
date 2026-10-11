"""Catalog ingestion: CSV/JSON parsing and the labelled synthetic dataset.

The demo dataset is generated with injected defects, and every injection is
recorded as ground truth. That is what lets ``eval.py`` report precision and
recall instead of a hand-waved percentage.
"""

from __future__ import annotations

import csv
import io
import json
import random
import re
from typing import Any

from .models import Product, Variant
from .taxonomy import CATEGORIES, CATEGORY_MAP

CSV_COLUMNS = [
    "product_id",
    "sku",
    "title",
    "brand",
    "category_id",
    "price",
    "currency",
    "stock",
    "barcode",
    "images",
    "description",
    "attributes",
    "variants",
    "supplier",
    "seo_keywords",
]


# --------------------------------------------------------------------------- #
# CSV / JSON in and out
# --------------------------------------------------------------------------- #


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def product_from_row(row: dict[str, Any]) -> Product:
    attributes = row.get("attributes") or {}
    if isinstance(attributes, str):
        try:
            attributes = json.loads(attributes) if attributes.strip() else {}
        except json.JSONDecodeError:
            attributes = {}
    images = row.get("images") or []
    if isinstance(images, str):
        images = [item.strip() for item in images.split("|") if item.strip()]
    variants_raw = row.get("variants") or []
    if isinstance(variants_raw, str):
        try:
            variants_raw = json.loads(variants_raw) if variants_raw.strip() else []
        except json.JSONDecodeError:
            variants_raw = []
    variants = [
        Variant(
            variant_id=str(item.get("variantId") or item.get("variant_id") or ""),
            axes={str(k): str(v) for k, v in (item.get("axes") or {}).items()},
            price=_as_float(item.get("price")),
            stock=_as_int(item.get("stock")),
        )
        for item in variants_raw
        if isinstance(item, dict)
    ]
    return Product(
        product_id=str(row.get("product_id") or row.get("productId") or ""),
        sku=str(row.get("sku") or ""),
        title=str(row.get("title") or ""),
        brand=str(row.get("brand") or ""),
        category_id=str(row.get("category_id") or row.get("categoryId") or ""),
        price=_as_float(row.get("price")),
        currency=str(row.get("currency") or "CNY"),
        stock=_as_int(row.get("stock")),
        barcode=str(row.get("barcode") or ""),
        images=[str(item) for item in images],
        description=str(row.get("description") or ""),
        attributes={str(k): str(v) for k, v in attributes.items()},
        variants=variants,
        supplier=str(row.get("supplier") or ""),
        seo_keywords=str(row.get("seo_keywords") or row.get("seoKeywords") or ""),
    )


def parse_csv(text: str) -> list[Product]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    products = [product_from_row(row) for row in reader]
    return [product for product in products if product.sku]


def to_csv(products: list[Product]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for product in products:
        writer.writerow(
            {
                "product_id": product.product_id,
                "sku": product.sku,
                "title": product.title,
                "brand": product.brand,
                "category_id": product.category_id,
                "price": product.price,
                "currency": product.currency,
                "stock": product.stock,
                "barcode": product.barcode,
                "images": "|".join(product.images),
                "description": product.description,
                "attributes": json.dumps(product.attributes, ensure_ascii=False),
                "variants": json.dumps(
                    [variant.to_dict() for variant in product.variants], ensure_ascii=False
                ),
                "supplier": product.supplier,
                "seo_keywords": product.seo_keywords,
            }
        )
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Synthetic labeled dataset
# --------------------------------------------------------------------------- #


def ean13(body: str) -> str:
    body = (body + "0" * 12)[:12]
    total = sum(int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body)))
    return body + str((10 - total % 10) % 10)


BLUEPRINTS: dict[str, dict[str, Any]] = {
    "audio": {
        "brands": ["韶音", "声阔", "漫步者", "西圣", "万魔", "击音"],
        "nouns": ["蓝牙耳机", "降噪耳机", "头戴式耳机", "真无线耳机", "便携音箱"],
        "prefix": "AUD",
        "spec": lambda rng: f"{rng.choice([6, 8, 10, 12, 24, 36, 48])}小时续航",
        "supplier": ["深圳声学供应链", "东莞音频制造", "惠州电声工厂"],
    },
    "kitchen": {
        "brands": ["苏泊尔", "九阳", "美的", "摩飞", "小熊", "东菱"],
        "nouns": ["电饭煲", "空气炸锅", "破壁料理机", "养生壶", "电煮锅"],
        "prefix": "KIT",
        "spec": lambda rng: f"{rng.choice([350, 500, 800, 1200, 1500, 1800])}W大功率",
        "supplier": ["顺德小家电基地", "中山厨电制造", "佛山家电工厂"],
    },
    "sportswear": {
        "brands": ["迪卡侬", "安踏", "李宁", "鸿星尔克", "凯乐石", "匹克"],
        "nouns": ["速干T恤", "运动长裤", "瑜伽裤", "跑步外套", "健身背心"],
        "prefix": "SPT",
        "spec": lambda rng: f"{rng.choice(['速干', '透气', '弹力', '轻薄'])}面料",
        "supplier": ["晋江运动服饰", "泉州针织工厂", "石狮服装供应链"],
    },
    "skincare": {
        "brands": ["珀莱雅", "薇诺娜", "玉泽", "可复美", "夸迪", "润百颜"],
        "nouns": ["精华液", "保湿面霜", "氨基酸洁面", "爽肤水", "修护乳液"],
        "prefix": "SKN",
        "spec": lambda rng: f"{rng.choice([15, 30, 50, 100, 120, 200])}ml",
        "supplier": ["广州美妆代工", "上海化妆品制造", "杭州护肤供应链"],
    },
    "mobile": {
        "brands": ["安克", "绿联", "倍思", "紫米", "罗马仕", "图拉斯"],
        "nouns": ["数据线", "氮化镓充电器", "手机壳", "充电宝", "钢化膜"],
        "prefix": "MOB",
        "spec": lambda rng: f"{rng.choice([30, 60, 100, 120, 150, 200])}cm",
        "supplier": ["深圳数码配件厂", "东莞线材制造", "惠州充电配件"],
    },
    "outdoor": {
        "brands": ["牧高笛", "挪客", "凯乐石", "骆驼", "探路者", "黑冰"],
        "nouns": ["登山背包", "露营帐篷", "轻量睡袋", "折叠椅", "保温杯"],
        "prefix": "OUT",
        "spec": lambda rng: f"{rng.choice([20, 30, 45, 60, 75, 90])}L容量",
        "supplier": ["宁波户外制造", "台州露营装备", "扬州户外供应链"],
    },
}

COLOR_POOL = ["黑", "白", "灰", "银", "蓝", "绿", "粉", "红"]
SIZE_POOL = ["S", "M", "L", "XL", "XXL"]
MATERIAL_POOL = ["不锈钢", "塑料", "玻璃", "铝合金", "硅胶", "帆布"]


def _clean_attributes(rng: random.Random, category_id: str) -> dict[str, str]:
    if category_id == "audio":
        return {
            "color": rng.choice(["黑", "白", "灰", "蓝", "粉"]),
            "connectivity": rng.choice(["蓝牙", "有线", "2.4G", "双模"]),
            "battery_hours": f"{rng.choice([6, 8, 10, 12, 24, 36, 48])}h",
            "weight": f"{rng.choice([18, 32, 45, 68, 120, 240, 320])}g",
            "driver_size": f"{rng.choice([6, 8, 10, 12, 13, 40, 50])}mm",
            "impedance": str(rng.choice([16, 24, 32, 40, 64, 150])),
            "noise_cancelling": rng.choice(["是", "否"]),
            "waterproof": rng.choice(["IPX4", "IPX5", "IPX7", "无"]),
            "warranty_months": str(rng.choice([6, 12, 18, 24])),
        }
    if category_id == "kitchen":
        return {
            "power_w": str(rng.choice([350, 500, 800, 1000, 1200, 1500, 1800, 2200])),
            "capacity": f"{rng.choice([0.8, 1.2, 1.8, 3, 5, 6])}L",
            "voltage": rng.choice(["220V", "110V", "100-240V"]),
            "material": rng.choice(MATERIAL_POOL),
            "weight": f"{rng.choice([0.8, 1.4, 2.2, 3.5, 5.6, 8.2])}kg",
            "dishwasher_safe": rng.choice(["是", "否"]),
            "warranty_months": str(rng.choice([12, 24, 36])),
        }
    if category_id == "sportswear":
        return {
            "size": rng.choice(SIZE_POOL),
            "color": rng.choice(COLOR_POOL),
            "fabric": rng.choice(["涤纶", "棉", "锦纶", "氨纶混纺", "羊毛"]),
            "gender": rng.choice(["男", "女", "中性"]),
            "weight": f"{rng.choice([120, 160, 210, 280, 340, 420])}g",
            "season": rng.choice(["春夏", "秋冬", "四季"]),
            "sport_type": rng.choice(["跑步", "健身", "户外", "球类", "瑜伽"]),
        }
    if category_id == "skincare":
        return {
            "volume": f"{rng.choice([15, 30, 50, 100, 120, 200])}ml",
            "skin_type": rng.choice(["干性", "油性", "混合性", "敏感性", "全肤质"]),
            "shelf_life_months": str(rng.choice([12, 18, 24, 36])),
            "ingredients": rng.choice(
                [
                    "烟酰胺、透明质酸钠、泛醇、积雪草提取物",
                    "神经酰胺、角鲨烷、甘油、燕麦仁提取物",
                    "维生素C衍生物、光甘草定、水解胶原",
                    "二裂酵母发酵产物、依克多因、泛醇",
                ]
            ),
            "origin": rng.choice(["中国", "韩国", "日本", "法国", "美国"]),
            "spf": str(rng.choice([0, 15, 30, 50])),
            "fragrance_free": rng.choice(["是", "否"]),
        }
    if category_id == "mobile":
        return {
            "compatible_brand": rng.choice(["苹果", "华为", "小米", "三星", "OPPO", "vivo", "通用"]),
            "material": rng.choice(["塑料", "铝合金", "硅胶", "玻璃"]),
            "length": f"{rng.choice([30, 60, 100, 120, 150, 200])}cm",
            "weight": f"{rng.choice([28, 45, 90, 180, 260, 420])}g",
            "color": rng.choice(COLOR_POOL),
            "fast_charge_w": str(rng.choice([18, 20, 30, 45, 65, 100, 120])),
            "warranty_months": str(rng.choice([6, 12, 18, 24])),
        }
    return {
        "capacity": f"{rng.choice([20, 30, 45, 60, 75, 90])}L",
        "material": rng.choice(["帆布", "铝合金", "塑料", "不锈钢"]),
        "weight": f"{rng.choice([280, 650, 1200, 1800, 2600, 4200])}g",
        "waterproof": rng.choice(["IPX4", "IPX5", "IPX7", "无"]),
        "color": rng.choice(COLOR_POOL),
        "foldable": rng.choice(["是", "否"]),
        "warranty_months": str(rng.choice([12, 24, 36])),
    }


def _price(rng: random.Random, category_id: str) -> float:
    spec = CATEGORY_MAP[category_id]
    low = spec.price_floor * 1.2
    high = spec.price_ceiling * 0.55
    value = low * (high / low) ** rng.random()
    if value < 200:
        return float(int(value) + 0.9)
    return float(int(round(value / 10.0)) * 10 - 1)


def _images(category_id: str, sku: str) -> list[str]:
    base = f"https://cdn.example.com/catalog/{category_id}/{sku.lower()}"
    return [f"{base}-main.jpg", f"{base}-detail.jpg", f"{base}-scene.jpg"]


def _make_product(rng: random.Random, index: int, category_id: str) -> Product:
    blueprint = BLUEPRINTS[category_id]
    spec = CATEGORY_MAP[category_id]
    brand = rng.choice(blueprint["brands"])
    noun = rng.choice(blueprint["nouns"])
    sku = f"{blueprint['prefix']}-{2000 + index}"
    model = f"{blueprint['prefix']}{100 + (index % 700)}"
    attributes = _clean_attributes(rng, category_id)
    color = attributes.get("color", "黑")
    title = f"{brand} {model} {noun} {blueprint['spec'](rng)} {color} 官方正品"
    price = _price(rng, category_id)
    keywords = ",".join([brand, blueprint["nouns"][0], noun, model])
    return Product(
        product_id=f"P{100000 + index}",
        sku=sku,
        title=title,
        brand=brand,
        category_id=category_id,
        price=price,
        currency="CNY",
        stock=rng.choice([0, 12, 35, 80, 160, 420, 900]),
        barcode=ean13(f"69{index:010d}"),
        images=_images(category_id, sku),
        description=(
            f"{brand} {noun}，采用{blueprint['spec'](rng)}设计，出厂前完成全检。"
            f"适用场景覆盖日常通勤与户外使用，随包附赠说明书与保修卡。"
            f"类目：{spec.name}；型号：{model}。"
        ),
        attributes={**attributes, "image_alt": f"{brand} {noun}"},
        variants=[
            Variant(
                variant_id=f"{sku}-01",
                axes={"color": color},
                price=price,
                stock=rng.choice([5, 20, 60, 120]),
            )
        ],
        supplier=rng.choice(blueprint["supplier"]),
        seo_keywords=keywords,
    )


# --------------------------------------------------------------------------- #
# Defect injectors - each returns the machine codes it is expected to trigger
# --------------------------------------------------------------------------- #


def _inject_missing_attribute(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    key = rng.choice(spec.required_keys)
    product.attributes.pop(key, None)
    return ["completeness.required_attribute"]


def _inject_enum_alias(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]

    def normalize(value: str) -> str:
        return re.sub(r"[\s\-_/,，。.、()（）:：;；]+", "", value).lower()

    def alias_keys(attr) -> list[str]:
        return [key for key, value in attr.aliases.items() if normalize(key) != normalize(value)]

    candidates = [attr for attr in spec.attributes if attr.dtype == "enum" and alias_keys(attr)]
    if not candidates:
        return []
    attr = rng.choice(candidates)
    product.attributes[attr.key] = rng.choice(alias_keys(attr))
    return ["conformance.enum_value_invalid"]


def _inject_enum_invalid(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    enum_attr = next((attr for attr in spec.attributes if attr.dtype == "enum"), None)
    if enum_attr is None:
        return _inject_enum_alias(product, rng)
    product.attributes[enum_attr.key] = rng.choice(["未知规格", "标准版加强款", "N/A"])
    return ["conformance.enum_value_invalid"]


def _inject_unit_mismatch(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    convertible_units = {"g", "kg", "cm", "mm", "ml", "L"}
    dim_attr = next(
        (
            attr
            for attr in spec.attributes
            if attr.dtype == "dimension" and attr.unit in convertible_units
        ),
        None,
    )
    if dim_attr is None:
        return []
    raw = product.attr(dim_attr.key)
    if dim_attr.unit == "g":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('g') or 100) / 1000:.3f}kg"
    elif dim_attr.unit == "kg":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('kg') or 1) * 1000:.0f}g"
    elif dim_attr.unit == "cm":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('cm') or 30) * 10:.0f}mm"
    elif dim_attr.unit == "mm":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('mm') or 10) / 10:.1f}cm"
    elif dim_attr.unit == "ml":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('ml') or 30) / 1000:.3f}L"
    elif dim_attr.unit == "L":
        product.attributes[dim_attr.key] = f"{float(raw.removesuffix('L') or 2) * 1000:.0f}ml"
    else:
        return []
    return ["conformance.unit_mismatch"]


def _inject_out_of_range(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    candidate = next(
        (attr for attr in spec.attributes if attr.dtype in {"number", "dimension"} and attr.max_value),
        None,
    )
    if candidate is None:
        return []
    product.attributes[candidate.key] = f"{candidate.max_value * 7:.0f}{candidate.unit or ''}"
    return ["conformance.numeric_out_of_range"]


def _inject_not_parseable(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    candidate = next(
        (attr for attr in spec.attributes if attr.dtype in {"number", "dimension"}), None
    )
    if candidate is None:
        return []
    product.attributes[candidate.key] = rng.choice(["待定", "三十二", "未知"])
    return ["conformance.numeric_not_parseable"]


def _inject_barcode_bad(product: Product, rng: random.Random) -> list[str]:
    digits = list(product.barcode)
    index = rng.randrange(0, 11)
    digits[index] = str((int(digits[index]) + 1) % 10)
    product.barcode = "".join(digits)
    return ["conformance.barcode_checksum"]


def _inject_barcode_missing(product: Product, rng: random.Random) -> list[str]:
    product.barcode = ""
    return ["completeness.missing_barcode"]


def _inject_price_invalid(product: Product, rng: random.Random) -> list[str]:
    product.price = rng.choice([0.0, -1.0])
    return ["accuracy.price_invalid"]


def _inject_price_outlier(product: Product, rng: random.Random) -> list[str]:
    spec = CATEGORY_MAP[product.category_id]
    product.price = round(spec.price_ceiling * rng.choice([20, 30, 40]), 2)
    product.variants = [
        Variant(
            variant_id=variant.variant_id,
            axes=dict(variant.axes),
            price=product.price,
            stock=variant.stock,
        )
        for variant in product.variants
    ]
    return ["accuracy.price_out_of_band", "accuracy.price_outlier"]


def _inject_banned_word(product: Product, rng: random.Random) -> list[str]:
    product.title = f"{product.title} {rng.choice(['全网最低', '销量第一', '100%有效', '国家级'])}"
    return ["text.banned_word"]


def _inject_promo_noise(product: Product, rng: random.Random) -> list[str]:
    product.title = f"{product.title} {rng.choice(['🔥', '★', '⚡️'])}限时"
    return ["text.promo_noise"]


def _inject_title_short(product: Product, rng: random.Random) -> list[str]:
    product.title = f"{product.brand} {product.sku[-3:]}"
    return ["text.title_length"]


def _inject_title_long(product: Product, rng: random.Random) -> list[str]:
    filler = (
        "本商品出厂前完成多轮质检并适配通勤差旅居家露营等多种使用场景随附说明书保修卡"
        "包装内附赠收纳袋与备用配件具体以详情页公示为准支持七天无理由退换并享受全国联保"
    )
    product.title = f"{product.title} {filler}"
    return ["text.title_length"]


def _inject_description_short(product: Product, rng: random.Random) -> list[str]:
    product.description = "新品上架"
    return ["text.description_too_short"]


def _inject_placeholder(product: Product, rng: random.Random) -> list[str]:
    product.description = rng.choice(["待补充", "TODO", "lorem ipsum"])
    return ["text.placeholder_text", "text.description_too_short"]


def _inject_raw_html(product: Product, rng: random.Random) -> list[str]:
    product.description = f"{product.description}<div class=\"detail-wrap\"><span>规格说明</span></div>"
    return ["text.raw_html"]


def _inject_seo_missing(product: Product, rng: random.Random) -> list[str]:
    product.seo_keywords = ""
    return ["seo.keywords_missing"]


def _inject_images_low(product: Product, rng: random.Random) -> list[str]:
    product.images = product.images[:1]
    return ["media.image_count_low"]


def _inject_image_url_invalid(product: Product, rng: random.Random) -> list[str]:
    product.images = [*product.images[:1], "/uploads/local-only.jpg", *product.images[2:]]
    return ["media.image_url_invalid"]


def _inject_brand_missing(product: Product, rng: random.Random) -> list[str]:
    product.brand = ""
    return ["completeness.missing_brand"]


def _inject_brand_conflict(product: Product, rng: random.Random) -> list[str]:
    product.brand = "漫步者"
    product.title = f"小米 {product.title}"
    return ["consistency.brand_conflict", "seo.brand_missing_in_title"]


def _inject_variant_axis_missing(product: Product, rng: random.Random) -> list[str]:
    product.variants = [Variant(variant_id=f"{product.sku}-01", axes={}, price=product.price, stock=10)]
    return ["consistency.variant_axis_missing"]


def _inject_variant_price(product: Product, rng: random.Random) -> list[str]:
    product.variants = [
        Variant(
            variant_id=f"{product.sku}-01",
            axes={"color": product.attr("color") or "黑"},
            price=round((product.price or 100) * 2.1, 2),
            stock=10,
        )
    ]
    return ["consistency.variant_price_inconsistent"]


def _inject_unknown_attribute(product: Product, rng: random.Random) -> list[str]:
    product.attributes["custom_flag"] = "1"
    return ["conformance.unknown_attribute"]


def _inject_all_caps(product: Product, rng: random.Random) -> list[str]:
    product.title = f"PREMIUM BLUETOOTH WIRELESS AUDIO DEVICE {product.sku}"
    return ["text.all_caps", "seo.brand_missing_in_title"]


def _inject_keyword_stuffing(product: Product, rng: random.Random) -> list[str]:
    noun = CATEGORY_MAP[product.category_id].keywords[0]
    product.title = f"{product.brand} {noun} {noun} {noun} {product.sku}"
    return ["text.keyword_stuffing"]


INJECTORS = [
    _inject_missing_attribute,
    _inject_enum_alias,
    _inject_enum_invalid,
    _inject_unit_mismatch,
    _inject_out_of_range,
    _inject_not_parseable,
    _inject_barcode_bad,
    _inject_barcode_missing,
    _inject_price_invalid,
    _inject_price_outlier,
    _inject_banned_word,
    _inject_promo_noise,
    _inject_title_short,
    _inject_title_long,
    _inject_description_short,
    _inject_placeholder,
    _inject_raw_html,
    _inject_seo_missing,
    _inject_images_low,
    _inject_image_url_invalid,
    _inject_brand_missing,
    _inject_brand_conflict,
    _inject_variant_axis_missing,
    _inject_variant_price,
    _inject_unknown_attribute,
    _inject_all_caps,
    _inject_keyword_stuffing,
]

# Defects that are deliberately *not* implemented by any rule. They stay in the
# labelled set so the evaluation can report an honest capability boundary instead
# of a self-fulfilling 100% score.
UNCOVERED_CODES = [
    "uncovered.title_spec_conflict",
    "uncovered.image_resolution",
    "uncovered.irrelevant_keyword",
]


def _inject_uncovered(product: Product, rng: random.Random, kind: str) -> None:
    if kind == "uncovered.title_spec_conflict":
        product.title = re.sub(r"\d+", lambda match: str(int(match.group()) + 40), product.title, count=1)
    elif kind == "uncovered.image_resolution":
        product.images = [
            f"{product.images[0]}?w=320&h=320",
            *product.images[1:],
        ]
    else:
        product.title = f"{product.title} 宠物用品"


def generate_demo_dataset(
    seed: int = 20261011,
    clean_count: int = 140,
    dirty_count: int = 260,
    duplicate_pairs: int = 40,
    distractor_pairs: int = 20,
    uncovered_count: int = 12,
) -> tuple[list[Product], dict[str, list[str]], list[list[str]], list[str]]:
    """Build a labelled dataset.

    Returns ``(products, labels, duplicate_labels, distractors)`` where ``labels``
    maps SKU to the list of rule codes that *should* fire, ``duplicate_labels``
    lists the SKUs a human would call duplicates, and ``distractors`` holds the
    similar-but-distinct SKUs used as a false-positive stress test.
    """

    rng = random.Random(seed)
    category_cycle = [category.category_id for category in CATEGORIES]
    products: list[Product] = []
    labels: dict[str, list[str]] = {}

    total = clean_count + dirty_count + duplicate_pairs * 2 + distractor_pairs * 2 + uncovered_count
    for index in range(total):
        category_id = category_cycle[index % len(category_cycle)]
        products.append(_make_product(rng, index, category_id))

    cursor = 0
    clean = products[cursor : cursor + clean_count]
    cursor += clean_count
    for product in clean:
        labels[product.sku] = []

    dirty = products[cursor : cursor + dirty_count]
    cursor += dirty_count
    for position, product in enumerate(dirty):
        chosen = INJECTORS[(position * 7 + rng.randrange(len(INJECTORS))) % len(INJECTORS)]
        codes = chosen(product, rng)
        if not codes:  # injector could not apply to this category
            codes = _inject_missing_attribute(product, rng)
        labels[product.sku] = codes

    duplicate_labels: list[list[str]] = []
    duplicate_zone = products[cursor : cursor + duplicate_pairs * 2]
    cursor += duplicate_pairs * 2
    for position in range(duplicate_pairs):
        original = duplicate_zone[position * 2]
        clone = duplicate_zone[position * 2 + 1]
        clone.category_id = original.category_id
        clone.brand = original.brand
        clone.title = (
            f"{original.brand} 官方正品 "
            f"{original.title.replace(original.brand, '').strip()} 同款包邮"
        )
        clone.barcode = original.barcode
        clone.images = list(original.images)
        clone.attributes = dict(original.attributes)
        clone.description = original.description
        clone.price = original.price
        clone.variants = [
            Variant(
                variant_id=f"{clone.sku}-01",
                axes=dict(variant.axes),
                price=clone.price,
                stock=variant.stock,
            )
            for variant in original.variants
        ]
        clone.supplier = original.supplier
        clone.seo_keywords = f"{original.brand},{original.sku},同款"
        labels[original.sku] = ["duplication.near_duplicate", "media.image_shared_asset"]
        labels[clone.sku] = ["duplication.near_duplicate", "media.image_shared_asset"]
        duplicate_labels.append([original.sku, clone.sku])

    distractor_skus: list[str] = []
    distractor_zone = products[cursor : cursor + distractor_pairs * 2]
    for position in range(distractor_pairs):
        left = distractor_zone[position * 2]
        right = distractor_zone[position * 2 + 1]
        right.brand = left.brand
        right.category_id = left.category_id
        right.title = (
            f"{left.brand} {CATEGORY_MAP[left.category_id].name} "
            f"{position + 40}系列 {left.sku[-2:]}号 独立型号"
        )
        right.attributes = _clean_attributes(rng, left.category_id)
        right.attributes["image_alt"] = f"{right.brand} {CATEGORY_MAP[right.category_id].name}"
        spec = CATEGORY_MAP[left.category_id]
        floor = spec.price_floor * 1.05
        ceiling = spec.price_ceiling * 0.9
        right.price = round(
            min(max((left.price or floor) * rng.choice([0.82, 1.0, 1.15]), floor), ceiling), 2
        )
        right.barcode = ean13(f"77{position:010d}")
        right.images = _images(right.category_id, right.sku)
        right.variants = [
            Variant(
                variant_id=f"{right.sku}-01",
                axes={"color": right.attributes.get("color", "黑")},
                price=right.price,
                stock=20,
            )
        ]
        right.seo_keywords = f"{right.brand},{spec.name},{position}系列,独立型号"
        right.description = (
            f"{right.brand} {spec.name} {position + 40} 系列独立型号，与同品牌其他型号共用售后体系。"
            f"包装内含说明书与保修卡，适用于日常使用场景。"
        )
        labels[left.sku] = []
        labels[right.sku] = []
        distractor_skus.extend([left.sku, right.sku])
    uncovered_zone = products[cursor : cursor + uncovered_count]
    for position, product in enumerate(uncovered_zone):
        kind = UNCOVERED_CODES[position % len(UNCOVERED_CODES)]
        _inject_uncovered(product, rng, kind)
        labels[product.sku] = [kind]
    return products, labels, duplicate_labels, distractor_skus

