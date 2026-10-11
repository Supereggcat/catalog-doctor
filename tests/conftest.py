from __future__ import annotations

import pytest

from catalog_doctor.ingest import ean13
from catalog_doctor.models import Product, Variant
from catalog_doctor.taxonomy import CATEGORY_MAP


def _midpoint(attr) -> str:
    low = attr.min_value if attr.min_value is not None else 1
    high = attr.max_value if attr.max_value is not None else low * 2
    value = (low + high) / 2
    text = str(int(value)) if float(value).is_integer() else f"{value:g}"
    return f"{text}{attr.unit or ''}"


def build_clean_product(category_id: str = "audio", **overrides) -> Product:
    spec = CATEGORY_MAP[category_id]
    attributes: dict[str, str] = {}
    for attr in spec.attributes:
        if attr.dtype == "enum":
            attributes[attr.key] = attr.enum_values[0]
        elif attr.dtype == "bool":
            attributes[attr.key] = "是"
        elif attr.dtype == "dimension":
            attributes[attr.key] = _midpoint(attr)
        elif attr.dtype == "number":
            attributes[attr.key] = _midpoint(attr)
        else:
            attributes[attr.key] = "主要成分说明文本，长度超过十个字符"
    attributes["image_alt"] = "商品主图"
    sku = overrides.pop("sku", "SKU-0001")
    product = Product(
        product_id="P0001",
        sku=sku,
        title="韶音 AUD100 蓝牙耳机 24小时续航 黑色 官方正品",
        brand="韶音",
        category_id=category_id,
        price=(spec.price_floor + spec.price_ceiling) / 4,
        currency="CNY",
        stock=25,
        barcode=ean13("690123456789"),
        images=[
            f"https://cdn.example.com/{sku}-main.jpg",
            f"https://cdn.example.com/{sku}-detail.jpg",
            f"https://cdn.example.com/{sku}-scene.jpg",
        ],
        description=(
            "商品采用轻量化结构设计，出厂前完成全项质检，适用于日常通勤与户外场景。"
            "包装内含说明书与保修卡，支持七天无理由退换。"
        ),
        attributes=attributes,
        variants=[Variant(variant_id=f"{sku}-01", axes={"color": attributes.get("color", "黑")}, price=10.0, stock=5)],
        supplier="测试供应商",
        seo_keywords="韶音,蓝牙耳机,AUD100,降噪",
    )
    product.variants[0].price = product.price
    for key, value in overrides.items():
        setattr(product, key, value)
    return product


@pytest.fixture
def make_product():
    return build_clean_product


@pytest.fixture(scope="session")
def demo_scan():
    from catalog_doctor.service import CatalogService

    service = CatalogService()
    return service.load_demo()

