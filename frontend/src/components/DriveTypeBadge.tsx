import type { SanitizationDevice } from '../types';

type DriveKind = 'HDD' | 'SSD' | 'NVMe' | 'USB' | string;

const CLASS_FOR: Record<string, string> = {
  HDD: 'drive-badge drive-badge-hdd',
  SSD: 'drive-badge drive-badge-ssd',
  NVMe: 'drive-badge drive-badge-nvme',
  USB: 'drive-badge drive-badge-usb',
};

export default function DriveTypeBadge({
  type,
  device,
}: {
  type?: DriveKind;
  device?: SanitizationDevice;
}) {
  const label = (type || device?.type || device?.drive_type || 'UNKNOWN').toString();
  const cls = CLASS_FOR[label] ?? 'drive-badge drive-badge-usb';
  return <span className={cls}>{label}</span>;
}
