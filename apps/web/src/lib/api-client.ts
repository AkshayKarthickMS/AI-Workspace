import type { HealthResponse } from "@aegisos/shared";

export class ApiClientError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "ApiClientError";
  }
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/backend/health", {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new ApiClientError("The API health check was unavailable.", response.status);
  return (await response.json()) as HealthResponse;
}
