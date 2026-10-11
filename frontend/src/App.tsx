import {
  Copy,
  Download,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  Package,
  RefreshCw,
  Search,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { IssueDrawer } from "./components/IssueDrawer";
import type { Issue, Meta, Summary } from "./types";
import { useToasts } from "./ui";
import { Duplicates } from "./views/Duplicates";
import { Eval } from "./views/Eval";
import { Issues } from "./views/Issues";
import { Overview } from "./views/Overview";
import { Products } from "./views/Products";
import { Repairs } from "./views/Repairs";

type ViewKey = "overview" | "issues" | "products" | "duplicates" | "repairs" | "eval";

const NAV: { key: ViewKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: "overview", label: "运营总览", icon: LayoutDashboard },
  { key: "issues", label: "问题队列", icon: ListChecks },
  { key: "products", label: "商品目录", icon: Package },
  { key: "duplicates", label: "重复商品", icon: Copy },
  { key: "repairs", label: "修复中心", icon: Wand2 },
  { key: "eval", label: "评测报告", icon: FlaskConical },
];

const TITLES: Record<ViewKey, { title: string; sub: string }> = {
  overview: { title: "运营总览", sub: "目录健康、问题分布与修复收益" },
  issues: { title: "问题队列", sub: "逐条排查并应用可解释的修复建议" },
  products: { title: "商品目录", sub: "以 SKU 为单位核对属性与评分" },
  duplicates: { title: "重复商品", sub: "相似度聚类与人工决策留痕" },
  repairs: { title: "修复中心", sub: "批量应用可自动修复项并导出清洗结果" },
  eval: { title: "评测报告", sub: "规则命中 precision / recall 与能力边界" },
};

const VIEW_KEYS = NAV.map((item) => item.key);

function viewFromHash(hash: string): ViewKey {
  const key = hash.replace(/^#\/?/, "").split("?")[0];
  return (VIEW_KEYS as string[]).includes(key) ? (key as ViewKey) : "overview";
}

export default function App() {
  const [view, setView] = useState<ViewKey>(() => viewFromHash(window.location.hash));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [globalQuery, setGlobalQuery] = useState("");
  const [activeIssue, setActiveIssue] = useState<Issue | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const { push, view: toastView } = useToasts();

  const go = useCallback((next: ViewKey) => {
    if (viewFromHash(window.location.hash) !== next) {
      window.location.hash = `#/${next}`;
    }
    setView(next);
  }, []);

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [nextSummary, nextMeta] = await Promise.all([api.summary(), api.meta()]);
      setSummary(nextSummary);
      setMeta(nextMeta);
    } catch (error) {
      push("无法连接后端", `${(error as Error).message}。请确认 uvicorn 已在 8010 端口启动。`, "error");
    }
  }, [push]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = document.activeElement?.tagName;
      if (event.key === "/" && target !== "INPUT" && target !== "SELECT") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const refresh = useCallback(() => {
    setRefreshKey((key) => key + 1);
    void loadAll();
  }, [loadAll]);

  async function rescan() {
    setBusy(true);
    try {
      await api.scan();
      refresh();
      push("扫描完成", "已重新生成示例目录并重跑全部规则");
    } catch (error) {
      push("扫描失败", (error as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  function renderView() {
    if (view === "overview") {
      if (!summary) return <div className="card card-body">正在加载目录数据…</div>;
      return (
        <Overview
          summary={summary}
          onOpenIssue={setActiveIssue}
          onOpenProduct={() => go("products")}
          onNavigate={(target) => go(target)}
        />
      );
    }
    if (view === "issues") {
      return (
        <Issues
          meta={meta}
          refreshKey={refreshKey}
          externalQuery={globalQuery}
          onOpenProduct={() => go("products")}
          onDataChanged={refresh}
          push={push}
        />
      );
    }
    if (view === "products") {
      return <Products meta={meta} refreshKey={refreshKey} onDataChanged={refresh} push={push} />;
    }
    if (view === "duplicates") {
      return <Duplicates refreshKey={refreshKey} onDataChanged={refresh} push={push} />;
    }
    if (view === "repairs") {
      return <Repairs refreshKey={refreshKey} onDataChanged={refresh} push={push} />;
    }
    return <Eval refreshKey={refreshKey} push={push} />;
  }

  const counts: Partial<Record<ViewKey, number>> = {
    issues: summary?.issueCount,
    duplicates: summary?.duplicateClusterCount,
    repairs: summary?.autoFixableCount,
    products: summary?.productCount,
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CD</div>
          <div className="brand-text">
            <strong>Catalog Doctor</strong>
            <span>商品数据质量工作台</span>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-label">治理工作台</div>
          {NAV.map((item) => {
            const Icon = item.icon;
            const count = counts[item.key];
            return (
              <button
                key={item.key}
                className={`nav-item ${view === item.key ? "active" : ""}`}
                onClick={() => go(item.key)}
              >
                <Icon size={16} />
                <span className="label">{item.label}</span>
                {count !== undefined && <span className="badge">{count}</span>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div>
            <strong>{summary?.datasetName ?? "加载中…"}</strong>
          </div>
          <div style={{ marginTop: 6 }}>
            {meta ? `${meta.productCount} SKU · ${meta.ruleCount} 条规则` : "正在连接服务"}
          </div>
          <div>零 API Key · 纯本地规则引擎</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumbs">
            <h1>{TITLES[view].title}</h1>
            <span>{TITLES[view].sub}</span>
          </div>
          <span className="topbar-spacer" />
          <div className="search">
            <Search size={14} />
            <input
              ref={searchRef}
              placeholder="搜索 SKU / 标题 / 规则"
              value={globalQuery}
              onChange={(event) => setGlobalQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && globalQuery.trim() && view !== "issues") go("issues");
              }}
            />
            <kbd>/</kbd>
          </div>
          <button className="btn" onClick={rescan} disabled={busy}>
            <RefreshCw size={14} />
            {busy ? "扫描中" : "重新扫描"}
          </button>
          <button className="btn primary" onClick={() => window.open(api.exportUrl, "_blank", "noopener")}>
            <Download size={14} />
            导出清洗结果
          </button>
        </header>

        <main className="content">{renderView()}</main>
      </div>

      {activeIssue && (
        <IssueDrawer
          issue={activeIssue}
          onClose={() => setActiveIssue(null)}
          onApplied={(detail) => {
            const failed = detail.startsWith("修复失败");
            push(failed ? "修复未应用" : "已应用修复", detail, failed ? "error" : "success");
            refresh();
          }}
          onOpenProduct={() => {
            setActiveIssue(null);
            go("products");
          }}
        />
      )}

      {toastView}
    </div>
  );
}

