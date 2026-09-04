import { useEffect, useState } from 'react';
import type { AuditLogEntry, AuditAction, AuditChainResponse, ChainVerifyResult } from '../types';
import { getAuditLog, getAuditChain, verifyAuditChain, anchorAuditChain } from '../api/audit';
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
  { value: 'audit.export', label: 'Audit Export / Anchor' },
  { value: 'auth.login', label: 'User login' },
  { value: 'auth.register', label: 'User register' },
  { value: 'auth.logout', label: 'User logout' },
  { value: 'demo.stage', label: 'Demo plant' },
  { value: 'demo.delete', label: 'Demo delete' },
  { value: 'ai.classify', label: 'AI classify' },
];

export default function AuditLog() {
  const [allEntries, setAllEntries] = useState<AuditLogEntry[]>([]);
  const [chain, setChain] = useState<AuditChainResponse | null>(null);
  const [verify, setVerify] = useState<ChainVerifyResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');
  const [anchoring, setAnchoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    Promise.all([getAuditLog(), getAuditChain(), verifyAuditChain()]).then(([log, ch, v]) => {
      const sorted = [...log].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );
      setAllEntries(sorted);
      setChain(ch);
      setVerify(v);
    });

  useEffect(() => {
    let cancelled = false;
    refresh()
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load chain');
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

  const isValidChain = verify?.valid ?? (allEntries.length > 0 && allEntries.every((entry, idx) => {
    if (idx === 0) return true;
    return allEntries[idx - 1].entry_hash === entry.prev_hash;
  }));

  const handleAnchor = async () => {
    setAnchoring(true);
    setError(null);
    try {
      await anchorAuditChain();
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Anchor failed');
    } finally {
      setAnchoring(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Blockchain Chain of Custody"
        subtitle="Permissioned SHA-256 ledger with Merkle-sealed blocks. Tamper-evident, optionally anchored."
        actions={
          <button className="btn btn-primary mono text-[12px]" disabled={anchoring} onClick={() => void handleAnchor()}>
            {anchoring ? 'ANCHORING…' : 'ANCHOR TIP HASH'}
          </button>
        }
      />

      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Height</div>
          <div className="text-[24px] font-mono">{chain?.height ?? 0}</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Integrity</div>
          <div className="text-[24px] font-mono" style={{ color: isValidChain ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {isValidChain ? 'VALID' : 'BROKEN'}
          </div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Anchors</div>
          <div className="text-[24px] font-mono">{chain?.anchors?.length ?? 0}</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Tip</div>
          <div className="mono text-[11px] break-all">{chain?.tip ?? '—'}</div>
        </div>
      </div>

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
              <div className="absolute left-[7px] top-2 bottom-2 w-px" style={{ background: 'var(--color-border)' }} />

              {entries.map((entry, idx) => {
                const isLinked = idx === 0 || entries[idx - 1].entry_hash === entry.prev_hash;
                return (
                  <div key={entry.id} className="relative mb-8 last:mb-0">
                    <div className="absolute -left-[30px] top-1.5 w-3 h-3 rounded-sm"
                         style={{ background: 'var(--color-bg-primary)', border: `2px solid ${isLinked ? 'var(--color-success)' : 'var(--color-danger)'}` }} />

                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-3">
                        <span className="mono text-[12px] font-semibold text-primary">{entry.action}</span>
                        <OutcomeBadge outcome={entry.outcome} />
                        {entry.block_index != null && (
                          <span className="badge badge-info">BLK {entry.block_index}</span>
                        )}
                      </div>

                      <div className="flex gap-4 mono text-[11px] text-muted mt-1">
                        <span>{new Date(entry.timestamp).toISOString().replace('T', ' ').slice(0, 19)}</span>
                        <span>ACTOR: {entry.actor}</span>
                        <span>TARGET: {entry.target}</span>
                      </div>

                      <div className="mt-2 bg-bg-surface border p-3 rounded" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-primary)' }}>
                        <div className="grid grid-cols-[90px_1fr] gap-2 mono text-[11px]">
                          <span className="text-muted">PREV HASH</span>
                          <span className="text-secondary break-all">{entry.prev_hash}</span>
                          <span className="text-muted">ENTRY HASH</span>
                          <span className="text-secondary break-all">{entry.entry_hash}</span>
                          {entry.block_hash && (
                            <>
                              <span className="text-muted">BLOCK</span>
                              <span className="text-secondary break-all">{entry.block_hash}</span>
                            </>
                          )}
                          {entry.merkle_root && (
                            <>
                              <span className="text-muted">MERKLE</span>
                              <span className="text-secondary break-all">{entry.merkle_root}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="w-[320px] flex flex-col gap-4">
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
              <div className="text-[11px] text-muted text-center">{verify?.reason ?? 'hash-linked + merkle-sealed'}</div>
              <div className="mt-4 w-full pt-4 border-t" style={{ borderColor: 'var(--color-border)' }}>
                <div className="flex justify-between text-[11px] mono">
                  <span className="text-muted">Verified Entries</span>
                  <span>{entries.length}</span>
                </div>
              </div>
            </div>
          </div>

          {!!chain?.anchors?.length && (
            <div className="card p-0 overflow-hidden">
              <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
                <h3 className="text-[12px] uppercase tracking-wider text-muted">External anchors</h3>
              </div>
              <div className="p-4 space-y-3">
                {chain.anchors.map((anchor) => (
                  <div key={anchor.tx_id} className="mono text-[11px]">
                    <div className="text-muted">{anchor.network}</div>
                    <div className="break-all">{anchor.tx_id}</div>
                    <div className="text-muted">block {anchor.block_index}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
