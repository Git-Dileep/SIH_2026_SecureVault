import type { SanitizationResult, SanitizationDevice } from '../types';
import { apiGet, apiPost } from './client';
import { mockErasureJobs, mockDevices } from './mocks/erasure';

/**
 * Get all erasure jobs.
 */
export function getErasureJobs(): Promise<SanitizationResult[]> {
  return apiGet('/erasure/jobs', mockErasureJobs);
}

/**
 * Get status of a specific erasure job.
 */
export function getErasureStatus(jobId: string): Promise<SanitizationResult> {
  const job = mockErasureJobs.find((j) => j.id === jobId) ?? mockErasureJobs[0];
  return apiGet(`/erasure/status/${jobId}`, job);
}

/**
 * Start a new erasure job.
 */
export function startErasure(deviceName: string, method: string): Promise<SanitizationResult> {
  const mockResponse: SanitizationResult = {
    id: `SAN-${Date.now()}`,
    device: mockDevices.find((d) => d.name === deviceName) ?? mockDevices[0],
    method: method as SanitizationResult['method'],
    passes_completed: 0,
    passes_total: method === 'clear' ? 1 : method === 'purge' ? 3 : 0,
    status: 'pending',
    started_at: new Date().toISOString(),
    completed_at: null,
    verification: { passed: false, sample_sectors_checked: 0, residual_data_found: false },
    certificate_url: null,
  };
  return apiPost('/erasure/start', { device: deviceName, method }, mockResponse);
}

/**
 * Get available devices for erasure.
 */
export function getDevices(): Promise<SanitizationDevice[]> {
  return apiGet('/erasure/devices', mockDevices);
}

/**
 * Get erasure certificate download URL.
 */
export function getErasureCertificate(jobId: string): Promise<{ url: string }> {
  return apiGet(`/erasure/certificate/${jobId}`, { url: `/certificates/${jobId}.pdf` });
}
