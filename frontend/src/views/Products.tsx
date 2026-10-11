import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { IssueDrawer } from "../components/IssueDrawer";
import type { Grade, Issue, Meta, Paged, ProductDetail, ProductRow } from "../types";
import { Card, Drawer, EmptyState, GradeBadge, ScoreRing, SeverityPill, SkeletonRows, formatNumber, percent } from "../ui";

const GRADES: (Grade | "")[] = ["", "A", "B", "C", "D", "E"];

const DIMENSION_LABELS: Record<string, string> = {
  completeness: "完整性",
  conformance: "规范性",
  accuracy: "准确性",
  consistency: "一致性",
  text: "文案质量",
  media: "媒体素材",
  pricing: "价格库存",
  seo: "搜索健壮性",
  duplication: "重复商品",
};

export function Products({
  meta,
  refreshKey,
  onDataChanged,
  push,
}: {
  meta: Meta | null;
  refreshKey: number;
  onDataChanged: () => void;
  push: (title: string, detail?: string, tone?: "success" | "error") => void;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [grade, setGrade] = useState<Grade | "">("");
  const [sort, setSort] = useState("issues");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paged<ProductRow> | null>(null);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const size = 20;

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .products({ q: query, category, grade, sort, page, size })
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch((error: Error) => push("加载商品列表失败", error.message, "error"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [query, category, grade, sort, page, refreshKey, push]);

  useEffect(() => {
    setPage(1);
  }, [query, category, grade, sort]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil((data?.total ?? 0) / size)), [data?.total, size]);

  async function openDetail(sku: string) {
    setDetailLoading(true);
    try {
      setDetail(await api.product(sku));
    } catch (error) {
      push("加载商品档案失败", (error as Error).message, "error");
    } finally {
      setDetailLoading(false);
    }
  }

  async function reloadDetail(sku: string) {
    setDetail(await api.product(sku));
    onDataChanged();
  }

  return (
    <>
      <Card
        title="商品目录"
        sub={data ? `${formatNumber(data.total)} 个 SKU` : "加载中"}
        bodyClass=""
        actions={
          <select className="select" value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="issues">按问题数（多→少）</option>
            <option value="score">按健康分（低→高）</option>
            <option value="completeness">按属性完整度</option>
            <option value="price">按价格</option>
          </select>
        }
      >
        <div className="toolbar">
          <div className="search" style={{ width: 240 }}>
            <Search size={14} />
            <input placeholder="搜索 SKU、标题、品牌" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <div className="chip-row">
            {GRADES.map((item) => (
              <button key={item || "all"} className={`chip ${grade === item ? "active" : ""}`} onClick={() => setGrade(item)}>
                {item === "" ? "全部等级" : `${item} 级`}
              </button>
            ))}
          </div>
          <span className="spacer" />
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
          <SkeletonRows rows={6} columns={6} />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="没有匹配的商品" hint="试着清空搜索或切换类目" />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 66 }}>健康分</th>
                  <th>商品</th>
                  <th style={{ width: 110 }}>类目</th>
                  <th style={{ width: 92 }}>价格</th>
                  <th style={{ width: 150 }}>属性完整度</th>
                  <th style={{ width: 150 }}>问题</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((product) => (
                  <tr key={product.sku} className="clickable" onClick={() => openDetail(product.sku)}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <GradeBadge grade={product.grade} />
                        <span className="num">{product.score.toFixed(0)}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cell-title">
                        <strong>{product.title}</strong>
                        <span>
                          <span className="mono">{product.sku}</span> · {product.brand || "无品牌"} · {product.supplier}
                        </span>
                      </div>
                    </td>
                    <td className="nowrap">{product.categoryName}</td>
                    <td className="num nowrap">
                      ¥{product.price ? product.price.toFixed(2) : "—"}
                    </td>
                    <td>
                      <div className="bar-track">
                        <i
                          style={{
                            width: `${product.completeness * 100}%`,
                            background: product.completeness >= 0.95 ? "#0e7c63" : "#b08200",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: 11, color: "var(--muted)" }}>{percent(product.completeness)}</span>
                    </td>
                    <td className="nowrap">
                      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                        {product.criticalCount > 0 && <SeverityPill severity="critical" label={`致命 ${product.criticalCount}`} />}
                        {product.majorCount > 0 && <SeverityPill severity="major" label={`严重 ${product.majorCount}`} />}
                        {product.issueCount === 0 && <span className="pill accent">无问题</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pager">
          <span>
            第 {data?.page ?? 1} / {totalPages} 页 · 共 {formatNumber(data?.total ?? 0)} 个 SKU
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

      {(detail || detailLoading) && (
        <Drawer
          title={detail?.title ?? "加载中…"}
          meta={
            detail && (
              <>
                <GradeBadge grade={detail.grade} />
                <span className="mono">{detail.sku}</span>
                <span>{detail.categoryName}</span>
                <span>{detail.brand || "无品牌"}</span>
              </>
            )
          }
          onClose={() => setDetail(null)}
          footer={
            detail && (
              <>
                <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
                  {detail.issueCount} 个问题 · {detail.autoFixableCount} 条可自动修复
                </span>
                <span className="spacer" />
                <button className="btn" onClick={() => window.open(api.exportUrl, "_blank", "noopener")}>
                  导出目录
                </button>
              </>
            )
          }
        >
          {detail ? (
            <>
              <div className="stat-strip">
                <div className="cell">
                  <span>健康分</span>
                  <strong>{detail.score.toFixed(1)}</strong>
                </div>
                <div className="cell">
                  <span>属性完整度</span>
                  <strong>{percent(detail.completeness)}</strong>
                </div>
                <div className="cell">
                  <span>问题总数</span>
                  <strong>{detail.issueCount}</strong>
                </div>
                <div className="cell">
                  <span>可自动修复</span>
                  <strong>{detail.autoFixableCount}</strong>
                </div>
              </div>

              {detail.duplicateCluster && (
                <div className="callout warn">
                  <span>
                    该商品与 <strong>{detail.duplicateCluster.skus.filter((sku) => sku !== detail.sku).join("、")}</strong> 高度相似
                    （{(detail.duplicateCluster.similarity * 100).toFixed(1)}%）：{detail.duplicateCluster.reason}
                  </span>
                </div>
              )}

              <div>
                <div className="section-title">
                  诊断问题 <span className="count">{detail.issues.length}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>
                  {detail.issues.length === 0 && <div className="callout">该商品未发现规则命中的问题，可以正常上架。</div>}
                  {detail.issues.map((issue) => (
                    <div className="issue-item" key={issue.id}>
                      <div className="body">
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <SeverityPill severity={issue.severity} />
                          <span className="mono" style={{ color: "var(--muted)" }}>
                            {issue.field}
                          </span>
                        </div>
                        <div className="msg">{issue.message}</div>
                        <div className="hint">{issue.suggestion}</div>
                      </div>
                      <button className="btn subtle" onClick={() => setSelectedIssue(issue)}>
                        处理
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="section-title">类目属性核对</div>
                <div className="attr-table" style={{ marginTop: 10 }}>
                  {detail.attributes.rows.map((row) => (
                    <div className="attr-row" key={row.key}>
                      <span className="k">
                        {row.label}
                        {row.required && <span style={{ color: "var(--critical)" }}> *</span>}
                      </span>
                      <span className={`v ${row.value ? "" : row.required ? "empty" : ""}`}>{row.value || "（空）"}</span>
                      <span className="flag">
                        {row.status === "ok" && "✓ 合规"}
                        {row.status === "issue" && "! 待修正"}
                        {row.status === "missing" && "缺少必填"}
                        {row.status === "optional" && "可选"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="section-title">多维评分</div>
                <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 10 }}>
                  <ScoreRing value={detail.score} size={88} stroke={9} caption="健康分" />
                  <div className="bars" style={{ flex: 1 }}>
                    {Object.entries(detail.scoreDetail?.dimensionScores ?? {}).map(([key, value]) => (
                      <div className="bar-row" key={key}>
                        <span className="name">{DIMENSION_LABELS[key] ?? key}</span>
                        <span className="bar-track">
                          <i style={{ width: `${value}%`, background: value >= 90 ? "#0e7c63" : "#c2620a" }} />
                        </span>
                        <span className="value">{value.toFixed(0)}</span>
                      </div>
                    ))}
                    {Object.keys(detail.scoreDetail?.dimensionScores ?? {}).length === 0 && (
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>该商品所有维度均无扣分</span>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <SkeletonRows rows={8} columns={3} />
          )}
        </Drawer>
      )}

      {selectedIssue && (
        <IssueDrawer
          issue={selectedIssue}
          onClose={() => setSelectedIssue(null)}
          onApplied={async (text) => {
            push(text.startsWith("修复失败") ? "修复未应用" : "已应用修复", text, text.startsWith("修复失败") ? "error" : "success");
            if (detail) await reloadDetail(detail.sku);
          }}
        />
      )}
    </>
  );
}

