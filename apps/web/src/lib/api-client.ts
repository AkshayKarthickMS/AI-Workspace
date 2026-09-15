import type {
  ApprovalDecisionRequest,
  ArtifactResponse,
  AuditEventResponse,
  HealthResponse,
  KnowledgeDocumentCreateRequest,
  KnowledgeDocumentResponse,
  MissionCreateRequest,
  MissionResponse,
  RunDetailResponse,
  RunStartResponse,
  RunSummaryResponse,
  WorkspaceCreateRequest,
  WorkspaceResponse,
} from "@aegisos/shared";

import { getStoredDisplayName, getStoredIdentity } from "./identity";

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

function authHeaders(): Headers {
  const headers = new Headers();
  const identity = getStoredIdentity();
  if (identity) headers.set("X-Aegis-Identity-Subject", identity);
  const displayName = getStoredDisplayName();
  if (displayName) headers.set("X-Aegis-Display-Name", displayName);
  return headers;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders();
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  for (const [key, value] of new Headers(init.headers)) headers.set(key, value);

  const response = await fetch(`/backend${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = undefined;
    }
    const detailMessage =
      detail && typeof detail === "object" && "detail" in detail
        ? (detail as { detail?: unknown }).detail
        : undefined;
    const message =
      typeof detailMessage === "string"
        ? detailMessage
        : `Request to ${path} failed with status ${response.status}`;
    throw new ApiClientError(message, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonBody(body: unknown): RequestInit {
  return { body: JSON.stringify(body) };
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export async function listWorkspaces(): Promise<WorkspaceResponse[]> {
  return request<WorkspaceResponse[]>("/api/v1/workspaces");
}

export async function createWorkspace(body: WorkspaceCreateRequest): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/api/v1/workspaces", { method: "POST", ...jsonBody(body) });
}

export async function listMissions(workspaceId: string): Promise<MissionResponse[]> {
  return request<MissionResponse[]>(`/api/v1/workspaces/${workspaceId}/missions`);
}

export async function createMission(
  workspaceId: string,
  body: MissionCreateRequest,
): Promise<MissionResponse> {
  return request<MissionResponse>(`/api/v1/workspaces/${workspaceId}/missions`, {
    method: "POST",
    ...jsonBody(body),
  });
}

export async function getMission(
  workspaceId: string,
  missionId: string,
): Promise<MissionResponse> {
  return request<MissionResponse>(`/api/v1/workspaces/${workspaceId}/missions/${missionId}`);
}

export async function listMissionRuns(
  workspaceId: string,
  missionId: string,
): Promise<RunSummaryResponse[]> {
  return request<RunSummaryResponse[]>(
    `/api/v1/workspaces/${workspaceId}/missions/${missionId}/runs`,
  );
}

export async function startRun(
  workspaceId: string,
  missionId: string,
): Promise<RunStartResponse> {
  return request<RunStartResponse>(
    `/api/v1/workspaces/${workspaceId}/missions/${missionId}/runs`,
    { method: "POST" },
  );
}

export async function getRun(workspaceId: string, runId: string): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/v1/workspaces/${workspaceId}/runs/${runId}`);
}

export async function resolveApproval(
  workspaceId: string,
  runId: string,
  body: ApprovalDecisionRequest,
): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/v1/workspaces/${workspaceId}/runs/${runId}/approvals`, {
    method: "POST",
    ...jsonBody(body),
  });
}

export async function resumeRun(workspaceId: string, runId: string): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/v1/workspaces/${workspaceId}/runs/${runId}/resume`, {
    method: "POST",
  });
}

export async function cancelRun(workspaceId: string, runId: string): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/v1/workspaces/${workspaceId}/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export async function listArtifacts(
  workspaceId: string,
  missionId: string,
): Promise<ArtifactResponse[]> {
  return request<ArtifactResponse[]>(
    `/api/v1/workspaces/${workspaceId}/missions/${missionId}/artifacts`,
  );
}

export async function getArtifactContent(
  workspaceId: string,
  artifactId: string,
): Promise<unknown> {
  return request<unknown>(`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/content`);
}

/** Triggers a browser download of an artifact's content. A plain `<a href>`
 * can't send the identity header, so this fetches the bytes with `fetch`
 * and saves them via a synthetic object-URL link -- the standard pattern
 * for an authenticated download in an SPA. */
export async function downloadArtifactContent(
  workspaceId: string,
  artifactId: string,
  filename: string,
): Promise<void> {
  const response = await fetch(
    `/backend/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/content`,
    { headers: authHeaders() },
  );
  if (!response.ok) {
    throw new ApiClientError(
      `Failed to download artifact (status ${response.status})`,
      response.status,
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function listAuditEvents(
  workspaceId: string,
  params?: { runId?: string; eventType?: string; limit?: number; offset?: number },
): Promise<AuditEventResponse[]> {
  const search = new URLSearchParams();
  if (params?.runId) search.set("run_id", params.runId);
  if (params?.eventType) search.set("event_type", params.eventType);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const query = search.toString();
  return request<AuditEventResponse[]>(
    `/api/v1/workspaces/${workspaceId}/audit-events${query ? `?${query}` : ""}`,
  );
}

export async function listKnowledgeDocuments(
  workspaceId: string,
): Promise<KnowledgeDocumentResponse[]> {
  return request<KnowledgeDocumentResponse[]>(
    `/api/v1/workspaces/${workspaceId}/knowledge/documents`,
  );
}

export async function ingestKnowledgeDocument(
  workspaceId: string,
  body: KnowledgeDocumentCreateRequest,
): Promise<KnowledgeDocumentResponse> {
  return request<KnowledgeDocumentResponse>(
    `/api/v1/workspaces/${workspaceId}/knowledge/documents`,
    { method: "POST", ...jsonBody(body) },
  );
}

export interface RunEventMessage {
  id: string;
  data: string;
}

/** Consumes the run's SSE stream via `fetch` + a manual reader rather than
 * `EventSource`, since `EventSource` can't send the identity header. Parses
 * the exact format `app.api.v1.runs.format_sse_event` produces; comment
 * lines (heartbeats, `retry:`) have no `data:` line and are filtered out. */
export async function streamRunEvents(
  workspaceId: string,
  runId: string,
  onEvent: (event: RunEventMessage) => void,
  signal: AbortSignal,
): Promise<void> {
  const headers = authHeaders();
  headers.set("Accept", "text/event-stream");

  const response = await fetch(
    `/backend/api/v1/workspaces/${workspaceId}/runs/${runId}/events`,
    { headers, signal },
  );
  if (!response.ok || !response.body) {
    throw new ApiClientError(
      `Failed to open the event stream (status ${response.status})`,
      response.status,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSseEvent(rawEvent);
      if (parsed) onEvent(parsed);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

function parseSseEvent(raw: string): RunEventMessage | null {
  let id = "";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("id:")) id = line.slice(3).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  return { id, data: dataLines.join("\n") };
}
