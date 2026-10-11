import { Check, GitCompare, Merge, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DuplicatesPayload, ProductRow } from "../types";
import { Card, EmptyState, GradeBadge, SkeletonRows, formatNumber, percent } from "../ui";

interface DuplicateMember extends ProductRow {
  supplier: string;
}

const COMPARE_FIELDS: { key: string; label: string; get: (member: DuplicateMember) => string }[] = [
  { key: "sku", label: "SKU", get: (member) => member.sku },
  { key: "title", label: "标题", get: (member) => member.title },
  { key: "brand", label: "品牌", get: (member) => member.brand || "—" },
  { key: "categoryName", label: "类目", get: (member) => member.categoryName },
  { key: "price", label: "售价", get: (member) => (member.price ? `¥${member.price.toFixed(2)}` : "—") },
  { key: "barcode", label: "条码", get: (member) => member.barcode || "—" },
  { key: "supplier", label: "供应商", get: (member) => member.supplier || "—" },
  { key: "score", label: "健康分", get: (member) => member.score.toFixed(1) },
  { key: "cover", label: "主图", get: (member) => member.images[0] ?? "—" },
];

export function Duplicates({
  refreshKey,
  onDataChanged,
  push,
}: {
  refreshKey: number;
  onDataChanged: () => void;
  push: (title: string, detail?: string, tone?: "success" | "error") => void;
}) {
  const [data, setData] = useState<DuplicatesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .duplicates()
      .then((payload) => {
        if (!alive) return;
        setData(payload);
        setSelectedId((current) =>
          current && payload.clusters.some((cluster) => cluster.clusterId === current)
            ? current
            : payload.clusters[0]?.clusterId ?? null,
        );
      })
      .catch((error: Error) => push("加载重复商品失败", error.message, "error"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [refreshKey, push]);

  const cluster = data?.clusters.find((item) => item.clusterId === selectedId) ?? data?.clusters[0];
  const members = (cluster?.members ?? []) as DuplicateMember[];

  async function resolve(action: "merge" | "distinct", keepSku?: string) {
    if (!cluster) return;
    setBusy(true);
    try {
      await api.resolveDuplicate(cluster.clusterId, action, keepSku);
      push(
        action === "merge" ? "已记录合并决策" : "已标记为不同商品",
        action === "merge"
          ? `保留 ${keepSku}，其余 ${cluster.skus.length - 1} 个 SKU 进入合并流程`
          : `该组不再计入重复商品告警，可在审计日志中回溯`,
      );
      onDataChanged();
    } catch (error) {
      push("操作失败", (error as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dup-layout">
      <Card
        title="重复商品簇"
        sub={data ? `${formatNumber(data.total)} 组 · 阈值 ${data.threshold}` : "加载中"}
        bodyClass="dup-list"
      >
        {loading && !data ? (
          <SkeletonRows rows={6} columns={2} />
        ) : data && data.clusters.length === 0 ? (
          <EmptyState title="没有发现重复商品" hint="当前目录没有超过相似度阈值的商品组合" />
        ) : (
          data?.clusters.map((item) => (
            <button
              key={item.clusterId}
              className={`dup-item ${item.clusterId === cluster?.clusterId ? "active" : ""}`}
              onClick={() => setSelectedId(item.clusterId)}
            >
              <div className="top">
                <Merge size={13} />
                {item.skus.length} 个 SKU
                <span className="sim">{percent(item.similarity, 1)}</span>
              </div>
              <div className="skus">{item.skus.join(" · ")}</div>
            </button>
          ))
        )}
      </Card>

      <Card
        title={cluster ? `比对视图 · ${cluster.clusterId}` : "比对视图"}
        sub={cluster?.reason}
        bodyClass="card-body"
        actions={
          cluster && (
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" disabled={busy} onClick={() => resolve("merge", cluster.skus[0])}>
                <Check size={14} /> 保留 {cluster.skus[0]}
              </button>
              <button className="btn" disabled={busy} onClick={() => resolve("merge", cluster.skus[1])}>
                <Check size={14} /> 保留 {cluster.skus[1]}
              </button>
              <button className="btn danger" disabled={busy} onClick={() => resolve("distinct")}>
                标记为不同商品
              </button>
            </div>
          )
        }
      >
        {!cluster ? (
          <EmptyState title="选择左侧的重复簇查看比对" />
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
              <span className="pill accent">
                <GitCompare size={12} /> 相似度 {percent(cluster.similarity, 1)}
              </span>
              {cluster.matchesGroundTruth ? (
                <span className="pill accent">
                  <ShieldCheck size={12} /> 与人工标注一致
                </span>
              ) : (
                <span className="pill outline">人工复核建议</span>
              )}
              {cluster.evidence.map((item) => (
                <span className="pill neutral mono" key={item}>
                  {item}
                </span>
              ))}
            </div>

            <div className="compare">
              <div className="head">字段</div>
              {members.map((member) => (
                <div className="head" key={member.sku}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <GradeBadge grade={member.grade} />
                    <span className="mono">{member.sku}</span>
                  </div>
                </div>
              ))}
              {COMPARE_FIELDS.map((field) => {
                const values = members.map((member) => field.get(member));
                const differs = new Set(values).size > 1;
                return (
                  <div key={field.key} style={{ display: "contents" }}>
                    <div className="field">{field.label}</div>
                    {values.map((value, index) => (
                      <div key={`${field.key}-${index}`} className={differs ? "differ" : ""} title={value}>
                        {value}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            <div className="callout neutral" style={{ marginTop: 14 }}>
              <div>
                合并动作不会自动删除数据：系统会记录保留的主商品与其他 SKU 的映射关系，便于后续把库存与订单归并到主 SKU，
                同时把重复告警从队列中移除。
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

