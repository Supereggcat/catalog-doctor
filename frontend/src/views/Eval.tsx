import { AlertTriangle, Beaker, CheckCircle2, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { MetricBar } from "../charts";
import type { Evaluation } from "../types";
import { Card, EmptyState, SkeletonRows, formatNumber, percent } from "../ui";

function metric(value: number | string | undefined, digits = 3): string {
  if (typeof value === "number") return value.toFixed(digits);
  if (typeof value === "string") return value;
  return "—";
}

const REPRODUCE = [
  "# 单次评测",
  "python -m catalog_doctor.cli scan",
  "",
  "# 多随机种子稳定性（含干扰集误报）",
  "python -m catalog_doctor.cli benchmark --seeds 5",
  "",
  "# 运行测试",
  "python -m pytest -q",
].join("\n");

export function Eval({
  refreshKey,
  push,
}: {
  refreshKey: number;
  push: (title: string, detail?: string, tone?: "success" | "error") => void;
}) {
  const [data, setData] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .evaluation()
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch((error: Error) => push("加载评测报告失败", error.message, "error"))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [refreshKey, push]);

  if (loading && !data) {
    return (
      <Card title="评测报告" bodyClass="">
        <SkeletonRows rows={8} columns={5} />
      </Card>
    );
  }

  if (!data?.available) {
    return (
      <Card title="评测报告" bodyClass="">
        <EmptyState
          title="当前数据集没有人工标注"
          hint={data?.reason ?? "上传带标注的数据集后可运行 precision / recall 评估。"}
          icon={<Beaker size={20} />}
        />
      </Card>
    );
  }

  const overall = data.overall ?? {};
  const duplicates = data.duplicates ?? {};
  const capability = data.capability;
  const stress = data.stress;
  const baseline = data.baseline ?? {};
  const autoFix = data.autoFix ?? {};
  const perCode = [...(data.perCode ?? [])].sort((left, right) => {
    if (right.support !== left.support) return right.support - left.support;
    return left.code.localeCompare(right.code);
  });

  return (
    <>
      <div className="grid kpi">
        <div className="card kpi">
          <span className="label">缺陷检出 F1</span>
          <div className="value">
            <span className="num">{metric(overall.f1)}</span>
          </div>
          <div className="foot">
            Precision {metric(overall.precision)} · Recall {metric(overall.recall)}
          </div>
          <MetricBar value={Number(overall.f1 ?? 0)} />
        </div>
        <div className="card kpi">
          <span className="label">重复商品检测 F1</span>
          <div className="value">
            <span className="num">{metric(duplicates.f1)}</span>
          </div>
          <div className="foot">
            TP {duplicates.truePositives ?? 0} · FP {duplicates.falsePositives ?? 0} · FN {duplicates.falseNegatives ?? 0}
          </div>
          <MetricBar value={Number(duplicates.f1 ?? 0)} />
        </div>
        <div className="card kpi">
          <span className="label">相似干扰集误报</span>
          <div className="value">
            <span className="num">{stress?.falsePositiveSkus ?? 0}</span>
            <small>/ {stress?.productCount ?? 0} 个 SKU</small>
          </div>
          <div className="foot">{stress?.name ?? "同品牌不同型号干扰集"}</div>
          <MetricBar value={stress?.cleanRate ?? 0} />
        </div>
        <div className="card kpi">
          <span className="label">自动修复覆盖率</span>
          <div className="value">
            <span className="num">{percent(autoFix.coverage ?? 0)}</span>
          </div>
          <div className="foot">
            {formatNumber(autoFix.autoFixableIssues ?? 0)} / {formatNumber(autoFix.totalIssues ?? 0)} 条问题可一键修复
          </div>
          <MetricBar value={autoFix.coverage ?? 0} />
        </div>
      </div>

      <div className="grid split-2">
        <Card title="评测方法" sub="可复现、可证伪">
          <div className="callout warn">
            <AlertTriangle size={15} />
            <div>
              本数据集由同一套类目规范生成，缺陷为人工注入并逐条打标，因此指标衡量的是
              <strong>「规则是否按预期命中」</strong>，属于能力上界而非线上真实准确率。真实召回请在自有数据上抽样标注后复测。
            </div>
          </div>
          <div className="stat-strip" style={{ marginTop: 12 }}>
            <div className="cell">
              <span>标注 SKU</span>
              <strong>{formatNumber(data.dataset?.labeledSkus ?? 0)}</strong>
            </div>
            <div className="cell">
              <span>标注缺陷</span>
              <strong>{formatNumber(data.dataset?.labeledDefects ?? 0)}</strong>
            </div>
            <div className="cell">
              <span>标注重复簇</span>
              <strong>{formatNumber(data.dataset?.duplicateClusters ?? 0)}</strong>
            </div>
            <div className="cell">
              <span>规则总数</span>
              <strong>{formatNumber(capability?.ruleFamilies ?? 0)}</strong>
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="section-title">
              <Terminal size={14} /> 复现命令
            </div>
            <pre
              className="mono"
              style={{
                margin: "8px 0 0",
                padding: "12px 14px",
                borderRadius: 8,
                background: "#131817",
                color: "#d7e3de",
                overflowX: "auto",
                lineHeight: 1.7,
              }}
            >
              {REPRODUCE}
            </pre>
          </div>
        </Card>

        <Card
          title="能力边界"
          sub={`已实现 ${capability?.implementedFamilies ?? 0} / ${capability?.labeledFamilies ?? 0} 个标注缺陷族`}
        >
          <div className="bars">
            <div className="bar-row">
              <span className="name">已实现规则</span>
              <span className="bar-track">
                <i
                  style={{
                    width: `${((capability?.implementedFamilies ?? 0) / Math.max(capability?.labeledFamilies ?? 1, 1)) * 100}%`,
                    background: "#0e7c63",
                  }}
                />
              </span>
              <span className="value">{capability?.implementedFamilies ?? 0}</span>
            </div>
            <div className="bar-row">
              <span className="name">未覆盖缺陷</span>
              <span className="bar-track">
                <i
                  style={{
                    width: `${((capability?.uncoveredFamilies.length ?? 0) / Math.max(capability?.labeledFamilies ?? 1, 1)) * 100}%`,
                    background: "#c2620a",
                  }}
                />
              </span>
              <span className="value">{capability?.uncoveredFamilies.length ?? 0}</span>
            </div>
          </div>
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            {(capability?.uncoveredFamilies ?? []).map((code) => (
              <div className="issue-item" key={code}>
                <div className="body">
                  <div className="mono" style={{ fontSize: 12 }}>
                    {code}
                  </div>
                  <div className="hint">
                    需要视觉模型或跨字段语义比对；当前版本显式标注为能力缺口，不参与上面的精度统计。
                  </div>
                </div>
                <span className="pill minor">未实现</span>
              </div>
            ))}
          </div>
          <p style={{ margin: "12px 0 0", fontSize: 11.5, color: "var(--muted)" }}>
            共 {capability?.uncoveredDefects ?? 0} 条缺陷落在未实现族中，召回率记为 0，避免用「已实现规则恰好覆盖的样本」自证。
          </p>
        </Card>
      </div>

      <div className="grid split-2">
        <Card title="对比朴素基线" sub="规则引擎 vs. 仅校验必填字段">
          <div className="bars">
            <div className="bar-row">
              <span className="name">Catalog Doctor</span>
              <span className="bar-track">
                <i style={{ width: `${Number(overall.recall ?? 0) * 100}%`, background: "#0e7c63" }} />
              </span>
              <span className="value">{percent(Number(overall.recall ?? 0))}</span>
            </div>
            <div className="bar-row">
              <span className="name">朴素基线</span>
              <span className="bar-track">
                <i style={{ width: `${Number(baseline.recall ?? 0) * 100}%`, background: "#c2620a" }} />
              </span>
              <span className="value">{percent(Number(baseline.recall ?? 0), 1)}</span>
            </div>
          </div>
          <div className="stat-strip" style={{ marginTop: 14 }}>
            <div className="cell">
              <span>基线覆盖规则族</span>
              <strong>
                {baseline.coveredCodeCount ?? 0} / {baseline.totalCodeCount ?? 0}
              </strong>
            </div>
            <div className="cell">
              <span>基线命中</span>
              <strong>{formatNumber(Number(baseline.detected ?? 0))}</strong>
            </div>
            <div className="cell">
              <span>基线误报</span>
              <strong>{formatNumber(Number(baseline.falsePositives ?? 0))}</strong>
            </div>
            <div className="cell">
              <span>缺陷族覆盖</span>
              <strong>{percent(Number(baseline.codeCoverage ?? 0), 1)}</strong>
            </div>
          </div>
          <p style={{ margin: "12px 0 0", fontSize: 11.5, color: "var(--muted)" }}>
            表格型人工巡检通常只能核对必填字段，这正是召回率被压在个位数的主要原因。
          </p>
        </Card>

        <Card title="规则族评测" sub="per-rule precision / recall">
          <div className="callout">
            <CheckCircle2 size={15} />
            <div>
              共 {perCode.length} 条规则参与评测，其中 {perCode.filter((row) => row.support > 0).length} 条在本数据集有正样本，
              {perCode.filter((row) => row.support === 0).length} 条未出现（标为「本次未覆盖」）。
            </div>
          </div>
          <div className="stat-strip" style={{ marginTop: 12 }}>
            <div className="cell">
              <span>micro Precision</span>
              <strong>{metric(overall.precision)}</strong>
            </div>
            <div className="cell">
              <span>micro Recall</span>
              <strong>{metric(overall.recall)}</strong>
            </div>
            <div className="cell">
              <span>macro F1</span>
              <strong>{metric(overall.macroF1)}</strong>
            </div>
            <div className="cell">
              <span>误报数</span>
              <strong>{formatNumber(Number(overall.falsePositives ?? 0))}</strong>
            </div>
          </div>
        </Card>
      </div>

      <Card title="逐规则指标" sub="按标注样本数排序" bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th style={{ width: 250 }}>规则</th>
                <th style={{ width: 70 }}>支持</th>
                <th style={{ width: 70 }}>预测</th>
                <th style={{ width: 56 }}>TP</th>
                <th style={{ width: 56 }}>FP</th>
                <th style={{ width: 56 }}>FN</th>
                <th style={{ width: 170 }}>Precision</th>
                <th style={{ width: 170 }}>Recall</th>
                <th style={{ width: 90 }}>F1</th>
              </tr>
            </thead>
            <tbody>
              {perCode.map((row) => (
                <tr key={row.code}>
                  <td>
                    <div className="cell-title">
                      <strong>{row.name}</strong>
                      <span className="mono">{row.code}</span>
                    </div>
                  </td>
                  <td className="num">{row.support}</td>
                  <td className="num">{row.predicted}</td>
                  <td className="num">{row.truePositives}</td>
                  <td className="num" style={{ color: row.falsePositives ? "var(--critical)" : "var(--muted)" }}>
                    {row.falsePositives}
                  </td>
                  <td className="num" style={{ color: row.falseNegatives ? "var(--critical)" : "var(--muted)" }}>
                    {row.falseNegatives}
                  </td>
                  <td>{row.support === 0 ? <span className="pill outline">本次未覆盖</span> : <MetricBar value={row.precision} />}</td>
                  <td>{row.support === 0 ? <span className="pill outline">—</span> : <MetricBar value={row.recall} />}</td>
                  <td className="num">{row.support === 0 ? "—" : row.f1.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

