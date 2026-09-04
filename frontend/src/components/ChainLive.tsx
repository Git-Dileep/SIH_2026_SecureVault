import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import type { ChainVerifyResult, LedgerBlock } from '../types';
import { getAuditChain, verifyAuditChain } from '../api/audit';

export default function ChainLive({ refreshKey }: { refreshKey?: string | number }) {
  const [blocks, setBlocks] = useState<LedgerBlock[]>([]);
  const [verify, setVerify] = useState<ChainVerifyResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAuditChain(), verifyAuditChain()])
      .then(([chain, report]) => {
        if (cancelled) return;
        const list = (chain.chain ?? []).slice(-6).reverse();
        setBlocks(list);
        setVerify(report);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const ok = verify?.valid !== false && verify?.status !== 'TAMPERED';

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-3">
        <div>
          <h3 className="text-[13px] uppercase tracking-wider text-muted">Live custody chain</h3>
          <p className="text-[12px] text-muted">Every plant / delete / recover is a sealed block. Edit the log file and this turns TAMPERED.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="mono text-[12px]" style={{ color: ok ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {verify?.status ?? '…'}
          </span>
          <Link to="/audit/chain" className="btn btn-secondary btn-sm no-underline">Open ledger</Link>
        </div>
      </div>
      {blocks.length === 0 ? (
        <div className="text-[13px] text-muted">No blocks yet.</div>
      ) : (
        <div className="space-y-2">
          {blocks.map((block) => (
            <div key={block.hash} className="flex gap-3 text-[12px] border-b pb-2" style={{ borderColor: 'var(--color-border)' }}>
              <span className="mono text-muted">#{block.index}</span>
              <span className="flex-1">
                {block.plain || block.action}
                <span className="mono text-muted ml-2">
                  {block.actor || (block.details?.actor as string) || ''}
                  {' · '}
                  {block.timestamp.replace('T', ' ').slice(0, 19)}
                </span>
              </span>
              <span className="mono text-muted hidden md:inline">{block.hash.slice(0, 10)}…</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
