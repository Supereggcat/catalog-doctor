import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { IssueDrawer } from "../components/IssueDrawer";
import type { Issue, Meta, Paged, Severity } from "../types";
import { Card, EmptyState, SeverityPill, SkeletonRows, formatNumber, percent } from "../ui";

const SEVERITIES: { key: Severity | ""; label: string }[] = [
  { key: "", label: "全部" },
  { key: "critical", label: "致命" },
  { key: "major", label: "严重" },
  { key: "minor", label: "轻微" },
  { key: "info", label: "提示" },
];

export function Issues({
  meta,
  refreshKey,
  externalQuery,
  onOpenProduct,
  onDataChanged,
  push,
}: {
  meta: Meta | null;
  refreshKey: number;
  externalQuery?: string;
  onOpenProduct: (sku: string) => void;
  onDataChanged: () => void;
  push: (title: string, detail?: string, tone?: "success" | "error") => void;
}) {
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [dimension, setDimension] = useState("");
  const [category, setCategory] = useState("");
  const [onlyFixable, setOnlyFixable] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paged<Issue> | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Issue | null>(null);
  const size = 25;

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .issues({
        q: query,
        severity,
        dimension,
        category,
        autoFixable: onlyFixable ? true : undefined,
        page,
        size,
      })
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch((error: Error) => push("加载问题列表失败", error.message, "error"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [query, severity, dimension, category, onlyFixable, page, refreshKey, push]);

  useEffect(() => {
    setPage(1);
  }, [query, severity, dimension, category, onlyFixable]);

  useEffect(() => {
    if (externalQuery) setQuery(externalQuery);
  }, [externalQuery]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((data?.total ?? 0) / size)),
    [data?.total, size],
  );

  return (
    <>
      <Card
        title="问题队列"
        sub={data ? `${formatNumber(data.total)} 条` : "加载中"}
        actions={
          <label className="switch">
            <input type="checkbox" checked={onlyFixable} onChange={(event) => setOnlyFixable(event.target.checked)} />
            <span className="track" />
            仅看可自动修复
          </label>
        }
        bodyClass=""
      >
        <div className="toolbar">
          <div className="search" style={{ width: 240 }}>
            <Search size={14} />
            <input
              placeholder="搜索 SKU、标题、规则码"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="chip-row">
            {SEVERITIES.map((item) => (
              <button
                key={item.key || "all"}
                className={`chip ${severity === item.key ? "active" : ""}`}
                onClick={() => setSeverity(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <select className="select" value={dimension} onChange={(event) => setDimension(event.target.value)}>
            <option value="">全部维度</option>
            {meta?.dimensions.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </select>
          <select className="select" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">全部类目</option>
            {meta?.categories.map((item) => (
              <option key={item.categoryId} value={item.categoryId}>
                {item.name}
              </option>
            ))}
          </select>
        </div>

        {loading && !data ? (
          <SkeletonRows rows={6} columns={5} />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="没有匹配的问题" hint="试着放宽筛选条件，或清除搜索关键词" />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 84 }}>级别</th>
                  <th style={{ width: 118 }}>SKU</th>
                  <th>问题描述</th>
                  <th style={{ width: 120 }}>维度</th>
                  <th style={{ width: 130 }}>字段</th>
                  <th style={{ width: 92 }}>置信度</th>
                  <th style={{ width: 104 }}>修复</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((issue) => (
                  <tr key={issue.id} className="clickable" onClick={() => setSelected(issue)}>
                    <td>
                      <SeverityPill severity={issue.severity} />
                    </td>
                    <td className="mono nowrap">{issue.sku}</td>
                    <td>
                      <div className="cell-title">
                        <strong>{issue.productTitle ?? issue.sku}</strong>
                        <span>{issue.message}</span>
                      </div>
                    </td>
                    <td className="nowrap">{issue.dimensionLabel}</td>
                    <td className="mono nowrap" style={{ color: "var(--muted)" }}>
                      {issue.field}
                    </td>
                    <td className="num">{percent(issue.confidence)}</td>
                    <td className="nowrap">
                      {issue.autoFixable ? <span className="pill accent">可自动修复</span> : <span className="pill outline">人工</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pager">
          <span>
            第 {data?.page ?? 1} / {totalPages} 页 · 共 {formatNumber(data?.total ?? 0)} 条
          </span>
          <div className="pages">
            <button className="btn" disabled={(data?.page ?? 1) <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
              上一页
            </button>
            <button
              className="btn"
              disabled={(data?.page ?? 1) >= totalPages}
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            >
              下一页
            </button>
          </div>
        </div>
      </Card>

      {selected && (
        <IssueDrawer
          issue={selected}
          onClose={() => setSelected(null)}
          onApplied={(detail) => {
            if (detail.startsWith("修复失败")) {
              push("修复未应用", detail, "error");
            } else {
              push("已应用修复", detail);
              onDataChanged();
            }
          }}
          onOpenProduct={(sku) => {
            setSelected(null);
            onOpenProduct(sku);
          }}
        />
      )}
    </>
  );
}

