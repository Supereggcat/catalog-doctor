import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import type { Grade, Severity } from "./types";

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "#c0392b",
  major: "#c2620a",
  minor: "#9a7b0a",
  info: "#55636e",
};

export const GRADE_COLOR: Record<Grade, string> = {
  A: "#0e7c63",
  B: "#4a8f4a",
  C: "#b08200",
  D: "#c2620a",
  E: "#b03025",
};

export const DIMENSION_COLOR: Record<string, string> = {
  completeness: "#0e7c63",
  conformance: "#3f7d8c",
  accuracy: "#c2620a",
  consistency: "#7a5ea8",
  text: "#2f7d4f",
  media: "#4a6fa5",
  pricing: "#9a7b0a",
  seo: "#7c6f4d",
  duplication: "#b0523f",
};

export function dimensionColor(key: string): string {
  return DIMENSION_COLOR[key] ?? "#55636e";
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function relativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function SeverityPill({ severity, label }: { severity: Severity; label?: string }) {
  const text: Record<Severity, string> = {
    critical: "致命",
    major: "严重",
    minor: "轻微",
    info: "提示",
  };
  return <span className={`pill ${severity}`}>{label ?? text[severity]}</span>;
}

export function GradeBadge({ grade }: { grade: Grade }) {
  return <span className={`grade ${grade}`}>{grade}</span>;
}

export function Card({
  title,
  sub,
  actions,
  children,
  className = "",
  bodyClass = "card-body",
}: {
  title?: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || actions) && (
        <header className="card-head">
          <h2>{title}</h2>
          {sub && <span className="sub">{sub}</span>}
          <span className="spacer" />
          {actions}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function ScoreRing({
  value,
  size = 76,
  stroke = 8,
  color,
  caption,
}: {
  value: number;
  size?: number;
  stroke?: number;
  color?: string;
  caption?: string;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const dash = (clamped / 100) * circumference;
  const tint = color ?? (clamped >= 90 ? "#0e7c63" : clamped >= 78 ? "#4a8f4a" : clamped >= 64 ? "#b08200" : clamped >= 48 ? "#c2620a" : "#b03025");
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label={`健康分 ${value}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#eceeec" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tint}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          lineHeight: 1.1,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div className="num" style={{ fontSize: size / 4.2, fontWeight: 650 }}>
            {value.toFixed(1)}
          </div>
          {caption && <div style={{ fontSize: 10.5, color: "var(--muted)" }}>{caption}</div>}
        </div>
      </div>
    </div>
  );
}

export function ProgressBar({ value, color = "#0e7c63", height = 6 }: { value: number; color?: string; height?: number }) {
  return (
    <div className="bar-track" style={{ height }}>
      <i style={{ width: `${Math.max(0, Math.min(100, value * 100))}%`, background: color }} />
    </div>
  );
}

export function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="empty">
      {icon}
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

export function SkeletonRows({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: 14 }}>
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <div key={columnIndex} className="skeleton" style={{ width: `${60 + ((rowIndex + columnIndex) % 4) * 10}%` }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function Drawer({
  title,
  meta,
  onClose,
  children,
  footer,
}: {
  title: ReactNode;
  meta?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true">
        <header className="drawer-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2>{title}</h2>
            {meta && <div className="meta">{meta}</div>}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </header>
        <div className="drawer-body">{children}</div>
        {footer && <footer className="drawer-foot">{footer}</footer>}
      </aside>
    </>
  );
}

export interface ToastItem {
  id: number;
  title: string;
  detail?: string;
  tone?: "success" | "error";
}

export function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((title: string, detail?: string, tone: "success" | "error" = "success") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, title, detail, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 4200);
  }, []);

  const view = (
    <div className="toast-stack">
      {toasts.map((item) => (
        <div key={item.id} className={`toast ${item.tone === "error" ? "error" : ""}`}>
          <span className="bar" />
          <div>
            <strong>{item.title}</strong>
            {item.detail && <span>{item.detail}</span>}
          </div>
        </div>
      ))}
    </div>
  );

  return { push, view };
}

export function AnimatedNumber({ value, digits = 0 }: { value: number; digits?: number }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const start = display;
    const delta = value - start;
    if (Math.abs(delta) < 0.005) {
      setDisplay(value);
      return;
    }
    const startedAt = performance.now();
    const duration = 480;
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + delta * eased);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span className="num">{formatNumber(display, digits)}</span>;
}

