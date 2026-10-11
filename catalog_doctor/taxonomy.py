"""Declarative catalog taxonomy: category specs, enum vocabularies and units.

The taxonomy is the contract every rule validates against. Keeping it in one
declarative module means a merchant can support a new category without touching
the rule engine - the same separation Bagisto and Saleor use for attribute sets.
"""

from __future__ import annotations

import re
from typing import Any

from .models import AttributeSpec, CategorySpec

# --------------------------------------------------------------------------- #
# Enum vocabularies and their accepted spellings
# --------------------------------------------------------------------------- #

COLOR_ALIASES = {
    "黑": "黑", "黑色": "黑", "black": "黑", "blk": "黑", "曜石黑": "黑", "深空黑": "黑",
    "白": "白", "白色": "白", "white": "白", "珍珠白": "白", "云白": "白",
    "灰": "灰", "灰色": "灰", "gray": "灰", "grey": "灰", "深灰": "灰", "银灰": "灰",
    "银": "银", "银色": "银", "silver": "银", "星空银": "银",
    "蓝": "蓝", "蓝色": "蓝", "blue": "蓝", "藏青": "蓝", "海军蓝": "蓝", "雾霾蓝": "蓝",
    "红": "红", "红色": "红", "red": "红", "酒红": "红", "樱桃红": "红",
    "绿": "绿", "绿色": "绿", "green": "绿", "军绿": "绿", "薄荷绿": "绿",
    "粉": "粉", "粉色": "粉", "pink": "粉", "樱花粉": "粉", "藕粉": "粉",
    "紫": "紫", "紫色": "紫", "purple": "紫", "香芋紫": "紫",
    "黄": "黄", "黄色": "黄", "yellow": "黄", "姜黄": "黄",
    "棕": "棕", "棕色": "棕", "brown": "棕", "咖啡色": "棕", "卡其": "棕",
    "透明": "透明", "transparent": "透明", "clear": "透明",
}

SIZE_ALIASES = {
    "xs": "XS", "xsmall": "XS", "加小": "XS", "特小": "XS",
    "s": "S", "small": "S", "小": "S", "小号": "S", "s码": "S",
    "m": "M", "medium": "M", "中": "M", "中号": "M", "m码": "M",
    "l": "L", "large": "L", "大": "L", "大号": "L", "l码": "L",
    "xl": "XL", "xlarge": "XL", "加大": "XL", "加大号": "XL", "xl码": "XL", "xl号": "XL",
    "xxl": "XXL", "2xl": "XXL", "xxlarge": "XXL", "双加大": "XXL", "xxl码": "XXL",
    "xxxl": "XXXL", "3xl": "XXXL", "三加大": "XXXL",
    "均码": "均码", "free": "均码", "onesize": "均码", "one_size": "均码",
    "36": "36", "37": "37", "38": "38", "39": "39", "40": "40", "41": "41",
    "42": "42", "43": "43", "44": "44", "45": "45",
}

MATERIAL_ALIASES = {
    "不锈钢": "不锈钢", "304不锈钢": "不锈钢", "316不锈钢": "不锈钢", "不锈钢材质": "不锈钢",
    "sts": "不锈钢", "stainless": "不锈钢", "stainlesssteel": "不锈钢",
    "塑料": "塑料", "abs塑料": "塑料", "abs": "塑料", "pc": "塑料", "pp": "塑料", "tpu": "塑料",
    "玻璃": "玻璃", "钢化玻璃": "玻璃", "glass": "玻璃", "高硼硅玻璃": "玻璃",
    "陶瓷": "陶瓷", "瓷": "陶瓷", "ceramic": "陶瓷", "搪瓷": "陶瓷",
    "铸铁": "铸铁", "生铁": "铸铁", "castiron": "铸铁",
    "涤纶": "涤纶", "聚酯纤维": "涤纶", "polyester": "涤纶",
    "棉": "棉", "纯棉": "棉", "全棉": "棉", "cotton": "棉", "精梳棉": "棉",
    "锦纶": "锦纶", "尼龙": "锦纶", "nylon": "锦纶", "尼龙布": "锦纶",
    "氨纶混纺": "氨纶混纺", "氨纶": "氨纶混纺", "弹力棉": "氨纶混纺", "spandex": "氨纶混纺",
    "羊毛": "羊毛", "美利奴羊毛": "羊毛", "wool": "羊毛",
    "铝合金": "铝合金", "铝": "铝合金", "aluminum": "铝合金", "aluminium": "铝合金",
    "硅胶": "硅胶", "silicone": "硅胶",
    "帆布": "帆布", "canvas": "帆布", "牛津布": "帆布",
}

