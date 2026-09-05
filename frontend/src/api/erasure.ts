import type { DriveDetection, SanitizationResult, SanitizationDevice } from '../types';
import { apiGet, apiPost, apiUpload } from './client';
import { mockErasureJobs, mockDevices } from './mocks/erasure';
import { mockDriveDetection } from '../data/mockData';

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
export function startErasure(deviceName: string, method: string, operatorId?: string): Promise<SanitizationResult> {
  const mockResponse: SanitizationResult = {
    id: `SAN-${Date.now()}`,
    device: mockDevices.find((d) => d.name === deviceName) ?? mockDevices[0],
    method: method as SanitizationResult['method'],
    passes_completed: 0,
    passes_total: method === 'clear' ? 1 : method === 'auto' || method === 'purge' ? 7 : 0,
    status: 'pending',
    started_at: new Date().toISOString(),
    completed_at: null,
    verification: { passed: false, sample_sectors_checked: 0, residual_data_found: false },
    certificate_url: null,
  };
  return apiPost('/erasure/sanitize', { device: deviceName, method, operator_id: operatorId }, mockResponse);
}

export function getComplianceCertificate(jobId: string): Promise<Record<string, unknown>> {
  return apiGet(`/erasure/compliance/${jobId}`, { job_id: jobId, standard: 'NIST SP 800-88 Rev. 2' });
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

export function detectDriveType(devicePath: string): Promise<DriveDetection> {
  return apiGet(`/erasure/detect?device=${encodeURIComponent(devicePath)}`, {
    ...mockDriveDetection,
    path: devicePath,
  });
}

export function sanitizeDrive(devicePath: string, operatorId?: string): Promise<SanitizationResult> {
  return startErasure(devicePath, 'auto', operatorId);
}

export function importErasureFile(file: File, media?: string): Promise<SanitizationDevice> {
  const form = new FormData();
  form.append('file', file);
  if (media) form.append('media', media);
  const mock: SanitizationDevice = {
    name: file.name,
    type: (media as SanitizationDevice['type']) || 'USB',
    serial: 'UPLOAD',
    capacity_bytes: file.size,
  };
  return apiUpload('/erasure/import', form, mock);
}
