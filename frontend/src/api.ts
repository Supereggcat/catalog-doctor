import type {
  DuplicatesPayload,
  Evaluation,
  Issue,
  Meta,
  Paged,
  ProductDetail,
  ProductRow,
  RepairsPayload,
  Summary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // keep the status line
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "" || value === false) return;
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  summary: () => request<Summary>("/api/v1/summary"),
  meta: () => request<Meta>("/api/v1/meta"),
  products: (params: Record<string, string | number | undefined>) =>
    request<Paged<ProductRow>>(`/api/v1/products${query(params)}`),
  product: (sku: string) => request<ProductDetail>(`/api/v1/products/${encodeURIComponent(sku)}`),
  issues: (params: Record<string, string | number | boolean | undefined>) =>
    request<Paged<Issue>>(`/api/v1/issues${query(params)}`),
  duplicates: () => request<DuplicatesPayload>("/api/v1/duplicates"),
  repairs: () => request<RepairsPayload>("/api/v1/repairs"),
  evaluation: () => request<Evaluation>("/api/v1/eval"),
  scan: () => request<Summary>("/api/v1/scan", { method: "POST", body: JSON.stringify({ dataset: "demo" }) }),
  applyRepairs: (sku: string, issueIds: string[]) =>
    request<{ appliedCount: number; beforeScore: number; afterScore: number; delta: number }>(
      "/api/v1/repairs/apply",
      { method: "POST", body: JSON.stringify({ sku, issueIds }) },
    ),
  applyBulk: (issueIds: string[]) =>
    request<{ appliedCount: number; beforeScore: number; afterScore: number; delta: number; skus: string[] }>(
      "/api/v1/repairs/apply-bulk",
      { method: "POST", body: JSON.stringify({ issueIds }) },
    ),
  resolveDuplicate: (clusterId: string, action: "merge" | "distinct", keepSku?: string) =>
    request<{ clusterId: string; action: string; resolvedCount: number }>("/api/v1/duplicates/resolve", {
      method: "POST",
      body: JSON.stringify({ clusterId, action, keepSku }),
    }),
  exportUrl: `${BASE}/api/v1/export.csv`,
};

export function openExport(): void {
  window.open(api.exportUrl, "_blank", "noopener");
}

