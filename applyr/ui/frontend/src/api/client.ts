export const API_BASE = "http://127.0.0.1:8000";

export class ApiError extends Error {}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.message ?? `Request to ${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
