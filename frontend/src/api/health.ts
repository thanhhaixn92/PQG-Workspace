/**
 * Health endpoint client.
 *
 * Calls GET /health on the Hermes Local Stack backend.
 */
import { apiFetch } from "./client";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
  timestamp: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}
