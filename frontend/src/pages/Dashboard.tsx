import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Database, FileSearch, ShieldCheck, ScrollText, ArrowRight } from 'lucide-react';
import type { DashboardStats, Evidence } from '../types';
import { getDashboardStats, getEvidenceList } from '../api/recovery';
import PageHeader from '../components/PageHeader';
import { EvidenceStatusBadge, OutcomeBadge } from '../components/StatusBadge';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboardStats(), getEvidenceList()])
      .then(([st, ev]) => {
        setStats(st);
        setEvidence(ev.slice(0, 5)); // recent evidence
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-[13px] text-muted">
        Loading overview...
      </div>
    );
  }

  return (
    <>
      <PageHeader title="Overview" subtitle="System status and recent operations" />

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
              {evidence.map((ev) => (
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
            <div className="mb-2 flex justify-between text-[13px]">
              <span className="mono">RS-2026-001 (EV-2026-001)</span>
              <span style={{ color: 'var(--color-success)' }}>84%</span>
            </div>
            <div className="progress-track mb-4">
              <div className="progress-fill" style={{ width: '84%' }} />
            </div>
            
            <div className="mb-2 flex justify-between text-[13px]">
              <span className="mono">RS-2026-002 (EV-2026-004)</span>
              <span style={{ color: 'var(--color-warning)' }}>32%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: '32%', background: 'var(--color-warning)' }} />
            </div>
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
              {stats.recent_activity.map((entry) => (
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
