export type Severity = "critical" | "major" | "minor" | "info";
export type Grade = "A" | "B" | "C" | "D" | "E";

export interface SeverityCounts {
  critical: number;
  major: number;
  minor: number;
  info: number;
}

export interface DimensionCount {
  key: string;
  label: string;
  count: number;
  critical: number;
  major: number;
  minor: number;
  info: number;
}

export interface CategoryHealth {
  categoryId: string;
  name: string;
  path: string;
  productCount: number;
  issueCount: number;
  criticalCount: number;
  majorCount: number;
  averageScore: number;
  completeness: number;
}

export interface RepairAction {
  issueId: string;
  sku: string;
  code: string;
  dimension: string;
  severity: Severity;
  field: string;
  kind: string;
  before: string | null;
  after: string | null;
  confidence: number;
  message: string;
  productTitle: string;
  categoryId: string;
}

export interface Issue {
  id: string;
  code: string;
  sku: string;
  productId: string;
  categoryId: string;
  dimension: string;
  dimensionLabel: string;
  severity: Severity;
  severityLabel: string;
  field: string;
  message: string;
  evidence: string;
  suggestion: string;
  autoFixable: boolean;
  confidence: number;
  repair: Record<string, unknown> | null;
  productTitle?: string;
  brand?: string;
  score?: number;
}

export interface ProductRow {
  productId: string;
  sku: string;
  title: string;
  brand: string;
  categoryId: string;
  categoryName: string;
  price: number | null;
  currency: string;
  stock: number | null;
  barcode: string;
  images: string[];
  description: string;
  supplier: string;
  score: number;
  grade: Grade;
  completeness: number;
  issueCount: number;
  criticalCount: number;
  majorCount: number;
  autoFixableCount: number;
  issueCodes: string[];
}

export interface AttributeRow {
  key: string;
  label: string;
  value: string;
  required: boolean;
  dtype: string;
  unit: string | null;
  enumValues: string[];
  status: "ok" | "missing" | "issue" | "optional";
  issues: Issue[];
}

export interface ProductDetail extends ProductRow {
  attributes: { values: Record<string, string>; rows: AttributeRow[] };
  issues: Issue[];
  scoreDetail?: {
    score: number;
    grade: Grade;
    dimensionScores: Record<string, number>;
    issueCounts: Record<string, number>;
    completeness: number;
  };
  duplicateCluster: DuplicateCluster | null;
}

export interface Summary {
  datasetName: string;
  generatedAt: string;
  productCount: number;
  issueCount: number;
  duplicateClusterCount: number;
  averageScore: number;
  gradeDistribution: Record<Grade, number>;
  severityCounts: SeverityCounts;
  dimensionBreakdown: DimensionCount[];
  categoryHealth: CategoryHealth[];
  scoreHistogram: Record<string, number>;
  autoFixableCount: number;
  projectedScoreGain: number;
  projectedCatalogGain: number;
  topIssues: Issue[];
  history: { at: string; averageScore: number; issueCount: number; productCount: number }[];
  appliedRepairCount: number;
}

export interface Paged<T> {
  total: number;
  page: number;
  size: number;
  items: T[];
}

export interface DuplicateCluster {
  clusterId: string;
  skus: string[];
  similarity: number;
  reason: string;
  evidence: string[];
  members?: (ProductRow & { supplier: string })[];
  matchesGroundTruth?: boolean;
}

export interface DuplicatesPayload {
  total: number;
  threshold: number;
  labelledClusters: number;
  clusters: DuplicateCluster[];
}

export interface EvalPerCode {
  code: string;
  name: string;
  dimension: string;
  support: number;
  predicted: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface Evaluation {
  available: boolean;
  reason?: string;
  dataset?: {
    name: string;
    generatedAt: string;
    productCount: number;
    labeledSkus: number;
    labeledDefects: number;
    duplicateClusters: number;
  };
  overall?: Record<string, number | string>;
  perCode?: EvalPerCode[];
  duplicates?: Record<string, number>;
  baseline?: Record<string, number | string | string[]>;
  autoFix?: Record<string, number>;
  stress?: { name: string; productCount: number; falsePositiveIssues: number; falsePositiveSkus: number; cleanRate: number };
  capability?: {
    labeledFamilies: number;
    implementedFamilies: number;
    ruleFamilies: number;
    uncoveredFamilies: string[];
    uncoveredDefects: number;
    uncoveredRecall: number;
    note: string;
  };
  rules?: unknown;
}

export interface RepairsPayload {
  total: number;
  applied: { issueId: string; code: string; field: string; before: string; after: string; kind: string }[];
  byCode: { code: string; name: string; count: number }[];
  items: RepairAction[];
}

export interface Meta {
  datasetName: string;
  generatedAt: string;
  productCount: number;
  ruleCount: number;
  categories: {
    categoryId: string;
    name: string;
    path: string;
    productCount: number;
    attributes: { key: string; label: string; dtype: string; required: boolean; unit: string | null }[];
  }[];
  rules: { code: string; name: string; dimension: string; severity: string; description: string }[];
  dimensions: { key: string; label: string }[];
  severities: { key: Severity; label: string }[];
}

