// ===== Types matching docs/data-schema.md exactly =====

export interface EvidenceHashes {
  md5: string;
  sha1: string;
  sha256: string;
}

export type EvidenceStatus = 'importing' | 'imported' | 'analyzing' | 'analyzed' | 'error';

export interface Evidence {
  id: string;
  filename: string;
  format: 'E01' | 'AFF4' | 'raw';
  size_bytes: number;
  import_timestamp: string; // ISO 8601
  hashes: EvidenceHashes;
  status: EvidenceStatus;
  metadata: Record<string, unknown>;
}

export interface IntegrityChecks {
  header_valid: boolean;
  footer_valid: boolean;
  structure_valid: boolean;
  hash: string; // SHA-256
}

export type RecoveryMethod = 'carved' | 'filesystem' | 'metadata';
export type ConfidenceLabel = 'high' | 'medium' | 'low';

export interface RecoveredFile {
  id: string;
  evidence_id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  offset: number;
  recovery_method: RecoveryMethod;
  confidence_score: number; // 0.0–1.0
  confidence_label: ConfidenceLabel;
  ai_explanation: string;
  integrity_checks: IntegrityChecks;
  recovered_at: string; // ISO 8601
}

export interface SanitizationDevice {
  name: string;
  type: 'HDD' | 'SSD' | 'NVMe' | 'USB';
  serial: string;
  capacity_bytes: number;
}

export interface SanitizationVerification {
  passed: boolean;
  sample_sectors_checked: number;
  residual_data_found: boolean;
}

export type SanitizationMethod = 'clear' | 'purge' | 'destroy';
export type SanitizationStatus = 'pending' | 'in_progress' | 'verifying' | 'completed' | 'failed';

export interface SanitizationResult {
  id: string;
  device: SanitizationDevice;
  method: SanitizationMethod;
  passes_completed: number;
  passes_total: number;
  status: SanitizationStatus;
  started_at: string;
  completed_at: string | null;
  verification: SanitizationVerification;
  certificate_url: string | null;
}

export type AuditAction =
  | 'evidence.import'
  | 'recovery.start'
  | 'recovery.complete'
  | 'erasure.start'
  | 'erasure.complete'
  | 'erasure.verify'
  | 'certificate.generate'
  | 'audit.export';

export type AuditOutcome = 'success' | 'failure' | 'error';

export interface AuditLogEntry {
  id: string;
  timestamp: string; // ISO 8601
  actor: string;
  action: AuditAction;
  target: string;
  outcome: AuditOutcome;
  details: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
}

// ===== API Response wrappers =====

export type RecoverySessionStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface RecoveryResultsResponse {
  session_id: string;
  evidence_id: string;
  total_files: number;
  files: RecoveredFile[];
  status?: RecoverySessionStatus;
  progress?: number;
  message?: string;
  image_size_bytes?: number;
}

export interface RecoverySessionSummary {
  session_id: string;
  evidence_id: string;
  status: RecoverySessionStatus;
  progress: number;
  message: string;
  total_files: number;
}

export interface DashboardStats {
  total_evidence: number;
  files_recovered: number;
  erasures_completed: number;
  audit_events: number;
  avg_confidence: number;
  recovery_by_type: { type: string; count: number }[];
  recent_activity: AuditLogEntry[];
  confidence_distribution: { label: string; count: number }[];
  sessions?: RecoverySessionSummary[];
}

export interface HealthStatus {
  ok: boolean;
  tool: string;
  version: string;
  mocks?: boolean;
}
