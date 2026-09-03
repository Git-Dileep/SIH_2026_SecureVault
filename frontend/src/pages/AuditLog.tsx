import { useEffect, useState } from 'react';
import type { AuditLogEntry, AuditAction } from '../types';
import { getAuditLog } from '../api/audit';
import PageHeader from '../components/PageHeader';
import { OutcomeBadge } from '../components/StatusBadge';

const ACTION_OPTIONS: { value: AuditAction | ''; label: string }[] = [
  { value: '', label: 'All Actions' },
  { value: 'evidence.import', label: 'Evidence Import' },
  { value: 'recovery.start', label: 'Recovery Start' },
  { value: 'recovery.complete', label: 'Recovery Complete' },
  { value: 'erasure.start', label: 'Erasure Start' },
  { value: 'erasure.complete', label: 'Erasure Complete' },
  { value: 'erasure.verify', label: 'Erasure Verify' },
  { value: 'certificate.generate', label: 'Certificate Generate' },
  { value: 'audit.export', label: 'Audit Export' },
];

export default function AuditLog() {
  const [allEntries, setAllEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');

  useEffect(() => {
    let cancelled = false;
    getAuditLog()
      .then((data) => {
        if (cancelled) return;
        const sorted = [...data].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
        );
        setAllEntries(sorted);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const entries = filterAction
    ? allEntries.filter((entry) => entry.action === filterAction)
    : allEntries;

  const isValidChain = allEntries.length > 0 && allEntries.every((entry, idx) => {
    if (idx === 0) return true;
    return allEntries[idx - 1].entry_hash === entry.prev_hash;
  });

  return (
    <>
      <PageHeader
        title="Audit Trail"
        subtitle="Cryptographically verifiable event log"
        actions={
          <button className="btn btn-secondary mono text-[12px]">
            EXPORT LOG
          </button>
        }
      />

      <div className="flex gap-6 items-start">
        <div className="card p-6 flex-1">
          <div className="flex justify-between items-center mb-8 pb-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted">Event Timeline</h3>
            <select
              className="input max-w-[200px] text-[12px] h-8 py-1"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
            >
              {ACTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {loading ? (
            <div className="py-8 text-[13px] text-muted text-center">Loading audit trail...</div>
          ) : (
            <div className="relative pl-6">
              {/* Vertical line */}
              <div className="absolute left-[7px] top-2 bottom-2 w-px" style={{ background: 'var(--color-border)' }} />
              
              {entries.map((entry, idx) => {
                const isLinked = idx === 0 || entries[idx - 1].entry_hash === entry.prev_hash;
                return (
                  <div key={entry.id} className="relative mb-8 last:mb-0">
                    {/* Timeline dot */}
                    <div className="absolute -left-[30px] top-1.5 w-3 h-3 rounded-sm" 
                         style={{ background: 'var(--color-bg-primary)', border: `2px solid ${isLinked ? 'var(--color-success)' : 'var(--color-danger)'}` }} />
                    
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-3">
                        <span className="mono text-[12px] font-semibold text-primary">{entry.action}</span>
                        <OutcomeBadge outcome={entry.outcome} />
                      </div>
                      
                      <div className="flex gap-4 mono text-[11px] text-muted mt-1">
                        <span>{new Date(entry.timestamp).toISOString().replace('T', ' ').slice(0, 19)}</span>
                        <span>ACTOR: {entry.actor}</span>
                        <span>TARGET: {entry.target}</span>
                      </div>

                      <div className="mt-2 bg-bg-surface border p-3 rounded" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-primary)' }}>
                        <div className="grid grid-cols-[80px_1fr] gap-2 mono text-[11px]">
                          <span className="text-muted">PREV HASH</span>
                          <span className="text-secondary">{entry.prev_hash}</span>
                          <span className="text-muted">ENTRY HASH</span>
                          <span className="text-secondary">{entry.entry_hash}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Integrity State Panel */}
        <div className="w-[300px]">
          <div className="card p-0 overflow-hidden sticky top-6">
            <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
              <h3 className="text-[12px] uppercase tracking-wider text-muted">Chain Status</h3>
            </div>
            <div className="p-6 flex flex-col items-center justify-center gap-2">
              <div className="text-[11px] uppercase tracking-widest text-muted">Audit Integrity</div>
              <div className="text-[28px] font-mono font-bold tracking-wider" 
                   style={{ color: isValidChain ? 'var(--color-success)' : 'var(--color-danger)' }}>
                {isValidChain ? 'VALID' : 'COMPROMISED'}
              </div>
              <div className="mt-4 w-full pt-4 border-t" style={{ borderColor: 'var(--color-border)' }}>
                <div className="flex justify-between text-[11px] mono">
                  <span className="text-muted">Verified Entries</span>
                  <span>{entries.length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
