/**
 * Base HTTP client for the Hermes Local Stack backend.
 *
 * Rules:
 * - All backend calls must go through this client (never bypass to direct
 *   Hermes, n8n, MCP, or filesystem access from the frontend).
 * - BASE_URL is read from the Vite env variable VITE_API_BASE_URL so it
 *   can be changed without modifying source code.
 */

function defaultApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  const host = window.location.hostname || "localhost";
  return `http://${host}:8000`;
}

export const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  defaultApiBaseUrl();

export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

/**
 * Thin fetch wrapper.
 * - Always sends/receives JSON.
 * - Throws ApiError on non-2xx responses.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError(response.status, text || response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
