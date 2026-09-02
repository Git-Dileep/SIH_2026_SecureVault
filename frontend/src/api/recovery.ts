import type { Evidence, RecoveryResultsResponse, DashboardStats } from '../types';
import { apiGet, apiPost } from './client';
import { mockEvidence } from './mocks/evidence';
import { mockRecoveryResults } from './mocks/recovery';
import { mockDashboardStats } from './mocks/audit';

/**
 * Import new evidence into the system.
 */
export function importEvidence(file: { filename: string; format: string }): Promise<Evidence> {
  const mockResponse: Evidence = {
    ...mockEvidence[0],
    id: `EV-${Date.now()}`,
    filename: file.filename,
    format: file.format as Evidence['format'],
    status: 'importing',
    import_timestamp: new Date().toISOString(),
  };
  return apiPost('/evidence/import', file, mockResponse);
}

/**
 * Get all imported evidence.
 */
export function getEvidenceList(): Promise<Evidence[]> {
  return apiGet('/evidence', mockEvidence);
}

/**
 * Get recovery results for a session.
 */
export function getRecoveryResults(sessionId?: string): Promise<RecoveryResultsResponse> {
  return apiGet(`/recovery/results/${sessionId ?? 'RS-2026-001'}`, mockRecoveryResults);
}

/**
 * Get dashboard statistics.
 */
export function getDashboardStats(): Promise<DashboardStats> {
  return apiGet('/dashboard/stats', mockDashboardStats);
}
