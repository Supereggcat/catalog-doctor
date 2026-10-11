import { ArrowRight, Download, Wand2 } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { RepairsPayload } from "../types";
import { Card, EmptyState, SeverityPill, SkeletonRows, formatNumber, percent } from "../ui";

export function Repairs({
  refreshKey,
  onDataChanged,
  push,
}: {
  refreshKey: number;
  onDataChanged: () => void;
  push: (title: string, detail?: string, tone?: "success" | "error") => void;
}) {
  const [data, setData] = useState<RepairsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .repairs()
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch((error: Error) => push("加载修复方案失败", error.message, "error"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [refreshKey, push]);

  const grouped = useMemo(() => {
    const items = data?.items ?? [];
    const map = new Map<string, { name: string; items: typeof items }>();
    for (const item of items) {
      const existing = map.get(item.code);
      const name = data?.byCode.find((row) => row.code === item.code)?.name ?? item.code;
      if (existing) existing.items.push(item);
      else map.set(item.code, { name, items: [item] });
    }
    return [...map.entries()].sort((left, right) => right[1].items.length - left[1].items.length);
  }, [data]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleGroup(ids: string[], on: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  }

  async function applySelected() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const result = await api.applyBulk([...selected]);
      push(
        "批量修复完成",
        `已应用 ${result.appliedCount} 条修复，覆盖 ${result.skus.length} 个 SKU，平均健康分 ${result.beforeScore} → ${result.afterScore}`,
      );
      setSelected(new Set());
      onDataChanged();
    } catch (error) {
      push("批量修复失败", (error as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  const rows = data?.items ?? [];

  return (
    <>
      <div className="grid split-3">
        <div className="card kpi">
          <span className="label">可自动修复问题</span>
          <div className="value">
            <span className="num">{formatNumber(data?.total ?? 0)}</span>
            <small>条</small>
          </div>
          <div className="foot">覆盖 {new Set(rows.map((row) => row.sku)).size} 个 SKU</div>
        </div>
        <div className="card kpi">
          <span className="label">修复类型</span>
          <div className="value">
            <span className="num">{grouped.length}</span>
            <small>类</small>
          </div>
          <div className="foot">词表归一、单位换算、禁用词清理、SEO 补全</div>
        </div>
        <div className="card kpi">
          <span className="label">已应用修复</span>
          <div className="value">
            <span className="num">{formatNumber(data?.applied.length ?? 0)}</span>
            <small>条</small>
          </div>
          <div className="foot">应用后系统会自动重跑全量扫描</div>
        </div>
      </div>

      <Card
        title="修复方案"
        sub="按规则分组，可逐条勾选后批量应用"
        bodyClass=""
        actions={
          <button className="btn" onClick={() => window.open(api.exportUrl, "_blank", "noopener")}>
            <Download size={14} /> 导出清洗后 CSV
          </button>
        }
      >
        {loading && !data ? (
          <SkeletonRows rows={7} columns={4} />
        ) : rows.length === 0 ? (
          <EmptyState title="当前没有可自动修复的问题" hint="剩余问题需要人工确认，或目录已经清洗完成" />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th style={{ width: 38 }} />
                    <th style={{ width: 92 }}>级别</th>
                    <th style={{ width: 118 }}>SKU</th>
                    <th>变更内容</th>
                    <th style={{ width: 150 }}>字段</th>
                    <th style={{ width: 90 }}>置信度</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped.map(([code, group]) => {
                    const ids = group.items.map((item) => item.issueId);
                    const allSelected = ids.every((id) => selected.has(id));
                    return (
                      <Fragment key={code}>
                        <tr style={{ background: "var(--surface-soft)" }}>
                          <td>
                            <input
                              className="checkbox"
                              type="checkbox"
                              checked={allSelected}
                              onChange={(event) => toggleGroup(ids, event.target.checked)}
                            />
                          </td>
                          <td colSpan={5}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <strong style={{ fontSize: 12.5 }}>{group.name}</strong>
                              <span className="pill neutral mono">{code}</span>
                              <span style={{ color: "var(--muted)", fontSize: 11.5 }}>{group.items.length} 条</span>
                            </div>
                          </td>
                        </tr>
                        {group.items.slice(0, 40).map((item) => (
                          <tr key={item.issueId}>
                            <td>
                              <input
                                className="checkbox"
                                type="checkbox"
                                checked={selected.has(item.issueId)}
                                onChange={() => toggle(item.issueId)}
                              />
                            </td>
                            <td>
                              <SeverityPill severity={item.severity} />
                            </td>
                            <td className="mono nowrap">{item.sku}</td>
                            <td>
                              <div className="cell-title">
                                <strong>{item.productTitle || item.sku}</strong>
                                <span>{item.message}</span>
                              </div>
                              {item.before !== null && item.after !== null && (
                                <div className="diff">
                                  <span className="before">{String(item.before) || "（空）"}</span>
                                  <span className="arrow">
                                    <ArrowRight size={12} />
                                  </span>
                                  <span className="after">{String(item.after)}</span>
                                </div>
                              )}
                            </td>
                            <td className="mono nowrap" style={{ color: "var(--muted)" }}>
                              {item.field}
                            </td>
                            <td className="num">{percent(item.confidence)}</td>
                          </tr>
                        ))}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="sticky-bar">
              <span style={{ fontSize: 12.5 }}>
                已选 <strong className="num">{selected.size}</strong> 条
              </span>
              <span className="spacer" />
              <button className="btn" onClick={() => setSelected(new Set(rows.map((row) => row.issueId)))}>
                全选本页
              </button>
              <button className="btn" onClick={() => setSelected(new Set())}>
                清空
              </button>
              <button className="btn primary" disabled={selected.size === 0 || busy} onClick={applySelected}>
                <Wand2 size={14} />
                {busy ? "应用中…" : `应用所选 ${selected.size} 条修复`}
              </button>
            </div>
          </>
        )}
      </Card>

      {data && data.applied.length > 0 && (
        <Card title="修复审计日志" sub="最近 50 条变更记录" bodyClass="">
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 110 }}>SKU</th>
                  <th style={{ width: 200 }}>规则</th>
                  <th style={{ width: 140 }}>字段</th>
                  <th>变更</th>
                </tr>
              </thead>
              <tbody>
                {data.applied.map((item, index) => (
                  <tr key={`${item.issueId}-${index}`}>
                    <td className="mono nowrap">{item.issueId.split(":")[0]}</td>
                    <td className="mono nowrap" style={{ color: "var(--muted)" }}>
                      {item.code}
                    </td>
                    <td className="mono nowrap">{item.field}</td>
                    <td>
                      <div className="diff">
                        <span className="before">{String(item.before ?? "（空）") || "（空）"}</span>
                        <span className="arrow">
                          <ArrowRight size={12} />
                        </span>
                        <span className="after">{String(item.after)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

