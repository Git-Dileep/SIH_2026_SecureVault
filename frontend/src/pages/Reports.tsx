import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import type { DashboardStats, RecoveryResultsResponse } from '../types';
import { getDashboardStats, getRecoveryResults } from '../api/recovery';
import { reportUrl } from '../api/client';
import PageHeader from '../components/PageHeader';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function Reports() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recovery, setRecovery] = useState<RecoveryResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDashboardStats(), getRecoveryResults()])
      .then(([st, rec]) => {
        setStats(st);
        setRecovery(rec);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load reports');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-8 text-[13px] text-muted text-center">Loading reports...</div>;
  }

  if (error) {
    return <div className="p-8 text-[13px] text-danger text-center">{error}</div>;
  }

  if (!stats || !recovery || recovery.status === 'idle' || !recovery.session_id) {
    return (
      <>
        <PageHeader title="Case Reports" subtitle="No recovery report yet" />
        <div className="card max-w-[560px]">
          <p className="text-[13px] mb-4">Run a carve against a raw image to generate JSON and HTML case reports.</p>
          <Link to="/import" className="btn btn-primary no-underline">Import evidence</Link>
        </div>
      </>
    );
  }

  const totalBytes = recovery.files.reduce((sum, file) => sum + file.size_bytes, 0);

  return (
    <>
      <PageHeader
        title="Case Reports"
        subtitle={`Session ${recovery.session_id} · Evidence ${recovery.evidence_id}`}
        actions={
          <div className="flex gap-2">
            {recovery.evidence_id && (
              <a
                className="btn btn-secondary mono text-[12px] no-underline"
                href={reportUrl(recovery.evidence_id, 'html')}
                target="_blank"
                rel="noreferrer"
              >
                HTML REPORT
              </a>
            )}
            <Link to="/recovery/results" className="btn btn-secondary mono text-[12px] no-underline">
              OPEN RECOVERY
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card flex flex-col gap-2">
          <div className="text-[12px] text-muted uppercase tracking-wider">Recovered files</div>
          <div className="text-[24px] font-mono">{recovery.total_files}</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="text-[12px] text-muted uppercase tracking-wider">Avg confidence</div>
          <div className="text-[24px] font-mono">{Math.round(stats.avg_confidence * 100)}%</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="text-[12px] text-muted uppercase tracking-wider">Payload size</div>
          <div className="text-[24px] font-mono">{formatBytes(totalBytes)}</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="text-[12px] text-muted uppercase tracking-wider">Audit events</div>
          <div className="text-[24px] font-mono">{stats.audit_events}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Recovery by type</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {stats.recovery_by_type.map((row) => (
                <tr key={row.type}>
                  <td className="mono">{row.type}</td>
                  <td className="mono">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Confidence distribution</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Band</th>
                <th>Files</th>
              </tr>
            </thead>
            <tbody>
              {stats.confidence_distribution.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td className="mono">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card col-span-2 p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Recovered file index</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Offset</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {recovery.files.map((file) => (
                <tr key={file.id}>
                  <td className="truncate max-w-[280px]">{file.filename}</td>
                  <td className="mono">{file.file_type}</td>
                  <td className="mono">{formatBytes(file.size_bytes)}</td>
                  <td className="mono">0x{file.offset.toString(16).toUpperCase()}</td>
                  <td className="mono">{Math.round(file.confidence_score * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
