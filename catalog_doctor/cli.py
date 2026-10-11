"""Command line entry point: ``catalog-doctor scan`` / ``serve`` / ``export``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .eval import evaluate
from .ingest import generate_demo_dataset, to_csv
from .rules import RuleContext, build_duplicate_clusters, evaluate_products
from .scoring import score_products


def _scan_demo(seed: int) -> dict:
    products, labels, duplicate_labels, distractors = generate_demo_dataset(seed=seed)
    duplicates = build_duplicate_clusters(products)
    ctx = RuleContext(products, "demo-catalog", duplicates)
    issues = evaluate_products(ctx)
    scores = score_products(products, issues)
    from datetime import datetime, timezone

    from .models import ScanResult

    result = ScanResult(
        products=products,
        issues=issues,
        duplicates=duplicates,
        scores=scores,
        categories=[],
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        dataset_name="demo-catalog",
        labels=labels,
        duplicate_labels=duplicate_labels,
        distractors=distractors,
    )
    report = evaluate(result)
    return {"summary": result.to_summary(), "evaluation": report}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalog-doctor", description="商品数据质量治理引擎")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="在示例数据集上运行扫描并输出评测报告")
    scan_parser.add_argument("--seed", type=int, default=20261011)
    scan_parser.add_argument("--json", action="store_true", help="输出完整 JSON")

    serve_parser = sub.add_parser("serve", help="启动 API 与前端")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8010)
    serve_parser.add_argument("--reload", action="store_true")

    export_parser = sub.add_parser("export", help="导出示例数据集 CSV")
    export_parser.add_argument("--out", default="examples/dirty_catalog.csv")
    export_parser.add_argument("--seed", type=int, default=20261011)

    bench_parser = sub.add_parser("benchmark", help="在多个随机种子上重复评测，输出稳定性")
    bench_parser.add_argument("--seeds", type=int, default=5)
    bench_parser.add_argument("--start-seed", type=int, default=20261011)

    args = parser.parse_args(argv)
    if args.command == "scan":
        payload = _scan_demo(args.seed)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            summary = payload["summary"]
            report = payload["evaluation"]
            print(f"商品数：{summary['productCount']}")
            print(f"问题数：{summary['issueCount']}")
            print(f"平均分：{summary['averageScore']}")
            print(f"重复簇：{summary['duplicateClusterCount']}")
            print(
                "缺陷检出 micro P/R/F1："
                f"{report['overall']['precision']:.3f} / "
                f"{report['overall']['recall']:.3f} / {report['overall']['f1']:.3f}"
            )
            print(
                "重复商品检测 P/R/F1："
                f"{report['duplicates']['precision']:.3f} / "
                f"{report['duplicates']['recall']:.3f} / {report['duplicates']['f1']:.3f}"
            )
        return 0
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "catalog_doctor.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0
    if args.command == "export":
        products, _, _, _ = generate_demo_dataset(seed=args.seed)
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_csv(products), encoding="utf-8")
        print(f"已写入 {target}（{len(products)} 行）")
        return 0
    if args.command == "benchmark":
        rows = []
        for offset in range(args.seeds):
            seed = args.start_seed + offset
            payload = _scan_demo(seed)
            overall = payload["evaluation"]["overall"]
            duplicates = payload["evaluation"]["duplicates"]
            stress = payload["evaluation"]["stress"]
            rows.append((seed, overall, duplicates, stress))
            print(
                f"seed={seed}  缺陷 P={overall['precision']:.3f} R={overall['recall']:.3f} "
                f"F1={overall['f1']:.3f} | 重复 P={duplicates['precision']:.3f} "
                f"R={duplicates['recall']:.3f} F1={duplicates['f1']:.3f} | "
                f"干扰集误报={stress['falsePositiveSkus']}"
            )
        mean = lambda key: sum(row[1][key] for row in rows) / len(rows)  # noqa: E731
        mean_dup = lambda key: sum(row[2][key] for row in rows) / len(rows)  # noqa: E731
        print(
            f"平均：缺陷 P={mean('precision'):.3f} R={mean('recall'):.3f} F1={mean('f1'):.3f} | "
            f"重复 F1={mean_dup('f1'):.3f} | 干扰集误报均值="
            f"{sum(row[3]['falsePositiveSkus'] for row in rows) / len(rows):.2f}"
        )
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

