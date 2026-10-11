import { ArrowRight, Info, ShieldCheck, Wand2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import type { Issue } from "../types";
import { Drawer, SeverityPill, percent } from "../ui";

export function IssueDrawer({
  issue,
  onClose,
  onApplied,
  onOpenProduct,
}: {
  issue: Issue;
  onClose: () => void;
  onApplied?: (detail: string) => void;
  onOpenProduct?: (sku: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const repair = issue.repair as { kind?: string; field?: string; before?: string; after?: string } | null;
  const canFix = issue.autoFixable && repair?.after !== undefined && repair?.after !== null;

  async function apply() {
    if (!canFix) return;
    setBusy(true);
    try {
      const result = await api.applyRepairs(issue.sku, [issue.id]);
      onApplied?.(
        `${issue.sku} 健康分 ${result.beforeScore} → ${result.afterScore}（+${result.delta}），已应用 ${result.appliedCount} 条修复`,
      );
      onClose();
    } catch (error) {
      onApplied?.(`修复失败：${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer
      title={issue.productTitle || issue.sku}
      meta={
        <>
          <SeverityPill severity={issue.severity} />
          <span className="pill neutral">{issue.dimensionLabel}</span>
          <span className="mono">{issue.sku}</span>
        </>
      }
      onClose={onClose}
      footer={
        <>
          {onOpenProduct && (
            <button className="btn" onClick={() => onOpenProduct(issue.sku)}>
              查看商品档案
            </button>
          )}
          <span className="spacer" />
          <button className="btn primary" disabled={!canFix || busy} onClick={apply}>
            <Wand2 size={14} />
            {busy ? "应用中…" : canFix ? "应用建议修复" : "需人工确认"}
          </button>
        </>
      }
    >
      <div className="issue-item">
        <div className="body">
          <div className="msg">{issue.message}</div>
          {issue.evidence && <div className="hint">证据：{issue.evidence}</div>}
          <div className="code">
            <span className="pill outline mono">{issue.code}</span>
          </div>
        </div>
      </div>

      <div>
        <div className="section-title">
          <Info size={14} /> 修复建议
        </div>
        <p style={{ margin: "8px 0 0", color: "var(--ink-soft)" }}>{issue.suggestion}</p>
      </div>

      {repair?.after !== undefined && repair?.after !== null && (
        <div>
          <div className="section-title">
            <Wand2 size={14} /> 变更预览
          </div>
          <div className="diff">
            <span className="before">{String(repair.before ?? "（空）")}</span>
            <span className="arrow">
              <ArrowRight size={14} />
            </span>
            <span className="after">{String(repair.after)}</span>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--muted)" }}>
            字段 <span className="mono">{repair.field}</span> · 修复类型 <span className="mono">{repair.kind}</span>
          </p>
        </div>
      )}

      <div className="stat-strip">
        <div className="cell">
          <span>规则置信度</span>
          <strong>{percent(issue.confidence)}</strong>
        </div>
        <div className="cell">
          <span>所属维度</span>
          <strong style={{ fontSize: 13 }}>{issue.dimensionLabel}</strong>
        </div>
        <div className="cell">
          <span>可自动修复</span>
          <strong style={{ fontSize: 13 }}>{issue.autoFixable ? "是" : "否"}</strong>
        </div>
        <div className="cell">
          <span>商品健康分</span>
          <strong>{issue.score ?? "—"}</strong>
        </div>
      </div>

      {!canFix && (
        <div className="callout warn">
          <ShieldCheck size={15} />
          <div>该问题需要人工确认后修改：自动改写可能影响品牌授权、价格策略或合规表述。</div>
        </div>
      )}
    </Drawer>
  );
}

