import { API_BASE_URL, USE_MOCKS } from '../config';

/**
 * Generic GET wrapper. In mock mode, returns mockData directly.
 * In production mode, fetches from API_BASE_URL + path.
 */
export async function apiGet<T>(path: string, mockData: T): Promise<T> {
  if (USE_MOCKS) {
    // Simulate network delay for realistic UX
    await new Promise((r) => setTimeout(r, 300 + Math.random() * 400));
    return structuredClone(mockData);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
  });

  if (!res.ok) {
    throw new Error(`API GET ${path} failed: ${res.status} ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

/**
 * Generic POST wrapper. In mock mode, returns mockResponse directly.
 * In production mode, POSTs body to API_BASE_URL + path.
 */
export async function apiPost<T>(path: string, body: unknown, mockResponse: T): Promise<T> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400 + Math.random() * 600));
    return structuredClone(mockResponse);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`API POST ${path} failed: ${res.status} ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}
