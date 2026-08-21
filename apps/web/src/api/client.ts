import type { BinderDocument, GapReport, Protocol, ProtocolCreate, Site, SiteCreate } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
        // Real auth (Entra External ID) plugs in here once a login flow exists —
        // see infra/bicep/modules/entra-b2c.md. The local API accepts requests
        // without a token while AUTH_DISABLED_FOR_LOCAL_DEV=true.
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the TrialReady API. Is it running?");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listSites: () => request<Site[]>("/api/v1/sites"),
  createSite: (payload: SiteCreate) =>
    request<Site>("/api/v1/sites", { method: "POST", body: JSON.stringify(payload) }),

  getSite: (siteId: string) => request<Site>(`/api/v1/sites/${siteId}`),
  listProtocolsForSite: (siteId: string) => request<Protocol[]>(`/api/v1/sites/${siteId}/protocols`),
  createProtocol: (siteId: string, payload: ProtocolCreate) =>
    request<Protocol>(`/api/v1/sites/${siteId}/protocols`, { method: "POST", body: JSON.stringify(payload) }),
  getProtocol: (protocolId: string) => request<Protocol>(`/api/v1/protocols/${protocolId}`),

  listDocuments: (protocolId: string) => request<BinderDocument[]>(`/api/v1/protocols/${protocolId}/documents`),
  uploadDocument: (protocolId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<BinderDocument>(`/api/v1/protocols/${protocolId}/documents`, {
      method: "POST",
      body: form,
    });
  },

  runGapCheck: (protocolId: string) =>
    request<GapReport>(`/api/v1/protocols/${protocolId}/gap-check`, { method: "POST" }),
  getLatestGapCheck: (protocolId: string) =>
    request<GapReport | null>(`/api/v1/protocols/${protocolId}/gap-check/latest`).catch((err) => {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }),
};
