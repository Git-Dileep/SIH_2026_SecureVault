import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Database, FileSearch, ShieldCheck, ScrollText } from 'lucide-react';
import type { DashboardStats, Evidence } from '../types';
import { getDashboardStats, getEvidenceList, importEvidence } from '../api/recovery';
import PageHeader from '../components/PageHeader';
import { EvidenceStatusBadge, OutcomeBadge } from '../components/StatusBadge';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const load = () =>
    Promise.all([getDashboardStats(), getEvidenceList()]).then(([st, ev]) => {
      setStats(st);
      setEvidence(ev.slice(0, 5));
    });

  useEffect(() => {
    load()
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const busy = stats?.sessions?.some((session) => session.status === 'running');
    if (!busy) return;
    const timer = window.setInterval(() => {
      load().catch(() => undefined);
    }, 800);
    return () => window.clearInterval(timer);
  }, [stats]);

  const loadDemo = async () => {
    setSeeding(true);
    setError(null);
    try {
      await importEvidence({ demo: true });
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load demo image');
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-[13px] text-muted">
        Loading overview...
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-[13px] text-danger">
        {error ?? 'Failed to load dashboard'}
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Live ForensicRecover carver and copy-only erasure demo"
        actions={
          <button className="btn btn-primary mono text-[12px]" disabled={seeding} onClick={() => void loadDemo()}>
            {seeding ? 'IMPORTING…' : 'LOAD DEMO IMAGE'}
          </button>
        }
      />
      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      {/* Compact Stat Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card flex flex-col gap-2">
          <div className="flex items-center justify-between text-[12px] text-muted uppercase tracking-wider">
            <span>Evidence Items</span>
            <Database size={14} />
          </div>
          <div className="text-[24px] font-mono">{stats.total_evidence}</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="flex items-center justify-between text-[12px] text-muted uppercase tracking-wider">
            <span>Recovered Files</span>
            <FileSearch size={14} />
          </div>
          <div className="text-[24px] font-mono">{stats.files_recovered}</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="flex items-center justify-between text-[12px] text-muted uppercase tracking-wider">
            <span>Erasures Completed</span>
            <ShieldCheck size={14} />
          </div>
          <div className="text-[24px] font-mono">{stats.erasures_completed}</div>
        </div>
        <div className="card flex flex-col gap-2">
          <div className="flex items-center justify-between text-[12px] text-muted uppercase tracking-wider">
            <span>Audit Events</span>
            <ScrollText size={14} />
          </div>
          <div className="text-[24px] font-mono">{stats.audit_events}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Recent Evidence */}
        <div className="card p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Recent Evidence</h3>
            <Link to="/import" className="text-[12px] hover:underline" style={{ color: 'var(--color-accent)' }}>View all</Link>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {evidence.length === 0 ? (
                <tr>
                  <td colSpan={3} className="text-muted">No evidence imported yet.</td>
                </tr>
              ) : evidence.map((ev) => (
                <tr key={ev.id}>
                  <td className="mono">{ev.id}</td>
                  <td className="truncate max-w-[150px]">{ev.filename}</td>
                  <td><EvidenceStatusBadge status={ev.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Active Recovery Operations (Mocked as list) */}
        <div className="card p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Active Recovery</h3>
            <Link to="/recovery/results" className="text-[12px] hover:underline" style={{ color: 'var(--color-accent)' }}>View details</Link>
          </div>
          <div className="p-4">
            {(stats.sessions ?? []).length === 0 ? (
              <div className="text-[13px] text-muted">No recovery sessions yet.</div>
            ) : (stats.sessions ?? []).slice(0, 3).map((session) => {
              const pct = Math.round((session.progress || 0) * 100);
              const color = session.status === 'failed'
                ? 'var(--color-danger)'
                : session.status === 'completed'
                  ? 'var(--color-success)'
                  : 'var(--color-warning)';
              return (
                <div key={session.session_id} className="mb-4 last:mb-0">
                  <div className="mb-2 flex justify-between text-[13px]">
                    <span className="mono">{session.session_id} ({session.evidence_id})</span>
                    <span style={{ color }}>{session.status === 'completed' ? '100%' : `${pct}%`}</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${session.status === 'completed' ? 100 : pct}%`, background: color }} />
                  </div>
                  {session.message && (
                    <div className="mt-1 text-[11px] text-muted mono">{session.message}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Audit Activity */}
        <div className="card p-0 overflow-hidden col-span-2">
          <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Recent Audit Activity</h3>
            <Link to="/audit" className="text-[12px] hover:underline" style={{ color: 'var(--color-accent)' }}>View timeline</Link>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_activity.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-muted">No audit events yet.</td>
                </tr>
              ) : stats.recent_activity.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono">{new Date(entry.timestamp).toLocaleString()}</td>
                  <td>{entry.actor}</td>
                  <td className="mono">{entry.action}</td>
                  <td><OutcomeBadge outcome={entry.outcome} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
