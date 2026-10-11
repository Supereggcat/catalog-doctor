"""Dataset-level context shared by every rule invocation."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from ..models import CategorySpec, DuplicateCluster, Product
from ..taxonomy import CATEGORY_MAP


@dataclass
class RuleContext:
    products: list[Product]
    dataset_name: str = "demo"
    duplicates: list[DuplicateCluster] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._price_index: dict[str, list[float]] = {}
        self._image_index: dict[str, list[str]] = {}
        self._duplicate_index: dict[str, DuplicateCluster] = {}
        self._median_cache: dict[str, float] = {}
        self._mad_cache: dict[str, float] = {}
        self._log_stats_cache: dict[str, tuple[float, float] | None] = {}
        for product in self.products:
            if product.price and product.price > 0:
                self._price_index.setdefault(product.category_id, []).append(product.price)
            for url in product.images:
                self._image_index.setdefault(url.strip(), []).append(product.sku)
        for cluster in self.duplicates:
            for sku in cluster.skus:
                self._duplicate_index[sku] = cluster

    # -- category helpers -------------------------------------------------- #
    def category(self, category_id: str) -> CategorySpec | None:
        return CATEGORY_MAP.get((category_id or "").strip())

    def category_prices(self, category_id: str) -> list[float]:
        return self._price_index.get(category_id, [])

    def category_median(self, category_id: str) -> float:
        if category_id not in self._median_cache:
            prices = self.category_prices(category_id)
            self._median_cache[category_id] = float(statistics.median(prices)) if prices else 0.0
        return self._median_cache[category_id]

    def category_mad(self, category_id: str) -> float:
        if category_id not in self._mad_cache:
            prices = self.category_prices(category_id)
            if len(prices) < 3:
                self._mad_cache[category_id] = 0.0
            else:
                median = statistics.median(prices)
                self._mad_cache[category_id] = float(
                    statistics.median([abs(value - median) for value in prices])
                )
        return self._mad_cache[category_id]

    def category_log_stats(self, category_id: str) -> tuple[float, float] | None:
        """Return ``(median, MAD)`` of ``ln(price)`` when enough samples exist."""

        if category_id not in self._log_stats_cache:
            prices = [value for value in self.category_prices(category_id) if value > 0]
            if len(prices) < 20:
                self._log_stats_cache[category_id] = None
            else:
                logs = [math.log(value) for value in prices]
                median = statistics.median(logs)
                mad = statistics.median([abs(value - median) for value in logs])
                self._log_stats_cache[category_id] = (median, mad) if mad else None
        return self._log_stats_cache[category_id]

    # -- media / duplicate helpers ----------------------------------------- #
    def image_users(self, url: str) -> list[str]:
        return self._image_index.get((url or "").strip(), [])

    def duplicate_cluster(self, sku: str) -> DuplicateCluster | None:
        return self._duplicate_index.get(sku)

    def peers(self, sku: str) -> list[str]:
        cluster = self.duplicate_cluster(sku)
        if cluster is None:
            return []
        return [peer for peer in cluster.skus if peer != sku]

