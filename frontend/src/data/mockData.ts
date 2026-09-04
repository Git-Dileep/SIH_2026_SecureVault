import type {
  AccuracyReport,
  DriveDetection,
  FragmentClassification,
  LedgerBlock,
  SanitizationDevice,
} from '../types';

export const mockLedger: LedgerBlock[] = [
  {
    index: 0,
    timestamp: '2026-09-01T08:00:00.000Z',
    action: 'GENESIS',
    details_hash: 'a0'.repeat(32),
    previous_hash: '0',
    hash: 'b0'.repeat(32),
    details: { message: 'System initialized' },
  },
  {
    index: 1,
    timestamp: '2026-09-01T08:05:12.000Z',
    action: 'USER_LOGIN',
    details_hash: 'a1'.repeat(32),
    previous_hash: 'b0'.repeat(32),
    hash: 'b1'.repeat(32),
    details: { operator_id: 'local-operator' },
  },
  {
    index: 2,
    timestamp: '2026-09-01T08:07:44.000Z',
    action: 'EVIDENCE_IMPORTED',
    details_hash: 'a2'.repeat(32),
    previous_hash: 'b1'.repeat(32),
    hash: 'b2'.repeat(32),
    details: { filename: 'synthetic_disk.img', sha256: 'cafebabedeadbeef' },
  },
  {
    index: 3,
    timestamp: '2026-09-01T08:08:01.000Z',
    action: 'RECOVERY_STARTED',
    details_hash: 'a3'.repeat(32),
    previous_hash: 'b2'.repeat(32),
    hash: 'b3'.repeat(32),
    details: { image: 'synthetic_disk.img' },
  },
  {
    index: 4,
    timestamp: '2026-09-01T08:08:09.000Z',
    action: 'FILE_EXTRACTED',
    details_hash: 'a4'.repeat(32),
    previous_hash: 'b3'.repeat(32),
    hash: 'b4'.repeat(32),
    details: { filename: '0001_JPEG_00010000.jpg', type: 'JPEG', method: 'signature' },
  },
  {
    index: 5,
    timestamp: '2026-09-01T08:08:10.000Z',
    action: 'FILE_EXTRACTED',
    details_hash: 'a5'.repeat(32),
    previous_hash: 'b4'.repeat(32),
    hash: 'b5'.repeat(32),
    details: { filename: '0005_AI_PDF_000a0000.pdf', type: 'PDF', method: 'ai_classified', confidence: 0.91 },
  },
  {
    index: 6,
    timestamp: '2026-09-01T08:08:12.000Z',
    action: 'RECOVERY_COMPLETED',
    details_hash: 'a6'.repeat(32),
    previous_hash: 'b5'.repeat(32),
    hash: 'b6'.repeat(32),
    details: { files: 8 },
  },
  {
    index: 7,
    timestamp: '2026-09-01T09:15:00.000Z',
    action: 'ERASURE_STARTED',
    details_hash: 'a7'.repeat(32),
    previous_hash: 'b6'.repeat(32),
    hash: 'b7'.repeat(32),
    details: { drive_type: 'SSD', method: 'ata_secure_erase' },
  },
  {
    index: 8,
    timestamp: '2026-09-01T09:15:08.000Z',
    action: 'ERASURE_VERIFIED',
    details_hash: 'a8'.repeat(32),
    previous_hash: 'b7'.repeat(32),
    hash: 'b8'.repeat(32),
    details: { passed: true, sample_sectors_checked: 256 },
  },
  {
    index: 9,
    timestamp: '2026-09-01T09:15:09.000Z',
    action: 'CERTIFICATE_GENERATED',
    details_hash: 'a9'.repeat(32),
    previous_hash: 'b8'.repeat(32),
    hash: 'b9'.repeat(32),
    details: { standard: 'NIST SP 800-88 Rev. 2' },
  },
];

export const mockClassification: FragmentClassification = {
  file_type: 'jpg',
  display_type: 'JPEG',
  confidence: 0.94,
  entropy: 7.31,
  scores: {
    jpg: 0.94, png: 0.02, pdf: 0.01, zip: 0.01, docx: 0.0,
    xlsx: 0.0, mp4: 0.01, mp3: 0.01, txt: 0.0, exe: 0.0,
  },
  method: 'mlp+heuristic',
  below_threshold: false,
  features: { printable_ratio: 0.12, zero_ratio: 0.01, magic_flags: { jpg: 1 } },
};

export const mockAccuracy: AccuracyReport = {
  model: 'FragmentMLP-3layer',
  accuracy: 0.8815,
  threshold: 0.7,
  types: ['jpg', 'png', 'pdf', 'zip', 'docx', 'xlsx', 'mp4', 'mp3', 'txt', 'exe'],
  fragment_size: 512,
  dataset: 'synthetic FFT-75-style 512-byte fragments',
  baseline_signature_only: 0.65,
  per_class: {
    jpg: 0.96, png: 0.95, pdf: 0.97, zip: 0.91, docx: 0.93,
    xlsx: 0.92, mp4: 0.94, mp3: 0.9, txt: 0.98, exe: 0.89,
  },
};

export const mockDriveDetection: DriveDetection = {
  path: 'workspace/targets/demo_ssd.bin',
  drive_type: 'SSD',
  type: 'SSD',
  model: 'SecureVault Virtual SATA SSD',
  serial: 'SV-SSD-DEMO-001',
  rotational: false,
  is_rotational: false,
  is_nvme: false,
  overprovisioning_risk: true,
  recommended_method: 'ata_secure_erase',
  recommended_nist_level: 'purge',
  nist_purge_command: 'hdparm --user-master u --security-erase NULL <device>',
  notes: 'Virtual SSD. Overwrite cannot reach overprovisioned NAND.',
};

export const mockSsdDevices: SanitizationDevice[] = [
  { name: 'workspace/targets/demo_hdd.bin', type: 'HDD', serial: 'SV-HDD-DEMO-001', capacity_bytes: 2_097_152, overprovisioning_risk: false, recommended_method: 'dod_5220_22m_7pass' },
  { name: 'workspace/targets/demo_ssd.bin', type: 'SSD', serial: 'SV-SSD-DEMO-001', capacity_bytes: 2_097_152, overprovisioning_risk: true, recommended_method: 'ata_secure_erase' },
  { name: 'workspace/targets/demo_nvme.bin', type: 'NVMe', serial: 'SV-NVME-DEMO-001', capacity_bytes: 2_097_152, overprovisioning_risk: true, recommended_method: 'nvme_format_nvm' },
];

export const mockCertificate = {
  certificate_id: 'NIST-SAN-001',
  standard: 'NIST SP 800-88 Rev. 2',
  job_id: 'SAN-001',
  issued_at: '2026-09-01T09:15:09Z',
  operator_id: 'local-operator',
  drive: { type: 'SSD', path: 'workspace/targets/demo_ssd.bin', serial: 'SV-SSD-DEMO-001' },
  method: { label: 'ATA Secure Erase (SECURITY ERASE UNIT)', nist_level: 'purge' },
  verification: { passed: true, sample_sectors_checked: 256, residual_data_found: false },
  certificate_sha256: 'deadbeefcafebabe',
};