VOLTAGE_ALIASES = {
    "220v": "220V", "220": "220V", "220v50hz": "220V", "220伏": "220V", "国标电压": "220V",
    "110v": "110V", "110": "110V", "110伏": "110V", "美规电压": "110V",
    "100240v": "100-240V", "100-240v": "100-240V", "宽电压": "100-240V",
    "100v240v": "100-240V", "全球电压": "100-240V",
}

CONNECTIVITY_ALIASES = {
    "蓝牙": "蓝牙", "bluetooth": "蓝牙", "bt": "蓝牙", "无线蓝牙": "蓝牙",
    "蓝牙5.0": "蓝牙", "蓝牙5.1": "蓝牙", "蓝牙5.2": "蓝牙", "蓝牙5.3": "蓝牙",
    "蓝牙5.4": "蓝牙", "wireless": "蓝牙",
    "有线": "有线", "wired": "有线", "3.5mm": "有线", "type-c有线": "有线",
    "2.4g": "2.4G", "2.4ghz": "2.4G", "2.4G无线": "2.4G", "usb接收器": "2.4G",
    "双模": "双模", "蓝牙+2.4g": "双模", "dual": "双模", "蓝牙有线双模": "双模",
}

SKIN_TYPE_ALIASES = {
    "干性": "干性", "干皮": "干性", "dry": "干性", "干性肌肤": "干性",
    "油性": "油性", "油皮": "油性", "oily": "油性", "油性肌肤": "油性",
    "混合性": "混合性", "混油": "混合性", "混干": "混合性", "combination": "混合性",
    "敏感性": "敏感性", "敏感肌": "敏感性", "敏感": "敏感性", "sensitive": "敏感性",
    "全肤质": "全肤质", "所有肤质": "全肤质", "任何肤质": "全肤质", "all": "全肤质",
    "通用": "全肤质", "allskintypes": "全肤质",
}

ORIGIN_ALIASES = {
    "中国": "中国", "国产": "中国", "中国制造": "中国", "china": "中国", "中国大陆": "中国",
    "韩国": "韩国", "韩产": "韩国", "korea": "韩国", "韩国制造": "韩国", "南韩": "韩国",
    "日本": "日本", "日产": "日本", "japan": "日本", "日本制造": "日本",
    "法国": "法国", "france": "法国", "法国制造": "法国",
    "美国": "美国", "usa": "美国", "美国制造": "美国", "us": "美国",
    "德国": "德国", "germany": "德国", "德国制造": "德国",
    "澳大利亚": "澳大利亚", "澳洲": "澳大利亚", "australia": "澳大利亚",
}

GENDER_ALIASES = {
    "男": "男", "男士": "男", "男款": "男", "men": "男", "male": "男", "man": "男",
    "女": "女", "女士": "女", "女款": "女", "women": "女", "female": "女", "woman": "女",
    "中性": "中性", "男女同款": "中性", "unisex": "中性", "通用款": "中性",
}

SEASON_ALIASES = {
    "春夏": "春夏", "春季": "春夏", "夏季": "春夏", "spring": "春夏", "summer": "春夏",
    "秋冬": "秋冬", "秋季": "秋冬", "冬季": "秋冬", "autumn": "秋冬", "winter": "秋冬",
    "四季": "四季", "allseason": "四季", "全年": "四季",
}

