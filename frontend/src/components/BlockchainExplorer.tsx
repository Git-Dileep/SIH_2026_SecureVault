import type { LedgerBlock } from '../types';

export default function BlockchainExplorer({
  blocks,
  selected,
  onSelect,
}: {
  blocks: LedgerBlock[];
  selected?: number | null;
  onSelect?: (block: LedgerBlock) => void;
}) {
  const ordered = [...blocks].sort((a, b) => a.index - b.index);
  return (
    <div className="chain-diagram">
      {ordered.map((block, i) => (
        <div key={block.hash} className="chain-node">
          <button
            type="button"
            className={`chain-block ${selected === block.index ? 'is-selected' : ''}`}
            onClick={() => onSelect?.(block)}
          >
            <div className="text-[10px] uppercase tracking-wider text-muted">Block {block.index}</div>
            <div className="text-[12px] font-medium mt-1 leading-snug">{block.plain || block.action}</div>
            <div className="mono text-[10px] text-muted mt-1">
              {(block.actor || (block.details?.actor as string) || 'system')} · {block.timestamp.replace('T', ' ').slice(0, 19)}
            </div>
            <div className="mono text-[10px] text-muted mt-2 break-all">{block.hash.slice(0, 20)}…</div>
          </button>
          {i < ordered.length - 1 && <div className="chain-arrow" aria-hidden>→</div>}
        </div>
      ))}
    </div>
  );
}
