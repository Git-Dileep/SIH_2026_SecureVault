import type { AuditOutcome, ConfidenceLabel, EvidenceStatus, SanitizationStatus } from '../types';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'accent' | 'neutral';

interface StatusBadgeProps {
  label: string;
  variant: BadgeVariant;
}

export default function StatusBadge({ label, variant }: StatusBadgeProps) {
  return <span className={`badge badge-${variant}`}>{label}</span>;
}

// ===== Convenience mappers =====

export function EvidenceStatusBadge({ status }: { status: EvidenceStatus }) {
  const map: Record<EvidenceStatus, { label: string; variant: BadgeVariant }> = {
    importing: { label: 'Importing', variant: 'info' },
    imported: { label: 'Imported', variant: 'accent' },
    analyzing: { label: 'Analyzing', variant: 'warning' },
    analyzed: { label: 'Analyzed', variant: 'success' },
    error: { label: 'Error', variant: 'danger' },
  };
  const { label, variant } = map[status];
  return <StatusBadge label={label} variant={variant} />;
}

export function SanitizationStatusBadge({ status }: { status: SanitizationStatus }) {
  const map: Record<SanitizationStatus, { label: string; variant: BadgeVariant }> = {
    pending: { label: 'Pending', variant: 'neutral' },
    in_progress: { label: 'In Progress', variant: 'warning' },
    verifying: { label: 'Verifying', variant: 'info' },
    completed: { label: 'Completed', variant: 'success' },
    failed: { label: 'Failed', variant: 'danger' },
  };
  const { label, variant } = map[status];
  return <StatusBadge label={label} variant={variant} />;
}

export function ConfidenceLabelBadge({ label }: { label: ConfidenceLabel }) {
  const map: Record<ConfidenceLabel, BadgeVariant> = {
    high: 'success',
    medium: 'warning',
    low: 'danger',
  };
  return <StatusBadge label={label.charAt(0).toUpperCase() + label.slice(1)} variant={map[label]} />;
}

export function OutcomeBadge({ outcome }: { outcome: AuditOutcome }) {
  const map: Record<AuditOutcome, BadgeVariant> = {
    success: 'success',
    failure: 'warning',
    error: 'danger',
  };
  return <StatusBadge label={outcome.charAt(0).toUpperCase() + outcome.slice(1)} variant={map[outcome]} />;
}