SPORT_TYPE_ALIASES = {
    "跑步": "跑步", "running": "跑步", "慢跑": "跑步", "马拉松": "跑步",
    "健身": "健身", "训练": "健身", "gym": "健身", "力量训练": "健身",
    "户外": "户外", "徒步": "户外", "登山": "户外", "outdoor": "户外",
    "球类": "球类", "篮球": "球类", "足球": "球类", "羽毛球": "球类",
    "游泳": "游泳", "swimming": "游泳", "泳池": "游泳",
    "瑜伽": "瑜伽", "普拉提": "瑜伽", "yoga": "瑜伽",
}

COMPATIBLE_BRAND_ALIASES = {
    "苹果": "苹果", "apple": "苹果", "iphone": "苹果", "ipad": "苹果", "ios": "苹果",
    "华为": "华为", "huawei": "华为", "荣耀": "华为", "honor": "华为",
    "小米": "小米", "xiaomi": "小米", "红米": "小米", "redmi": "小米",
    "三星": "三星", "samsung": "三星", "galaxy": "三星",
    "oppo": "OPPO", "欧珀": "OPPO", "一加": "OPPO", "oneplus": "OPPO",
    "vivo": "vivo", "维沃": "vivo", "iqoo": "vivo",
    "通用": "通用", "万能": "通用", "universal": "通用", "全兼容": "通用",
}

WATERPROOF_ALIASES = {
    "ipx4": "IPX4", "ipx4级": "IPX4", "防溅水": "IPX4", "生活防水": "IPX4",
    "ipx5": "IPX5", "ipx5级": "IPX5", "防喷水": "IPX5",
    "ipx7": "IPX7", "ipx7级": "IPX7", "可水洗": "IPX7", "ip67": "IPX7", "ip68": "IPX8",
    "ipx8": "IPX8", "ipx8级": "IPX8", "游泳级": "IPX8", "潜水级": "IPX8",
    "无": "无", "不防水": "无", "none": "无", "ipx0": "无",
}

FABRIC_ALIASES = {
    "涤纶": "涤纶", "聚酯纤维": "涤纶", "polyester": "涤纶", "速干面料": "涤纶",
    "棉": "棉", "纯棉": "棉", "全棉": "棉", "cotton": "棉",
    "锦纶": "锦纶", "尼龙": "锦纶", "nylon": "锦纶",
    "氨纶混纺": "氨纶混纺", "弹力面料": "氨纶混纺", "spandex": "氨纶混纺",
    "羊毛": "羊毛", "美利奴": "羊毛", "wool": "羊毛",
}

ENUM_ALIASES: dict[str, dict[str, str]] = {
    "color": COLOR_ALIASES,
    "size": SIZE_ALIASES,
    "material": MATERIAL_ALIASES,
    "voltage": VOLTAGE_ALIASES,
    "connectivity": CONNECTIVITY_ALIASES,
    "skin_type": SKIN_TYPE_ALIASES,
    "origin": ORIGIN_ALIASES,
    "gender": GENDER_ALIASES,
    "season": SEASON_ALIASES,
    "sport_type": SPORT_TYPE_ALIASES,
    "compatible_brand": COMPATIBLE_BRAND_ALIASES,
    "waterproof": WATERPROOF_ALIASES,
    "fabric": FABRIC_ALIASES,
}

