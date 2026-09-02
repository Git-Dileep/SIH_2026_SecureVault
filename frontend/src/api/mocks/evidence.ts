import type { Evidence } from '../../types';

export const mockEvidence: Evidence[] = [
  {
    id: 'EV-2026-001',
    filename: 'case_447_drive_image.E01',
    format: 'E01',
    size_bytes: 256_000_000_000,
    import_timestamp: '2026-08-28T09:15:00Z',
    hashes: {
      md5: 'a3f2b8c1d4e5f6a7b8c9d0e1f2a3b4c5',
      sha1: '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b',
      sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    },
    status: 'analyzed',
    metadata: { case_number: 'CASE-2026-447', examiner: 'Dr. Sarah Chen' },
  },
  {
    id: 'EV-2026-002',
    filename: 'suspect_usb_backup.AFF4',
    format: 'AFF4',
    size_bytes: 32_000_000_000,
    import_timestamp: '2026-08-29T14:30:00Z',
    hashes: {
      md5: 'b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9',
      sha1: '2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c',
      sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    },
    status: 'analyzed',
    metadata: { case_number: 'CASE-2026-447', examiner: 'Dr. Sarah Chen' },
  },
  {
    id: 'EV-2026-003',
    filename: 'server_raid_partition_3.raw',
    format: 'raw',
    size_bytes: 512_000_000_000,
    import_timestamp: '2026-08-30T08:00:00Z',
    hashes: {
      md5: 'c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0',
      sha1: '3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d',
      sha256: 'd7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592',
    },
    status: 'importing',
    metadata: { case_number: 'CASE-2026-512', examiner: 'James Rodriguez' },
  },
  {
    id: 'EV-2026-004',
    filename: 'mobile_extraction_full.E01',
    format: 'E01',
    size_bytes: 64_000_000_000,
    import_timestamp: '2026-08-31T11:45:00Z',
    hashes: {
      md5: 'd6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1',
      sha1: '4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e',
      sha256: '4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce',
    },
    status: 'analyzing',
    metadata: { case_number: 'CASE-2026-512', examiner: 'James Rodriguez' },
  },
];
