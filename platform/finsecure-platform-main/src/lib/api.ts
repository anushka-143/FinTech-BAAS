/**
 * API Client — typed methods for all backend endpoints.
 *
 * Base URL defaults to localhost:8000 in dev, configurable via VITE_API_URL.
 * All requests include X-Tenant-Id header from auth context.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

class APIError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const token = localStorage.getItem("auth_token") || "";
  const tenantId = localStorage.getItem("tenant_id") || "default";

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      "X-Tenant-Id": tenantId,
      ...opts.headers,
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new APIError(res.status, data?.detail || res.statusText, data);
  }

  return res.json();
}

// ─── Response wrappers ───

interface APIResponse<T> {
  status: string;
  data: T;
  meta?: Record<string, unknown>;
}

// ─── Auth ───

export const authAPI = {
  login: (email: string, password: string) =>
    request<APIResponse<{ token: string; user: unknown }>>("/v1/auth/login", {
      method: "POST", body: { email, password },
    }),
  refresh: () =>
    request<APIResponse<{ token: string }>>("/v1/auth/refresh", { method: "POST" }),
};

// ─── Payouts ───

export const payoutsAPI = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<APIResponse<unknown[]>>(`/v1/payouts${qs}`);
  },
  get: (id: string) => request<APIResponse<unknown>>(`/v1/payouts/${id}`),
  create: (data: unknown) =>
    request<APIResponse<unknown>>("/v1/payouts", { method: "POST", body: data }),
  retry: (id: string) =>
    request<APIResponse<unknown>>(`/v1/payouts/${id}/retry`, { method: "POST" }),
};

// ─── KYC ───

export const kycAPI = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<APIResponse<unknown[]>>(`/v1/kyc/cases${qs}`);
  },
  get: (id: string) => request<APIResponse<unknown>>(`/v1/kyc/cases/${id}`),
  submit: (data: unknown) =>
    request<APIResponse<unknown>>("/v1/kyc/cases", { method: "POST", body: data }),
  approve: (id: string) =>
    request<APIResponse<unknown>>(`/v1/kyc/cases/${id}/approve`, { method: "POST" }),
  reject: (id: string, reason: string) =>
    request<APIResponse<unknown>>(`/v1/kyc/cases/${id}/reject`, { method: "POST", body: { reason } }),
};

// ─── Collections ───

export const collectionsAPI = {
  list: () => request<APIResponse<unknown[]>>("/v1/virtual-accounts"),
  create: (data: unknown) =>
    request<APIResponse<unknown>>("/v1/virtual-accounts/create", { method: "POST", body: data }),
};

// ─── Ledger ───

export const ledgerAPI = {
  journals: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<APIResponse<unknown[]>>(`/v1/ledger/journals${qs}`);
  },
  balance: (accountId: string) =>
    request<APIResponse<unknown>>(`/v1/ledger/balance/${accountId}`),
  forecast: () =>
    request<APIResponse<unknown>>("/v1/ledger/forecast"),
};

// ─── Risk ───

export const riskAPI = {
  alerts: () => request<APIResponse<unknown[]>>("/v1/risk/alerts"),
  assess: (data: unknown) =>
    request<APIResponse<unknown>>("/v1/risk/assess", { method: "POST", body: data }),
};

// ─── Reconciliation ───

export const reconAPI = {
  runs: () => request<APIResponse<unknown[]>>("/v1/recon/runs"),
  breaks: (runId?: string) => {
    const qs = runId ? `?run_id=${runId}` : "";
    return request<APIResponse<unknown[]>>(`/v1/recon/breaks${qs}`);
  },
  get: (id: string) => request<APIResponse<unknown>>(`/v1/recon/breaks/${id}`),
};

// ─── Webhooks ───

export const webhooksAPI = {
  list: () => request<APIResponse<unknown[]>>("/v1/webhooks/endpoints"),
  create: (data: unknown) =>
    request<APIResponse<unknown>>("/v1/webhooks/endpoints", { method: "POST", body: data }),
  deliveries: (endpointId: string) =>
    request<APIResponse<unknown[]>>(`/v1/webhooks/endpoints/${endpointId}/deliveries`),
};

// ─── Audit ───

export const auditAPI = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<APIResponse<unknown[]>>(`/v1/audit/log${qs}`);
  },
};

// ─── AI Copilot ───

export interface CopilotCitation {
  source: string;
  title: string;
  content_snippet: string;
  relevance_score: number;
}

export interface CopilotResponse {
  answer: string;
  citations: CopilotCitation[];
  confidence: number;
  tools_used: string[];
  requires_human_verification: boolean;
}

export interface AIResult {
  task_type: string;
  summary: string;
  confidence: number;
  root_cause: string | null;
  evidence: { source: string; detail: string; relevance: string }[];
  recommendations: { action: string; reason: string; priority: string; requires_approval: boolean }[];
  warnings: string[];
}

export const aiAPI = {
  copilotAsk: (question: string, sourceTypes?: string[]) =>
    request<APIResponse<CopilotResponse>>("/v1/ai/copilot/ask", {
      method: "POST", body: { question, source_types: sourceTypes },
    }),
  opsCopilot: (query: string) =>
    request<APIResponse<AIResult>>("/v1/ai/copilot/ops", {
      method: "POST", body: { query },
    }),
  devCopilot: (query: string) =>
    request<APIResponse<AIResult>>("/v1/ai/copilot/developer", {
      method: "POST", body: { query },
    }),
  triagePayout: (payoutId: string) =>
    request<APIResponse<AIResult>>(`/v1/ai/triage/payout/${payoutId}`, { method: "POST" }),
  reviewKYC: (caseId: string) =>
    request<APIResponse<AIResult>>(`/v1/ai/review/kyc/${caseId}`, { method: "POST" }),
  analyzeRecon: (breakId: string) =>
    request<APIResponse<AIResult>>(`/v1/ai/analyze/recon/${breakId}`, { method: "POST" }),
  explainRisk: (alertId: string) =>
    request<APIResponse<AIResult>>(`/v1/ai/explain/risk/${alertId}`, { method: "POST" }),
};

// ─── Approvals ───

export interface ApprovalRequest {
  id: string;
  resource_type: string;
  resource_id: string;
  action: string;
  maker_id: string;
  maker_reason: string;
  status: string;
  created_at: string;
  reviewed_at?: string;
  checker_id?: string;
  checker_comment?: string;
}

export const approvalsAPI = {
  list: (status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return request<APIResponse<ApprovalRequest[]>>(`/v1/approvals/pending${qs}`);
  },
  create: (data: { resource_type: string; resource_id: string; action: string; reason: string }) =>
    request<APIResponse<ApprovalRequest>>("/v1/approvals/request", { method: "POST", body: data }),
  review: (id: string, action: "approve" | "reject", comment: string) =>
    request<APIResponse<ApprovalRequest>>(`/v1/approvals/${id}/review`, {
      method: "POST", body: { action, comment },
    }),
};

// ─── Cases ───

export interface CaseRecord {
  id: string;
  case_type: string;
  title: string;
  status: string;
  priority: string;
  assigned_to?: string;
  sla_deadline?: string;
  created_at: string;
  updated_at: string;
  resource_type?: string;
  resource_id?: string;
  ai_summary?: string;
}

export interface CaseComment {
  id: string;
  case_id: string;
  author_id: string;
  content: string;
  comment_type: string;
  created_at: string;
}

export const casesAPI = {
  list: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<APIResponse<CaseRecord[]>>(`/v1/cases/${qs}`);
  },
  get: (id: string) => request<APIResponse<CaseRecord>>(`/v1/cases/${id}`),
  create: (data: unknown) =>
    request<APIResponse<CaseRecord>>("/v1/cases/", { method: "POST", body: data }),
  update: (id: string, data: unknown) =>
    request<APIResponse<CaseRecord>>(`/v1/cases/${id}`, { method: "PATCH", body: data }),
  addComment: (id: string, content: string, commentType?: string) =>
    request<APIResponse<CaseComment>>(`/v1/cases/${id}/comments`, {
      method: "POST", body: { content, comment_type: commentType || "note" },
    }),
  timeline: (id: string) =>
    request<APIResponse<CaseComment[]>>(`/v1/cases/${id}/timeline`),
};

// ─── Policy ───

export const policyAPI = {
  evaluate: (data: { resource_type: string; resource_id: string; action: string; context: unknown }) =>
    request<APIResponse<unknown>>("/v1/policy/evaluate", { method: "POST", body: data }),
  defaults: () => request<APIResponse<unknown>>("/v1/policy/defaults"),
};

// ─── BFF (aggregated views) ───

export const bffAPI = {
  dashboardOverview: () =>
    request<APIResponse<unknown>>("/v1/bff/dashboard/overview"),
  kycDetail: (id: string) =>
    request<APIResponse<unknown>>(`/v1/bff/kyc/${id}/detail`),
  payoutDetail: (id: string) =>
    request<APIResponse<unknown>>(`/v1/bff/payout/${id}/detail`),
};

// ─── Notifications ───

export const notificationsAPI = {
  list: () => request<APIResponse<unknown[]>>("/v1/notifications"),
  markRead: (id: string) =>
    request<APIResponse<unknown>>(`/v1/notifications/${id}/read`, { method: "POST" }),
};

// ─── Real-Time SSE ───

export function createSSEConnection(
  eventTypes?: string[],
  onEvent?: (event: { type: string; data: unknown }) => void,
): EventSource {
  const tenantId = localStorage.getItem("tenant_id") || "default";
  const params = new URLSearchParams({ tenant_id: tenantId });
  if (eventTypes) {
    eventTypes.forEach(t => params.append("event_types", t));
  }
  const es = new EventSource(`${API_BASE}/v1/realtime/stream?${params.toString()}`);
  if (onEvent) {
    es.onmessage = (e) => {
      try { onEvent(JSON.parse(e.data)); } catch { /* ignore parse errors */ }
    };
  }
  return es;
}

// ─── Document AI ───

export const documentAIAPI = {
  extract: (documentId: string) =>
    request<APIResponse<unknown>>(`/v1/document-ai/extract/${documentId}`, { method: "POST" }),
};

export { request, APIError, API_BASE };