CANONICAL_ENUMS: dict[str, list[str]] = {
    "color": ["黑", "白", "灰", "银", "蓝", "红", "绿", "粉", "紫", "黄", "棕", "透明"],
    "size": ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "均码"],
    "material": [
        "不锈钢", "塑料", "玻璃", "陶瓷", "铸铁", "铝合金", "硅胶",
        "涤纶", "棉", "锦纶", "氨纶混纺", "羊毛", "帆布",
    ],
    "voltage": ["220V", "110V", "100-240V"],
    "connectivity": ["蓝牙", "有线", "2.4G", "双模"],
    "skin_type": ["干性", "油性", "混合性", "敏感性", "全肤质"],
    "origin": ["中国", "韩国", "日本", "法国", "美国", "德国", "澳大利亚"],
    "gender": ["男", "女", "中性"],
    "season": ["春夏", "秋冬", "四季"],
    "sport_type": ["跑步", "健身", "户外", "球类", "游泳", "瑜伽"],
    "compatible_brand": ["苹果", "华为", "小米", "三星", "OPPO", "vivo", "通用"],
    "waterproof": ["IPX4", "IPX5", "IPX7", "IPX8", "无"],
    "fabric": ["涤纶", "棉", "锦纶", "氨纶混纺", "羊毛"],
}

# --------------------------------------------------------------------------- #
# Unit handling
# --------------------------------------------------------------------------- #

UNIT_FAMILIES: dict[str, dict[str, float]] = {
    "mass": {"g": 1.0, "kg": 1000.0, "mg": 0.001, "lb": 453.59237, "oz": 28.349523,
             "克": 1.0, "千克": 1000.0, "公斤": 1000.0, "斤": 500.0, "两": 50.0, "磅": 453.59237},
    "length": {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "inch": 25.4,
               "英寸": 25.4, "寸": 33.3333, "毫米": 1.0, "厘米": 10.0, "米": 1000.0},
    "volume": {"ml": 1.0, "l": 1000.0, "cl": 10.0, "floz": 29.5735, "oz": 29.5735,
               "毫升": 1.0, "升": 1000.0},
    "power": {"w": 1.0, "kw": 1000.0, "瓦": 1.0, "千瓦": 1000.0},
    "duration": {"h": 1.0, "hr": 1.0, "hour": 1.0, "hours": 1.0, "min": 1 / 60,
                 "分钟": 1 / 60, "小时": 1.0},
}

UNIT_TO_FAMILY: dict[str, str] = {}
for _family, _units in UNIT_FAMILIES.items():
    for _unit in _units:
        UNIT_TO_FAMILY[_unit] = _family

MEASUREMENT_RE = re.compile(
    r"^\s*(?P<num>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z\u4e00-\u9fff°Ω%/]{0,8})\s*$"
)


def normalize_unit_token(unit: str) -> str:
    token = (unit or "").strip().lower().replace(" ", "")
    token = token.replace("小时", "小时").replace("毫", "毫")
    return token


def parse_measurement(raw: Any) -> tuple[float, str | None] | None:
    """Parse ``"18cm"`` / ``"1.8 米"`` / ``"500"`` into ``(value, unit)``."""

    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    match = MEASUREMENT_RE.match(text)
    if not match:
        return None
    try:
        value = float(match.group("num"))
    except ValueError:
        return None
    unit = normalize_unit_token(match.group("unit"))
    return value, (unit or None)


def convert(value: float, from_unit: str, to_unit: str) -> float | None:
    """Convert between two units of the same family, else ``None``."""

    source = normalize_unit_token(from_unit)
    target = normalize_unit_token(to_unit)
    if source == target:
        return value
    family = UNIT_TO_FAMILY.get(source)
    if family is None or family != UNIT_TO_FAMILY.get(target):
        return None
    base_value = value * UNIT_FAMILIES[family][source]
    return base_value / UNIT_FAMILIES[family][target]


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- #
# Text heuristics vocabularies
# --------------------------------------------------------------------------- #

# Advertising-law sensitive superlatives and absolute claims.
BANNED_WORDS: list[str] = [
    "全网最低", "全国最低", "史上最低", "最低价", "最便宜", "最好用", "最强",
    "第一品牌", "销量第一", "绝对有效", "绝对安全", "绝对正品", "100%有效",
    "国家级", "世界级", "顶级品质", "顶级享受", "极品", "王牌",
    "包治百病", "无副作用", "永久", "特效", "根治", "独家秘方", "秒杀全网",
]

