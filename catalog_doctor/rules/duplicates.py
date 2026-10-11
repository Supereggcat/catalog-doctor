"""Near-duplicate detection over noisy merchandising text.

Exact keys catch only a fraction of duplicate listings: dropshippers reword the
title, reorder the selling points and append "官方正品". The matcher therefore
combines three signals - an exact barcode key, TF-IDF cosine similarity over
character shingles, and a penalty for conflicting model numbers or variant axes.
Everything runs on the standard library, so the engine works without an API key
or a vector database.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict

from ..models import DuplicateCluster, Issue, Product
from ..taxonomy import MARKETING_NOISE
from .context import RuleContext

SHINGLE_SIZE = 3
DEFAULT_THRESHOLD = 0.72

_PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
_DIGIT_GROUP_RE = re.compile(r"\d+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def fullwidth_to_halfwidth(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def normalize_for_match(text: str) -> str:
    text = fullwidth_to_halfwidth(text).lower()
    for noise in MARKETING_NOISE:
        text = text.replace(noise, "")
    text = _PUNCT_RE.sub("", text)
    return text


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    if not text:
        return set()
    if len(text) <= size:
        return {text}
    return {text[index : index + size] for index in range(len(text) - size + 1)}


def digit_signature(text: str) -> frozenset[str]:
    return frozenset(token for token in _DIGIT_GROUP_RE.findall(fullwidth_to_halfwidth(text)) if len(token) >= 2)


def longest_common_substrings(left: str, right: str, min_length: int = 4, limit: int = 4) -> list[str]:
    """Cheap LCS-substring extraction used only for human-readable evidence."""

    found: set[str] = set()
    index = 0
    while index < len(left):
        size = min_length
        best = ""
        while index + size <= len(left):
            chunk = left[index : index + size]
            if chunk in right:
                best = chunk
                size += 1
            else:
                break
        if best:
            found.add(best)
            index += len(best)
        else:
            index += 1
    ordered = sorted(found, key=len, reverse=True)
    return ordered[:limit]


def _tfidf_vectors(documents: list[set[str]]) -> list[dict[str, float]]:
    total = len(documents) or 1
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(document)
    vectors: list[dict[str, float]] = []
    for document in documents:
        vector: dict[str, float] = {}
        for token in document:
            tf = 1.0
            idf = math.log((1 + total) / (1 + document_frequency[token])) + 1.0
            vector[token] = tf * idf
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors.append({token: value / norm for token, value in vector.items()})
    return vectors


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(token, 0.0) for token, value in left.items())


def pair_similarity(left: Product, right: Product, left_vector, right_vector) -> tuple[float, dict]:
    base = cosine(left_vector, right_vector)
    left_text = normalize_for_match(left.title)
    right_text = normalize_for_match(right.title)
    left_digits = digit_signature(left.title)
    right_digits = digit_signature(right.title)
    penalty = 0.0
    reasons: list[str] = []
    if left_digits and right_digits and left_digits != right_digits:
        penalty += 0.30
        reasons.append("型号数字不同")
    for key in ("size", "color", "capacity", "volume", "length", "material"):
        left_value = left.attr(key).lower()
        right_value = right.attr(key).lower()
        if left_value and right_value and left_value != right_value:
            penalty += 0.12
            reasons.append(f"{key} 不同")
    if left.brand and right.brand and left.brand.lower() != right.brand.lower():
        penalty += 0.18
        reasons.append("品牌不同")
    similarity = max(0.0, base - penalty)
    evidence = longest_common_substrings(left_text, right_text)
    return similarity, {"reasons": reasons, "evidence": evidence, "base": base}


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, node: int) -> int:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def build_duplicate_clusters(
    products: list[Product], threshold: float = DEFAULT_THRESHOLD
) -> list[DuplicateCluster]:
    if len(products) < 2:
        return []
    normalized = [normalize_for_match(f"{product.brand} {product.title}") for product in products]
    documents = [shingles(text) for text in normalized]
    vectors = _tfidf_vectors(documents)

    candidates: set[tuple[int, int]] = set()
    inverted: dict[str, list[int]] = defaultdict(list)
    for index, document in enumerate(documents):
        for shingle in document:
            inverted[shingle].append(index)
    for holders in inverted.values():
        if len(holders) < 2 or len(holders) > 60:
            continue
        for position, left in enumerate(holders):
            for right in holders[position + 1 :]:
                candidates.add((left, right))
    barcode_index: dict[str, list[int]] = defaultdict(list)
    for index, product in enumerate(products):
        code = re.sub(r"\D", "", product.barcode or "")
        if code:
            barcode_index[code].append(index)
    for holders in barcode_index.values():
        if len(holders) < 2:
            continue
        for position, left in enumerate(holders):
            for right in holders[position + 1 :]:
                candidates.add((left, right))

    union_find = _UnionFind(len(products))
    pair_details: dict[tuple[int, int], dict] = {}
    for left, right in candidates:
        similarity, detail = pair_similarity(products[left], products[right], vectors[left], vectors[right])
        exact_barcode = re.sub(r"\D", "", products[left].barcode or "") == re.sub(
            r"\D", "", products[right].barcode or ""
        ) and bool(re.sub(r"\D", "", products[left].barcode or ""))
        if exact_barcode and similarity >= 0.35:
            similarity = max(similarity, 0.99)
            detail["reasons"] = [*detail["reasons"], "条码完全一致"]
            detail["barcode_match"] = True
        detail["similarity"] = similarity
        pair_details[(left, right)] = detail
        if similarity >= threshold:
            union_find.union(left, right)

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(products)):
        grouped[union_find.find(index)].append(index)

    clusters: list[DuplicateCluster] = []
    for members in grouped.values():
        if len(members) < 2:
            continue
        best = 0.0
        worst = 1.0
        reasons: list[str] = []
        evidence: list[str] = []
        for position, left in enumerate(members):
            for right in members[position + 1 :]:
                key = (left, right) if (left, right) in pair_details else (right, left)
                detail = pair_details.get(key, {})
                value = float(detail.get("similarity", 0.0))
                best = max(best, value)
                worst = min(worst, value)
                reasons.extend(detail.get("reasons", []))
                evidence.extend(detail.get("evidence", []))
        skus = [products[index].sku for index in members]
        clusters.append(
            DuplicateCluster(
                cluster_id=f"dup-{'-'.join(sorted(skus)[:2])}",
                skus=sorted(skus),
                similarity=round(best, 4),
                reason="、".join(dict.fromkeys(reasons)) or "标题高度相似",
                evidence=list(dict.fromkeys(evidence))[:5],
            )
        )
    clusters.sort(key=lambda cluster: (-cluster.similarity, cluster.cluster_id))
    return clusters


def rule_duplicate(ctx: RuleContext, product: Product) -> list[Issue]:
    cluster = ctx.duplicate_cluster(product.sku)
    if cluster is None:
        return []
    peers = [sku for sku in cluster.skus if sku != product.sku]
    severity = "major" if cluster.similarity >= 0.85 else "minor"
    return [
        Issue(
            code="duplication.near_duplicate",
            sku=product.sku,
            product_id=product.product_id,
            category_id=product.category_id,
            dimension="duplication",
            severity=severity,
            field="title",
            message=(
                f"与 {len(peers)} 个 SKU 高度相似（相似度 {cluster.similarity * 100:.1f}%）："
                f"{', '.join(peers[:3])}"
            ),
            evidence="、".join(cluster.evidence[:3]) or cluster.reason,
            suggestion="比对规格与供货商后合并为一个商品的多规格，或下架重复铺货",
            auto_fixable=False,
            confidence=min(0.99, 0.5 + cluster.similarity / 2),
            repair={"kind": "merge_duplicate", "field": "product", "before": product.sku, "after": peers[0]},
        )
    ]

