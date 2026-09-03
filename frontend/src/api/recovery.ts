import type { Evidence, RecoveryResultsResponse, DashboardStats, HealthStatus } from '../types';
import { apiGet, apiPost, apiUpload } from './client';
import { mockEvidence } from './mocks/evidence';
import { mockRecoveryResults } from './mocks/recovery';
import { mockDashboardStats } from './mocks/audit';

function mockImportedEvidence(filename: string, format: Evidence['format']): Evidence {
  return {
    ...mockEvidence[0],
    id: `EV-${Date.now()}`,
    filename,
    format,
    status: 'importing',
    import_timestamp: new Date().toISOString(),
  };
}

export function importEvidence(input: {
  filename?: string;
  format?: string;
  file?: File;
  demo?: boolean;
  path?: string;
}): Promise<Evidence> {
  const filename = input.file?.name ?? input.filename ?? 'evidence.img';
  const format = (input.format ??
    (filename.toLowerCase().endsWith('.e01')
      ? 'E01'
      : filename.toLowerCase().endsWith('.aff4')
        ? 'AFF4'
        : 'raw')) as Evidence['format'];
  const mockResponse = mockImportedEvidence(filename, format);

  if (input.file) {
    const form = new FormData();
    form.append('file', input.file);
    return apiUpload('/evidence/import', form, mockResponse);
  }

  return apiPost(
    '/evidence/import',
    {
      filename,
      format,
      demo: input.demo ?? false,
      path: input.path,
    },
    mockResponse,
  );
}

export function getEvidenceList(): Promise<Evidence[]> {
  return apiGet('/evidence', mockEvidence);
}

export function getRecoveryResults(sessionId?: string): Promise<RecoveryResultsResponse> {
  const id = sessionId ?? 'latest';
  return apiGet(`/recovery/results/${id}`, mockRecoveryResults);
}

export function startRecovery(evidenceId: string): Promise<RecoveryResultsResponse> {
  return apiPost('/recovery/start', { evidence_id: evidenceId }, mockRecoveryResults);
}

export function getDashboardStats(): Promise<DashboardStats> {
  return apiGet('/dashboard/stats', mockDashboardStats);
}

export function getHealth(): Promise<HealthStatus> {
  return apiGet('/health', { ok: true, tool: 'ForensicRecover', version: 'mock', mocks: true });
}
