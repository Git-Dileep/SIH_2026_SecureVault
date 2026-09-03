import { API_BASE_URL, USE_MOCKS } from '../config';

async function readError(res: Response, path: string): Promise<string> {
  const body = await res.text();
  try {
    const parsed = JSON.parse(body) as { error?: string };
    if (parsed.error) return parsed.error;
  } catch {
    /* use raw text */
  }
  return body || `${res.status} ${res.statusText} for ${path}`;
}

/**
 * Generic GET wrapper. In mock mode, returns mockData directly.
 * In production mode, fetches from API_BASE_URL + path.
 */
export async function apiGet<T>(path: string, mockData: T): Promise<T> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 300 + Math.random() * 400));
    return structuredClone(mockData);
  }

  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(await readError(res, path));
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
    throw new Error(await readError(res, path));
  }
  return res.json() as Promise<T>;
}

export async function apiUpload<T>(path: string, form: FormData, mockResponse: T): Promise<T> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400 + Math.random() * 600));
    return structuredClone(mockResponse);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    throw new Error(await readError(res, path));
  }
  return res.json() as Promise<T>;
}

export function fileUrl(evidenceId: string, filename: string): string {
  return `${API_BASE_URL}/files/${encodeURIComponent(evidenceId)}/${encodeURIComponent(filename)}`;
}

export function reportUrl(evidenceId: string, kind: 'html' | 'json'): string {
  return `${API_BASE_URL}/reports/${encodeURIComponent(evidenceId)}/${kind}`;
}

export function apiAssetUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}
