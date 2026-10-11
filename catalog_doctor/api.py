"""HTTP API.

Run with ``uvicorn catalog_doctor.api:app --reload``. The same process serves
the built single-page UI from ``frontend/dist`` when it exists.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .service import CatalogNotFound, CatalogService

service = CatalogService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the demo catalog on first boot so the UI has data immediately."""

    if service.result is None:
        service.load_demo()
    yield


class ScanRequest(BaseModel):
    dataset: str = Field(default="demo", description="demo 表示重新生成示例数据集")


class ApplyRequest(BaseModel):
    sku: str
    issue_ids: list[str] = Field(default_factory=list, alias="issueIds")

    model_config = {"populate_by_name": True}


class BulkApplyRequest(BaseModel):
    issue_ids: list[str] = Field(default_factory=list, alias="issueIds")

    model_config = {"populate_by_name": True}


class ResolveDuplicateRequest(BaseModel):
    cluster_id: str = Field(alias="clusterId")
    action: str = Field(default="merge", pattern="^(merge|distinct)$")
    keep_sku: str | None = Field(default=None, alias="keepSku")

    model_config = {"populate_by_name": True}


def create_app() -> FastAPI:
    app = FastAPI(
        title="Catalog Doctor API",
        version=__version__,
        description=(
            "商品数据质量治理引擎：类目规范校验、重复商品识别、可解释评分与一键修复。"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "dataset": service.result.dataset_name if service.result else None,
        }

    @app.get("/api/v1/meta")
    def meta() -> dict:
        return service.meta()

    @app.get("/api/v1/summary")
    def summary() -> dict:
        return service.summary()

    @app.get("/api/v1/products")
    def products(
        q: str = "",
        category: str = "",
        grade: str = "",
        severity: str = "",
        sort: str = "-issues",
        page: int = 1,
        size: int = Query(default=20, ge=1, le=200),
    ) -> dict:
        return service.products_page(
            query=q,
            category_id=category,
            grade=grade,
            severity=severity,
            sort=sort,
            page=page,
            size=size,
        )

    @app.get("/api/v1/products/{sku}")
    def product_detail(sku: str) -> dict:
        try:
            return service.product_detail(sku)
        except CatalogNotFound as error:
            raise HTTPException(status_code=404, detail=f"未找到 SKU {error.args[0]}") from error

    @app.get("/api/v1/issues")
    def issues(
        q: str = "",
        severity: str = "",
        dimension: str = "",
        category: str = "",
        auto_fixable: bool | None = Query(default=None, alias="autoFixable"),
        page: int = 1,
        size: int = Query(default=25, ge=1, le=200),
    ) -> dict:
        return service.issues_page(
            query=q,
            severity=severity,
            dimension=dimension,
            category_id=category,
            auto_fixable=auto_fixable,
            page=page,
            size=size,
        )

    @app.get("/api/v1/duplicates")
    def duplicates() -> dict:
        return service.duplicates_view()

    @app.post("/api/v1/duplicates/resolve")
    def resolve_duplicate(request: ResolveDuplicateRequest) -> dict:
        try:
            return service.resolve_duplicate(request.cluster_id, request.action, request.keep_sku)
        except CatalogNotFound as error:
            raise HTTPException(status_code=404, detail=f"未找到重复簇 {error.args[0]}") from error

    @app.get("/api/v1/repairs")
    def repairs() -> dict:
        return service.repairs_view()

    @app.post("/api/v1/repairs/apply")
    def apply_repairs(request: ApplyRequest) -> dict:
        try:
            return service.apply_repairs(request.sku, request.issue_ids)
        except CatalogNotFound as error:
            raise HTTPException(status_code=404, detail=f"未找到 SKU {error.args[0]}") from error

    @app.post("/api/v1/repairs/apply-bulk")
    def apply_bulk(request: BulkApplyRequest) -> dict:
        return service.apply_bulk(request.issue_ids)

    @app.get("/api/v1/eval")
    def evaluation() -> dict:
        return service.evaluation()

    @app.post("/api/v1/scan")
    def scan(request: ScanRequest) -> dict:
        if request.dataset == "demo":
            service.load_demo()
        else:
            service.scan()
        return service.summary()

    @app.post("/api/v1/upload")
    async def upload(file: Annotated[UploadFile, File()]) -> dict:
        raw = await file.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gb18030", errors="replace")
        try:
            service.load_csv(text, name=file.filename or "uploaded-catalog")
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return service.summary()

    @app.get("/api/v1/export.csv", response_class=PlainTextResponse)
    def export_csv() -> PlainTextResponse:
        return PlainTextResponse(
            service.export_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="catalog-clean.csv"'},
        )

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")

    return app


app = create_app()

