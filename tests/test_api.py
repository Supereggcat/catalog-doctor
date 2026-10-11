from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from catalog_doctor.api import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    payload = client.get("/api/v1/health").json()
    assert payload["status"] == "ok"


def test_meta_lists_categories_and_rules(client):
    payload = client.get("/api/v1/meta").json()
    assert len(payload["categories"]) == 6
    assert payload["ruleCount"] >= 30
    assert any(rule["code"] == "duplication.near_duplicate" for rule in payload["rules"])


def test_summary_contains_kpis(client):
    payload = client.get("/api/v1/summary").json()
    assert payload["productCount"] > 0
    assert payload["severityCounts"]["critical"] > 0
    assert payload["autoFixableCount"] > 0
    assert payload["scoreHistogram"]
    assert payload["categoryHealth"]


def test_products_pagination_and_filter(client):
    payload = client.get("/api/v1/products", params={"size": 5, "page": 1}).json()
    assert len(payload["items"]) == 5
    assert payload["total"] > 5
    filtered = client.get("/api/v1/products", params={"category": "audio", "size": 50}).json()
    assert all(item["categoryId"] == "audio" for item in filtered["items"])


def test_product_detail(client):
    sku = client.get("/api/v1/products", params={"size": 1}).json()["items"][0]["sku"]
    payload = client.get(f"/api/v1/products/{sku}").json()
    assert payload["sku"] == sku
    assert "attributes" in payload


def test_missing_product_returns_404(client):
    assert client.get("/api/v1/products/NOPE").status_code == 404


def test_issues_filter_by_severity(client):
    payload = client.get("/api/v1/issues", params={"severity": "critical", "size": 50}).json()
    assert payload["total"] > 0
    assert all(item["severity"] == "critical" for item in payload["items"])


def test_duplicates_endpoint_exposes_threshold(client):
    payload = client.get("/api/v1/duplicates").json()
    assert payload["total"] >= 30
    assert payload["threshold"] == 0.72
    assert payload["clusters"][0]["members"]


def test_repairs_plan_and_apply(client):
    plan = client.get("/api/v1/repairs").json()
    assert plan["total"] > 0
    item = plan["items"][0]
    response = client.post(
        "/api/v1/repairs/apply",
        json={"sku": item["sku"], "issueIds": [item["issueId"]]},
    ).json()
    assert response["appliedCount"] >= 1
    assert response["afterScore"] >= response["beforeScore"]


def test_eval_endpoint_reports_capability(client):
    payload = client.get("/api/v1/eval").json()
    assert payload["available"] is True
    assert payload["overall"]["f1"] >= 0.95
    assert payload["capability"]["uncoveredFamilies"]
    assert payload["stress"]["productCount"] == 40


def test_export_csv(client):
    response = client.get("/api/v1/export.csv")
    assert response.status_code == 200
    assert response.text.startswith("product_id,sku,title")


def test_upload_rejects_empty_catalog(client):
    response = client.post(
        "/api/v1/upload",
        files={"file": ("empty.csv", "title\n无 sku\n", "text/csv")},
    )
    assert response.status_code == 400


def test_scan_resets_demo(client):
    payload = client.post("/api/v1/scan", json={"dataset": "demo"}).json()
    assert payload["productCount"] == 532

