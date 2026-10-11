import type { Grade } from "./types";
import { GRADE_COLOR, SEVERITY_COLOR } from "./ui";

export function Histogram({
  data,
  gradeBands,
}: {
  data: Record<string, number>;
  gradeBands: Record<string, Grade>;
}) {
  const entries = Object.entries(data);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  return (
    <div className="histogram">
      {entries.map(([bucket, value]) => {
        const grade = gradeBands[bucket] ?? "A";
        const height = Math.max(3, (value / max) * 120);
        return (
          <div className="col" key={bucket} title={`${bucket} 分：${value} 个 SKU`}>
            <div className="cap">{value}</div>
            <div
              className="stack"
              style={{ height, background: GRADE_COLOR[grade] }}
              aria-label={`${bucket} 分 ${value} 个商品`}
            />
            <div className="tick">{bucket.split("-")[0]}</div>
          </div>
        );
      })}
    </div>
  );
}

export function GradeStack({ distribution }: { distribution: Record<Grade, number> }) {
  const grades: Grade[] = ["A", "B", "C", "D", "E"];
  const total = grades.reduce((sum, grade) => sum + (distribution[grade] ?? 0), 0) || 1;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="bar-track" style={{ height: 12 }}>
        {grades.map((grade) => {
          const value = distribution[grade] ?? 0;
          if (!value) return null;
          return (
            <i
              key={grade}
              style={{ width: `${(value / total) * 100}%`, background: GRADE_COLOR[grade] }}
              title={`${grade} 级 ${value} 个 SKU`}
            />
          );
        })}
      </div>
      <div className="ring-legend">
        {grades.map((grade) => (
          <div className="item" key={grade}>
            <span className="swatch" style={{ background: GRADE_COLOR[grade] }} />
            <span>{grade} 级</span>
            <span className="count">
              {distribution[grade] ?? 0} · {(((distribution[grade] ?? 0) / total) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SeverityBars({
  rows,
}: {
  rows: { key: string; label: string; count: number; critical: number; major: number; minor: number; info: number }[];
}) {
  const max = Math.max(...rows.map((row) => row.count), 1);
  return (
    <div className="bars">
      {rows.map((row) => (
        <div className="bar-row" key={row.key}>
          <span className="name">{row.label}</span>
          <span className="bar-track">
            {(["critical", "major", "minor", "info"] as const).map((severity) =>
              row[severity] ? (
                <i
                  key={severity}
                  style={{
                    width: `${(row[severity] / max) * 100}%`,
                    background: SEVERITY_COLOR[severity],
                  }}
                  title={`${severity} ${row[severity]}`}
                />
              ) : null,
            )}
          </span>
          <span className="value">{row.count}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ points, height = 42 }: { points: number[]; height?: number }) {
  if (points.length === 0) return <div className="spark" />;
  const width = 240;
  const values = points.length === 1 ? [points[0], points[0]] : points;
  const min = Math.min(...values) - 1;
  const max = Math.max(...values) + 1;
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const path = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / span) * (height - 6) - 3;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `${path} L${width},${height} L0,${height} Z`;

  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="扫描历史趋势">
      <defs>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0e7c63" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#0e7c63" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#sparkFill)" />
      <path d={path} fill="none" stroke="#0e7c63" strokeWidth="1.8" strokeLinejoin="round" />
      {values.map((value, index) => {
        const x = index * step;
        const y = height - ((value - min) / span) * (height - 6) - 3;
        return <circle key={index} cx={x} cy={y} r={2.2} fill="#0e7c63" />;
      })}
    </svg>
  );
}

export function MetricBar({ value, color = "#0e7c63", label }: { value: number; color?: string; label?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 120 }}>
      <span className="bar-track" style={{ flex: 1, height: 6 }}>
        <i style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
      </span>
      <span className="num" style={{ fontSize: 11.5, color: "var(--muted)", minWidth: 34, textAlign: "right" }}>
        {label ?? `${(value * 100).toFixed(0)}%`}
      </span>
    </div>
  );
}

