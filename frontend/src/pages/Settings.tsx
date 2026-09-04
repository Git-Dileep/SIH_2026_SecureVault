import { useEffect, useState } from 'react';
import { getOperator } from '../auth';
import { API_BASE_URL, USE_MOCKS } from '../config';
import { getHealth } from '../api/recovery';
import type { HealthStatus } from '../types';
import PageHeader from '../components/PageHeader';

export default function Settings() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const operator = getOperator();

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'API unreachable');
      });
  }, []);

  return (
    <>
      <PageHeader title="Settings" subtitle="Lab appliance configuration — not a multi-tenant cloud" />

      <div className="grid grid-cols-2 gap-6">
        <div className="card flex flex-col gap-4">
          <h3 className="text-[13px] uppercase tracking-wider text-muted">API connection</h3>
          <div className="grid grid-cols-[140px_1fr] gap-2 text-[13px]">
            <span className="text-muted">Mock data</span>
            <span className="mono" style={{ color: USE_MOCKS ? 'var(--color-warning)' : 'var(--color-success)' }}>
              {USE_MOCKS ? 'ENABLED' : 'DISABLED'}
            </span>
            <span className="text-muted">API base URL</span>
            <span className="mono break-all">{API_BASE_URL}</span>
            <span className="text-muted">Engine</span>
            <span className="mono">{health ? `${health.tool} ${health.version}` : error ? 'unreachable' : 'checking…'}</span>
            <span className="text-muted">Bind</span>
            <span className="mono">{health?.bind ?? '127.0.0.1'}</span>
            <span className="text-muted">Mode</span>
            <span className="mono">{health?.mode ?? 'lab'}</span>
          </div>
          {error && <p className="text-[12px]" style={{ color: 'var(--color-danger)' }}>{error}</p>}
        </div>

        <div className="card flex flex-col gap-4">
          <h3 className="text-[13px] uppercase tracking-wider text-muted">Signed-in operator</h3>
          <div className="grid grid-cols-[140px_1fr] gap-2 text-[13px]">
            <span className="text-muted">User ID</span>
            <span className="mono">{operator}</span>
          </div>
          <p className="text-[12px] text-muted">
            This username and a UTC timestamp are written on every recovery, erasure, classify, and audit block. Sign out from the sidebar.
          </p>
        </div>

        <div className="card flex flex-col gap-4">
          <h3 className="text-[13px] uppercase tracking-wider text-muted">Safety</h3>
          <div className="grid grid-cols-[180px_1fr] gap-2 text-[13px]">
            <span className="text-muted">Firmware erase</span>
            <span className="mono">{health?.firmware_simulated === false ? 'LIVE' : 'SIMULATED'}</span>
            <span className="text-muted">Block devices</span>
            <span className="mono">{health?.safety?.block_devices_refused ? 'REFUSED' : 'unknown'}</span>
            <span className="text-muted">Evidence</span>
            <span className="mono">READ-ONLY</span>
            <span className="text-muted">Audit chain</span>
            <span className="mono" style={{ color: health?.chain?.valid === false ? 'var(--color-danger)' : 'var(--color-success)' }}>
              {health?.chain?.status ?? '—'} (height {health?.chain?.height ?? '—'})
            </span>
            <span className="text-muted">Classifier accuracy</span>
            <span className="mono">
              {health?.classifier?.accuracy != null ? `${Math.round(health.classifier.accuracy * 100)}% measured` : '—'}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
