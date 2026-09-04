import { useEffect, useMemo, useState } from 'react';
import type { ChainVerifyResult, LedgerBlock } from '../types';
import { getAuditChain, getBlock, getCustodyReceipt, verifyAuditChain } from '../api/audit';
import BlockchainExplorer from '../components/BlockchainExplorer';
import PageHeader from '../components/PageHeader';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'demo', label: 'Delete → recover' },
  { id: 'recovery', label: 'Carving' },
  { id: 'erasure', label: 'Erasure' },
  { id: 'auth', label: 'Operator' },
];

function bucket(action: string): string {
  if (action.startsWith('DEMO_') || action.includes('DEMO')) return 'demo';
  if (action.startsWith('RECOVERY') || action === 'FILE_EXTRACTED' || action === 'EVIDENCE_IMPORTED' || action === 'AI_CLASSIFIED') return 'recovery';
  if (action.startsWith('ERASURE') || action === 'CERTIFICATE_GENERATED') return 'erasure';
  if (action.startsWith('USER_') || action.includes('LOGIN')) return 'auth';
  return 'all';
}

export default function AuditChainPage() {
  const [blocks, setBlocks] = useState<LedgerBlock[]>([]);
  const [verify, setVerify] = useState<ChainVerifyResult | null>(null);
  const [selected, setSelected] = useState<LedgerBlock | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [exporting, setExporting] = useState(false);

  const load = async () => {
    const [chain, report] = await Promise.all([getAuditChain(), verifyAuditChain()]);
    const list = chain.chain ?? [];
    setBlocks(list);
    setVerify(report);
    return list;
  };

  useEffect(() => {
    load()
      .then((list) => setSelected(list[list.length - 1] ?? null))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load chain'))
      .finally(() => setLoading(false));
  }, []);

  const handleVerify = async () => {
    setError(null);
    try {
      const report = await verifyAuditChain();
      setVerify(report);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verify failed');
    }
  };

  const handleSelect = async (block: LedgerBlock) => {
    setSelected(block);
    try {
      setSelected(await getBlock(block.index));
    } catch {
      /* keep row */
    }
  };

  const downloadReceipt = async () => {
    setExporting(true);
    setError(null);
    try {
      const receipt = await getCustodyReceipt();
      const blob = new Blob([JSON.stringify(receipt, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `securevault-custody-${receipt.height}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const status = verify?.status ?? (verify?.valid === false ? 'TAMPERED' : verify?.valid ? 'VALID' : null);
  const ordered = useMemo(() => [...blocks].sort((a, b) => b.index - a.index), [blocks]);
  const visible = ordered.filter((block) => {
    if (filter !== 'all' && bucket(block.action) !== filter) return false;
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      block.action.toLowerCase().includes(q)
      || (block.plain || '').toLowerCase().includes(q)
      || (block.actor || '').toLowerCase().includes(q)
      || block.hash.toLowerCase().includes(q)
      || JSON.stringify(block.details || {}).toLowerCase().includes(q)
    );
  });

  return (
    <>
      <PageHeader
        title="Chain of custody"
        subtitle="A hash-linked log of what this workstation did. Useful as a receipt: if VALID, nobody silently rewrote the history of plant / delete / carve / wipe."
        actions={
          <div className="flex gap-2">
            <button className="btn btn-secondary mono text-[12px]" disabled={exporting} onClick={() => void downloadReceipt()}>
              {exporting ? 'EXPORTING…' : 'DOWNLOAD RECEIPT'}
            </button>
            <button className="btn btn-primary mono text-[12px]" onClick={() => void handleVerify()}>
              Verify now
            </button>
          </div>
        }
      />
      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Blocks</div>
          <div className="text-[24px] font-mono">{blocks.length}</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Integrity</div>
          <div className="text-[24px] font-mono" style={{ color: status === 'TAMPERED' ? 'var(--color-danger)' : 'var(--color-success)' }}>
            {status ?? '…'}
          </div>
        </div>
        <div className="card col-span-2">
          <div className="text-[11px] uppercase tracking-wider text-muted">What this proves</div>
          <p className="text-[13px] mt-1">
            {status === 'TAMPERED'
              ? `Broken at block ${verify?.broken_at}. Someone changed a stored event.`
              : 'Each block includes the previous hash. A judge can re-run Verify. If it still says VALID, the log matches what the tool wrote.'}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            className={`btn btn-sm ${filter === item.id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
        <input
          className="input max-w-[240px]"
          placeholder="Search file, action, hash…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="card mb-6 overflow-x-auto">
        <h3 className="text-[13px] uppercase tracking-wider text-muted mb-4">Recent blocks</h3>
        {loading ? <div className="text-muted text-[13px]">Loading…</div> : (
          <BlockchainExplorer
            blocks={[...visible].sort((a, b) => a.index - b.index).slice(-12)}
            selected={selected?.index}
            onSelect={(b) => void handleSelect(b)}
          />
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="card p-0 overflow-hidden col-span-2">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>When (UTC)</th>
                <th>User ID</th>
                <th>What happened</th>
                <th>Hash</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((block) => (
                <tr key={block.hash} className="cursor-pointer" onClick={() => void handleSelect(block)}>
                  <td className="mono">{block.index}</td>
                  <td className="mono text-[11px]">{block.timestamp.replace('T', ' ').slice(0, 19)}</td>
                  <td className="mono">{block.actor || (block.details?.actor as string) || '—'}</td>
                  <td>{block.plain || block.action}</td>
                  <td className="mono text-[11px] truncate max-w-[180px]">{block.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3 className="text-[13px] uppercase tracking-wider text-muted mb-3">Selected event</h3>
          {selected ? (
            <div className="space-y-2 text-[13px]">
              <p className="font-medium">{selected.plain || selected.action}</p>
              <div className="grid grid-cols-[80px_1fr] gap-2 text-[11px] mono">
                <span className="text-muted">Block</span><span>{selected.index}</span>
                <span className="text-muted">User</span><span>{selected.actor || (selected.details?.actor as string) || '—'}</span>
                <span className="text-muted">Code</span><span>{selected.action}</span>
                <span className="text-muted">Time</span><span>{selected.timestamp}</span>
                <span className="text-muted">Hash</span><span className="break-all">{selected.hash}</span>
                <span className="text-muted">Prev</span><span className="break-all">{selected.previous_hash}</span>
              </div>
              {selected.details && Object.keys(selected.details).length > 0 && (
                <pre className="text-[11px] mono overflow-x-auto p-2 border" style={{ borderColor: 'var(--color-border)' }}>
                  {JSON.stringify(selected.details, null, 2)}
                </pre>
              )}
              <p className="text-[12px] text-muted">
                To challenge this row, change audit/audit_chain.json and click Verify now.
              </p>
            </div>
          ) : (
            <p className="text-[13px] text-muted">Click a row to explain it.</p>
          )}
        </div>
      </div>
    </>
  );
}
