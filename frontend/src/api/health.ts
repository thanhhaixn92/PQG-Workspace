/**
 * Health endpoint client.
 *
 * Calls GET /health on the DIRAP Local Workbench backend.
 */
import { apiFetch } from "./client";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
  timestamp: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
  // The dev server proxies this route to the backend root health endpoint so
  // it uses the same local origin as every other browser request.
  return apiFetch<HealthResponse>("/api/health");
}
