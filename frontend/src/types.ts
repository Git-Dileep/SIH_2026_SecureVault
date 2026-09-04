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
  ai_confidence?: number | null;
  entropy?: number | null;
  classifier?: 'signature' | 'ai';
}

export interface SanitizationDevice {
  name: string;
  type: 'HDD' | 'SSD' | 'NVMe' | 'USB';
  serial: string;
  capacity_bytes: number;
  drive_type?: string;
  model?: string;
  protocol?: string;
  recommended_method?: string;
  recommended_nist_level?: string;
  overprovisioning_risk?: boolean;
  nist_purge_command?: string;
  notes?: string;
}

export interface SanitizationVerification {
  passed: boolean;
  sample_sectors_checked: number;
  residual_data_found: boolean;
}

export type SanitizationMethod = 'clear' | 'purge' | 'destroy' | 'auto';
export type SanitizationStatus = 'pending' | 'in_progress' | 'verifying' | 'completed' | 'failed';

export interface SanitizationResult {
  id: string;
  device: SanitizationDevice;
  method: SanitizationMethod | string;
  passes_completed: number;
  passes_total: number;
  status: SanitizationStatus;
  started_at: string;
  completed_at: string | null;
  verification: SanitizationVerification;
  certificate_url: string | null;
  technique?: string;
  nist_level?: string;
  drive_type?: string;
  compliance_url?: string;
  certificate?: Record<string, unknown>;
  details?: Record<string, unknown>;
}

export type AuditAction =
  | 'evidence.import'
  | 'recovery.start'
  | 'recovery.complete'
  | 'erasure.start'
  | 'erasure.complete'
  | 'erasure.verify'
  | 'certificate.generate'
  | 'audit.export'
  | 'auth.login'
  | 'auth.register'
  | 'auth.logout'
  | 'ai.classify'
  | 'file.export'
  | 'demo.stage'
  | 'demo.delete'
  | 'demo.upload'
  | 'demo.reset';

export type AuditOutcome = 'success' | 'failure' | 'error';

export interface AuditLogEntry {
  id: string;
  timestamp: string; // ISO 8601
  actor: string;
  action: AuditAction | string;
  target: string;
  outcome: AuditOutcome;
  details: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
  block_index?: number;
  block_hash?: string;
  merkle_root?: string;
}

export interface ChainBlock {
  index: number;
  timestamp: string;
  hash: string;
  prev_hash: string;
  merkle_root: string;
  entries: AuditLogEntry[];
}

export interface ChainAnchor {
  network: string;
  tx_id: string;
  block_index: number;
  block_hash: string;
  anchored_at: string;
}

export interface LedgerBlock {
  index: number;
  timestamp: string;
  action: string;
  details_hash: string;
  previous_hash: string;
  hash: string;
  details?: Record<string, unknown>;
  plain?: string;
  actor?: string;
}

export interface CustodyReceipt {
  title: string;
  generated_at: string;
  operator: string;
  status?: string;
  valid: boolean;
  height: number;
  tip: string;
  note?: string;
  events: { index: number; timestamp: string; action: string; plain: string; hash: string; actor?: string; details: Record<string, unknown> }[];
}

export interface AuditChainResponse {
  height: number;
  tip: string;
  valid: boolean;
  status?: 'VALID' | 'TAMPERED' | string;
  anchors: ChainAnchor[];
  blocks: ChainBlock[];
  chain?: LedgerBlock[];
  verify?: ChainVerifyResult;
}

export interface ChainVerifyResult {
  valid: boolean;
  status?: 'VALID' | 'TAMPERED' | string;
  broken_at: number | null;
  reason: string;
  height: number;
  tip?: string;
  anchors?: number;
  blocks_checked?: number;
}

export interface DriveDetection {
  path?: string;
  type?: string;
  drive_type: string;
  rotational?: boolean | null;
  is_rotational?: boolean | null;
  is_nvme?: boolean;
  supports_trim?: boolean;
  model: string;
  serial?: string;
  protocol?: string;
  recommended_method?: string;
  recommended_nist_level?: string;
  overprovisioning_risk?: boolean;
  nist_purge_command?: string;
  notes?: string;
  capabilities?: Record<string, boolean>;
}

export interface MerkleProof {
  entry_id: string;
  block_index: number;
  block_hash: string;
  merkle_root: string;
  leaf: string;
  proof: { position: string; hash: string }[];
  valid: boolean;
  entry: AuditLogEntry;
}

export interface FragmentClassification {
  file_type: string;
  display_type: string;
  confidence: number;
  entropy: number;
  scores: Record<string, number>;
  method: string;
  below_threshold: boolean;
  features?: {
    printable_ratio?: number;
    zero_ratio?: number;
    magic_flags?: Record<string, number>;
  };
}

export interface AccuracyReport {
  model: string;
  accuracy: number | null;
  threshold: number;
  types: string[];
  fragment_size?: number;
  dataset?: string;
  per_class?: Record<string, number>;
  baseline_signature_only?: number;
  notes?: string;
  train?: { accuracy: number };
  test?: { accuracy: number };
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
  innovations?: {
    ssd_aware_erasure: boolean;
    ai_fragment_classifier: boolean;
    blockchain_audit: boolean;
    chain_height: number;
    chain_valid: boolean;
  };
}

export interface DemoExhibit {
  filename: string;
  size?: number;
  offset?: number;
  sha256?: string;
  type?: string;
  url?: string;
  carvable?: boolean;
}

export interface DeleteRecoverDemo {
  phase: 'empty' | 'picking' | 'staged' | 'deleted' | 'recovering';
  exhibits_folder: DemoExhibit[];
  directory: DemoExhibit[];
  planted: DemoExhibit[];
  inbox?: DemoExhibit[];
  source?: string;
  image_path?: string | null;
  image_size?: number;
  evidence_id?: string | null;
  note?: string;
  evidence?: Evidence;
}

export interface HealthStatus {
  ok: boolean;
  tool: string;
  version: string;
  mocks?: boolean;
  mode?: string;
  bind?: string;
  firmware_simulated?: boolean;
  auth_required?: boolean;
  chain?: { valid: boolean; status?: string; height?: number };
  classifier?: { loaded: boolean; accuracy?: number | null; dataset?: string };
  safety?: { block_devices_refused: boolean; evidence_read_only: boolean; erasure_copy_only: boolean };
}
