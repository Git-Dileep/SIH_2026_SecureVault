import type { AuditLogEntry } from '../types';
import { apiGet } from './client';
import { mockAuditLog } from './mocks/audit';

/**
 * Get audit log entries, optionally filtered.
 */
export function getAuditLog(filters?: {
  from?: string;
  to?: string;
  actor?: string;
  action?: string;
}): Promise<AuditLogEntry[]> {
  if (filters) {
    let filtered = [...mockAuditLog];
    if (filters.actor) {
      filtered = filtered.filter((e) => e.actor.toLowerCase().includes(filters.actor!.toLowerCase()));
    }
    if (filters.action) {
      filtered = filtered.filter((e) => e.action === filters.action);
    }
    if (filters.from) {
      filtered = filtered.filter((e) => e.timestamp >= filters.from!);
    }
    if (filters.to) {
      filtered = filtered.filter((e) => e.timestamp <= filters.to!);
    }
    return apiGet('/audit/log', filtered);
  }
  return apiGet('/audit/log', mockAuditLog);
}