PLACEHOLDER_PATTERNS: list[str] = [
    "lorem ipsum", "待补充", "待填写", "暂无描述", "暂无简介", "测试文案",
    "todo", "tbd", "placeholder", "asdf", "xxx", "文案待定",
]

PROMO_NOISE_CHARS = "★☆✦✧🔥💥🎁⚡️①②③㊙️！!!~～～"

# Words that carry no discriminating power when comparing two titles.
MARKETING_NOISE: list[str] = [
    "官方", "正品", "旗舰店", "专营店", "专卖店", "包邮", "新款", "新品", "爆款",
    "网红", "同款", "促销", "特价", "清仓", "批发", "现货", "国行", "行货",
    "秒杀", "限时", "直营", "授权", "原装", "进口", "热卖", "热销", "加厚",
]

GENERIC_IMAGE_HINTS: list[str] = [
    "image", "img", "photo", "pic", "screenshot", "unnamed", "未命名", "微信图片",
    "default", "temp", "tmp", "dsc", "timg", "u=", "oss-process=image/resize",
]

# --------------------------------------------------------------------------- #
# Category vocabulary
# --------------------------------------------------------------------------- #


def _attr(
    key: str,
    label: str,
    dtype: str = "text",
    *,
    required: bool = True,
    unit: str | None = None,
    enum: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    hint: str = "",
) -> AttributeSpec:
    values: list[str] = []
    aliases: dict[str, str] = {}
    if enum:
        values = list(CANONICAL_ENUMS.get(enum, []))
        aliases = dict(ENUM_ALIASES.get(enum, {}))
    return AttributeSpec(
        key=key,
        label=label,
        dtype=dtype,
        required=required,
        unit=unit,
        enum_values=values,
        min_value=min_value,
        max_value=max_value,
        aliases=aliases,
        hint=hint,
    )


