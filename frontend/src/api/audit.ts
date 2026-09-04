import type { AuditChainResponse, AuditLogEntry, ChainVerifyResult, CustodyReceipt, LedgerBlock, MerkleProof } from '../types';
import { apiGet, apiPost } from './client';
import { mockAuditLog } from './mocks/audit';
import { mockLedger } from '../data/mockData';

/**
 * Get audit log entries, optionally filtered.
 */
export function getAuditLog(filters?: {
  from?: string;
  to?: string;
  actor?: string;
  action?: string;
}): Promise<AuditLogEntry[]> {
  if (filters) {
    let filtered = [...mockAuditLog];
    if (filters.actor) {
      filtered = filtered.filter((e) => e.actor.toLowerCase().includes(filters.actor!.toLowerCase()));
    }
    if (filters.action) {
      filtered = filtered.filter((e) => e.action === filters.action);
    }
    if (filters.from) {
      filtered = filtered.filter((e) => e.timestamp >= filters.from!);
    }
    if (filters.to) {
      filtered = filtered.filter((e) => e.timestamp <= filters.to!);
    }
    return apiGet('/audit/log', filtered);
  }
  return apiGet('/audit/log', mockAuditLog);
}

const mockChain: AuditChainResponse = {
  height: mockLedger.length - 1,
  tip: mockLedger[mockLedger.length - 1]?.hash ?? '',
  valid: true,
  status: 'VALID',
  anchors: [],
  chain: mockLedger,
  blocks: mockAuditLog.map((entry, i) => ({
    index: i + 1,
    timestamp: entry.timestamp,
    hash: entry.entry_hash,
    prev_hash: entry.prev_hash,
    merkle_root: entry.entry_hash,
    entries: [entry],
  })),
};

export function getAuditChain(): Promise<AuditChainResponse> {
  return apiGet('/audit/chain', mockChain);
}

export function verifyAuditChain(): Promise<ChainVerifyResult> {
  return apiGet('/audit/verify', {
    valid: true,
    status: 'VALID',
    broken_at: null,
    reason: 'chain intact',
    height: mockChain.height,
    blocks_checked: mockLedger.length,
  });
}

export function getCustodyReceipt(): Promise<CustodyReceipt> {
  return apiGet('/audit/receipt', {
    title: 'SecureVault chain-of-custody receipt',
    generated_at: new Date().toISOString(),
    operator: 'local-operator',
    valid: true,
    status: 'VALID',
    height: mockChain.height,
    tip: mockChain.tip,
    events: [],
  });
}

export function getBlock(index: number): Promise<LedgerBlock> {
  const block = mockLedger.find((item) => item.index === index) ?? mockLedger[0];
  return apiGet(`/audit/block/${index}`, block);
}

export function getMerkleProof(entryId: string): Promise<MerkleProof> {
  const entry = mockAuditLog.find((item) => item.id === entryId) ?? mockAuditLog[0];
  return apiGet(`/audit/proof/${entryId}`, {
    entry_id: entryId,
    block_index: 1,
    block_hash: entry.entry_hash,
    merkle_root: entry.entry_hash,
    leaf: entry.entry_hash,
    proof: [],
    valid: true,
    entry,
  });
}

export function anchorAuditChain(network = 'simulated-ethereum'): Promise<{ tx_id: string; network: string; block_hash: string }> {
  return apiPost('/audit/anchor', { network }, {
    tx_id: `0x${'ab'.repeat(32)}`,
    network,
    block_hash: mockChain.tip,
  });
}
