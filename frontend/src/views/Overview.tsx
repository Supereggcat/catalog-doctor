import { AlertTriangle, ArrowRight, Layers, Sparkles, Wand2 } from "lucide-react";
import { GradeStack, Histogram, SeverityBars, Sparkline } from "../charts";
import type { Grade, Issue, Summary } from "../types";
import { AnimatedNumber, Card, ScoreRing, SeverityPill, formatNumber, relativeTime } from "../ui";

function gradeBandOf(bucket: string): Grade {
  const start = Number(bucket.split("-")[0]);
  if (start >= 90) return "A";
  if (start >= 80) return "B";
  if (start >= 70) return "C";
  if (start >= 60) return "D";
  return "E";
}

export function Overview({
  summary,
  onOpenIssue,
  onOpenProduct,
  onNavigate,
}: {
  summary: Summary;
  onOpenIssue: (issue: Issue) => void;
  onOpenProduct: (sku: string) => void;
  onNavigate: (view: "issues" | "repairs" | "eval") => void;
}) {
  const gradeBands = Object.fromEntries(
    Object.keys(summary.scoreHistogram).map((bucket) => [bucket, gradeBandOf(bucket)]),
  ) as Record<string, Grade>;
  const history = summary.history ?? [];
  const latest = history[history.length - 1];
  const previous = history.length > 1 ? history[history.length - 2] : undefined;
  const delta = latest && previous ? latest.averageScore - previous.averageScore : 0;

  return (
    <>
      <div className="grid kpi">
        <div className="card kpi">
          <span className="label">
            <Sparkles size={13} /> 目录平均健康分
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <ScoreRing value={summary.averageScore} size={72} stroke={8} />
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="pill accent">
                {summary.gradeDistribution.A} 个 A 级
              </span>
              <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
                最低 {Math.min(...(history.map((item) => item.averageScore) || [summary.averageScore])).toFixed(1)} 分
              </span>
            </div>
          </div>
          <div className="foot">
            <span>{history.length} 次扫描记录</span>
            {delta !== 0 && (
              <span style={{ color: delta > 0 ? "var(--accent)" : "var(--critical)" }}>
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)} 分
              </span>
            )}
          </div>
        </div>

        <div className="card kpi">
          <span className="label">
            <Layers size={13} /> 在售 SKU
          </span>
          <div className="value">
            <AnimatedNumber value={summary.productCount} />
            <small>个商品</small>
          </div>
          <div className="foot">
            <span>重复商品簇 {summary.duplicateClusterCount} 组</span>
          </div>
          <div className="track">
            <i style={{ width: `${(summary.gradeDistribution.A / Math.max(summary.productCount, 1)) * 100}%` }} />
          </div>
        </div>

        <div className="card kpi">
          <span className="label">
            <AlertTriangle size={13} /> 待处理问题
          </span>
          <div className="value">
            <AnimatedNumber value={summary.issueCount} />
            <small>条</small>
          </div>
          <div className="foot" style={{ gap: 6, flexWrap: "wrap" }}>
            <SeverityPill severity="critical" label={`致命 ${summary.severityCounts.critical}`} />
            <SeverityPill severity="major" label={`严重 ${summary.severityCounts.major}`} />
            <SeverityPill severity="minor" label={`轻微 ${summary.severityCounts.minor}`} />
          </div>
        </div>

        <div className="card kpi">
          <span className="label">
            <Wand2 size={13} /> 可自动修复
          </span>
          <div className="value">
            <AnimatedNumber value={summary.autoFixableCount} />
            <small>条</small>
          </div>
          <div className="foot">
            <span>应用后类目均分预计 +{summary.projectedCatalogGain.toFixed(2)}</span>
          </div>
          <button className="btn subtle" style={{ alignSelf: "flex-start", paddingLeft: 0 }} onClick={() => onNavigate("repairs")}>
            去修复中心 <ArrowRight size={13} />
          </button>
        </div>
      </div>

      <div className="grid split-2">
        <Card
          title="健康分分布"
          sub={`共 ${formatNumber(summary.productCount)} 个 SKU`}
          actions={
            <div className="legend">
              <span>
                <i style={{ background: "#0e7c63" }} />A
              </span>
              <span>
                <i style={{ background: "#4a8f4a" }} />B
              </span>
              <span>
                <i style={{ background: "#b08200" }} />C
              </span>
              <span>
                <i style={{ background: "#c2620a" }} />D
              </span>
            </div>
          }
        >
          <Histogram data={summary.scoreHistogram} gradeBands={gradeBands} />
        </Card>

        <Card title="等级构成" sub="按健康分区间统计">
          <GradeStack distribution={summary.gradeDistribution} />
        </Card>
      </div>

      <div className="grid split-2">
        <Card title="问题维度分布" sub="按严重程度堆叠">
          <SeverityBars rows={summary.dimensionBreakdown} />
        </Card>

        <Card
          title="扫描历史"
          sub={latest ? `最近一次 ${relativeTime(latest.at)}` : "暂无记录"}
        >
          {history.length > 0 ? (
            <>
              <Sparkline points={history.map((item) => item.averageScore)} />
              <div className="stat-strip" style={{ marginTop: 12 }}>
                <div className="cell">
                  <span>最新均分</span>
                  <strong>{latest?.averageScore.toFixed(1)}</strong>
                </div>
                <div className="cell">
                  <span>最新问题数</span>
                  <strong>{formatNumber(latest?.issueCount ?? 0)}</strong>
                </div>
                <div className="cell">
                  <span>已应用修复</span>
                  <strong>{formatNumber(summary.appliedRepairCount)}</strong>
                </div>
                <div className="cell">
                  <span>扫描次数</span>
                  <strong>{history.length}</strong>
                </div>
              </div>
            </>
          ) : (
            <div className="empty">暂无扫描记录</div>
          )}
        </Card>
      </div>

      <Card
        title="高优先级问题"
        sub={`共 ${summary.severityCounts.critical + summary.severityCounts.major} 条致命/严重问题`}
        actions={
          <button className="btn subtle" onClick={() => onNavigate("issues")}>
            查看全部 <ArrowRight size={13} />
          </button>
        }
        bodyClass=""
      >
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th style={{ width: 84 }}>级别</th>
                <th style={{ width: 120 }}>SKU</th>
                <th>问题</th>
                <th style={{ width: 130 }}>维度</th>
                <th style={{ width: 110 }}>可修复</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {summary.topIssues.map((issue) => (
                <tr key={issue.id} className="clickable" onClick={() => onOpenIssue(issue)}>
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
                  <td className="nowrap">
                    {issue.autoFixable ? <span className="pill accent">可自动修复</span> : <span className="pill outline">需人工确认</span>}
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="btn subtle"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenProduct(issue.sku);
                        }}
                      >
                        商品
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="类目健康度" sub="按平均分升序，优先关注垫底类目" bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>类目</th>
                <th style={{ width: 90 }}>SKU 数</th>
                <th style={{ width: 100 }}>问题数</th>
                <th style={{ width: 110 }}>致命/严重</th>
                <th style={{ width: 150 }}>属性完整度</th>
                <th style={{ width: 160 }}>平均健康分</th>
              </tr>
            </thead>
            <tbody>
              {summary.categoryHealth.map((row) => (
                <tr key={row.categoryId}>
                  <td>
                    <div className="cell-title">
                      <strong>{row.name}</strong>
                      <span>{row.path}</span>
                    </div>
                  </td>
                  <td className="num">{row.productCount}</td>
                  <td className="num">{row.issueCount}</td>
                  <td className="num">
                    {row.criticalCount} / {row.majorCount}
                  </td>
                  <td>
                    <div className="bar-track">
                      <i
                        style={{
                          width: `${row.completeness * 100}%`,
                          background: row.completeness >= 0.95 ? "#0e7c63" : row.completeness >= 0.8 ? "#b08200" : "#c2620a",
                        }}
                      />
                    </div>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>{(row.completeness * 100).toFixed(0)}%</span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="bar-track" style={{ flex: 1 }}>
                        <i
                          style={{
                            width: `${row.averageScore}%`,
                            background: row.averageScore >= 90 ? "#0e7c63" : row.averageScore >= 78 ? "#4a8f4a" : "#c2620a",
                          }}
                        />
                      </span>
                      <span className="num" style={{ width: 38, textAlign: "right" }}>
                        {row.averageScore.toFixed(1)}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

