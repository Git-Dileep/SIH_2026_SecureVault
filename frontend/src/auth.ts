const OPERATOR_KEY = 'sv-operator';
const TOKEN_KEY = 'sv-token';

export function getOperator(): string {
  return sessionStorage.getItem(OPERATOR_KEY) || 'local-operator';
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setSession(operatorId: string, token?: string): void {
  sessionStorage.setItem(OPERATOR_KEY, operatorId);
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearSession(): void {
  sessionStorage.removeItem(OPERATOR_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Operator-Id': getOperator(),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}