CATEGORIES: list[CategorySpec] = [
    CategorySpec(
        category_id="audio",
        name="音频设备",
        path="数码 / 音频设备",
        price_floor=39,
        price_ceiling=3999,
        keywords=["耳机", "蓝牙耳机", "音箱", "音频"],
        attributes=[
            _attr("color", "颜色", "enum", enum="color"),
            _attr("connectivity", "连接方式", "enum", enum="connectivity"),
            _attr("battery_hours", "续航", "dimension", unit="h", min_value=0.5, max_value=400),
            _attr("weight", "净重", "dimension", unit="g", min_value=3, max_value=4000),
            _attr("driver_size", "单元尺寸", "dimension", unit="mm", min_value=4, max_value=120),
            _attr("impedance", "阻抗", "number", unit="Ω", min_value=4, max_value=600),
            _attr("noise_cancelling", "主动降噪", "bool", required=False),
            _attr("waterproof", "防水等级", "enum", required=False, enum="waterproof"),
            _attr("warranty_months", "保修期", "number", required=False, unit="月", min_value=0, max_value=60),
        ],
    ),
    CategorySpec(
        category_id="kitchen",
        name="厨房小家电",
        path="家电 / 厨房电器",
        price_floor=59,
        price_ceiling=8999,
        keywords=["电饭煲", "榨汁机", "空气炸锅", "料理机", "养生壶"],
        attributes=[
            _attr("power_w", "额定功率", "number", unit="W", min_value=100, max_value=3500),
            _attr("capacity", "容量", "dimension", unit="L", min_value=0.2, max_value=30),
            _attr("voltage", "额定电压", "enum", enum="voltage"),
            _attr("material", "主要材质", "enum", enum="material"),
            _attr("weight", "净重", "dimension", unit="kg", min_value=0.1, max_value=40),
            _attr("dishwasher_safe", "可机洗", "bool", required=False),
            _attr("warranty_months", "保修期", "number", required=False, unit="月", min_value=0, max_value=60),
        ],
    ),
    CategorySpec(
        category_id="sportswear",
        name="运动服饰",
        path="服饰 / 运动服饰",
        price_floor=29,
        price_ceiling=2599,
        keywords=["运动T恤", "速干衣", "瑜伽裤", "运动裤", "冲锋衣"],
        attributes=[
            _attr("size", "尺码", "enum", enum="size"),
            _attr("color", "颜色", "enum", enum="color"),
            _attr("fabric", "面料", "enum", enum="fabric"),
            _attr("gender", "适用人群", "enum", enum="gender"),
            _attr("weight", "克重", "dimension", unit="g", min_value=40, max_value=2500),
            _attr("season", "适用季节", "enum", required=False, enum="season"),
            _attr("sport_type", "运动类型", "enum", required=False, enum="sport_type"),
        ],
    ),
    CategorySpec(
        category_id="skincare",
        name="美妆护肤",
        path="美妆 / 护肤",
        price_floor=19,
        price_ceiling=3999,
        keywords=["精华液", "面霜", "洁面", "爽肤水", "防晒"],
        attributes=[
            _attr("volume", "净含量", "dimension", unit="ml", min_value=1, max_value=2000),
            _attr("skin_type", "适用肤质", "enum", enum="skin_type"),
            _attr("shelf_life_months", "保质期", "number", unit="月", min_value=3, max_value=60),
            _attr("ingredients", "主要成分", "text", hint="至少 10 个字符"),
            _attr("origin", "产地", "enum", enum="origin"),
            _attr("spf", "防晒指数", "number", required=False, min_value=0, max_value=120),
            _attr("fragrance_free", "无香精", "bool", required=False),
        ],
    ),
    CategorySpec(
        category_id="mobile",
        name="手机配件",
        path="数码 / 手机配件",
        price_floor=9,
        price_ceiling=1999,
        keywords=["数据线", "充电器", "手机壳", "充电宝", "钢化膜"],
        attributes=[
            _attr("compatible_brand", "适配品牌", "enum", enum="compatible_brand"),
            _attr("material", "材质", "enum", enum="material"),
            _attr("length", "线材长度", "dimension", unit="cm", min_value=1, max_value=500),
            _attr("weight", "净重", "dimension", unit="g", min_value=2, max_value=3000),
            _attr("color", "颜色", "enum", enum="color"),
            _attr("fast_charge_w", "快充功率", "number", required=False, unit="W", min_value=0, max_value=300),
            _attr("warranty_months", "保修期", "number", required=False, unit="月", min_value=0, max_value=60),
        ],
    ),
    CategorySpec(
        category_id="outdoor",
        name="户外装备",
        path="运动户外 / 户外装备",
        price_floor=39,
        price_ceiling=6999,
        keywords=["登山包", "帐篷", "睡袋", "折叠椅", "保温杯"],
        attributes=[
            _attr("capacity", "容量", "dimension", unit="L", min_value=0.3, max_value=200),
            _attr("material", "材质", "enum", enum="material"),
            _attr("weight", "净重", "dimension", unit="g", min_value=50, max_value=12000),
            _attr("waterproof", "防水等级", "enum", enum="waterproof"),
            _attr("color", "颜色", "enum", enum="color"),
            _attr("foldable", "可折叠", "bool", required=False),
            _attr("warranty_months", "保修期", "number", required=False, unit="月", min_value=0, max_value=60),
        ],
    ),
]

CATEGORY_MAP: dict[str, CategorySpec] = {spec.category_id: spec for spec in CATEGORIES}


def category(category_id: str) -> CategorySpec | None:
    return CATEGORY_MAP.get((category_id or "").strip())


def categories_as_dicts() -> list[dict[str, Any]]:
    return [spec.to_dict() for spec in CATEGORIES]

