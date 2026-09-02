import { useEffect, useState } from 'react';
import type { SanitizationResult, SanitizationDevice, SanitizationMethod } from '../types';
import { getErasureJobs, getDevices, startErasure } from '../api/erasure';
import PageHeader from '../components/PageHeader';
import { SanitizationStatusBadge } from '../components/StatusBadge';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

const METHOD_INFO: Record<SanitizationMethod, { label: string; desc: string; passes: string }> = {
  clear: {
    label: 'CLEAR',
    desc: 'Single-pass overwrite with zeros. Suitable for non-sensitive media reuse.',
    passes: '1 pass',
  },
  purge: {
    label: 'PURGE',
    desc: 'Multi-pass overwrite (DoD 5220.22-M). Suitable for sensitive media before reuse or disposal.',
    passes: '3 passes',
  },
  destroy: {
    label: 'DESTROY',
    desc: 'Physical destruction verification logging. Device cannot be reused.',
    passes: 'N/A',
  },
};

export default function ErasureFlow() {
  const [devices, setDevices] = useState<SanitizationDevice[]>([]);
  const [jobs, setJobs] = useState<SanitizationResult[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [selectedDevice, setSelectedDevice] = useState<string>('');
  const [selectedMethod, setSelectedMethod] = useState<SanitizationMethod>('clear');
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    Promise.all([getDevices(), getErasureJobs()])
      .then(([devs, jbs]) => { 
        setDevices(devs); 
        setJobs(jbs);
        if (devs.length > 0) setSelectedDevice(devs[0].name);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleStart = async () => {
    if (!selectedDevice || !selectedMethod) return;
    setStarting(true);
    const job = await startErasure(selectedDevice, selectedMethod);
    setJobs((prev) => [job, ...prev]);
    setStarting(false);
  };

  if (loading) {
    return <div className="p-8 text-[13px] text-muted text-center">Loading erasure module...</div>;
  }

  return (
    <>
      <PageHeader title="Media Sanitization" subtitle="NIST SP 800-88 compliant secure erasure" />

      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* New Job Form */}
        <div className="card col-span-1 flex flex-col h-full border-danger">
          <div className="mb-6 pb-2 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-danger font-semibold">Initiate Sanitization</h3>
          </div>
          
          <div className="flex flex-col gap-4 flex-1">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-muted mb-2">Target Device</label>
              <select 
                className="input" 
                value={selectedDevice} 
                onChange={(e) => setSelectedDevice(e.target.value)}
              >
                {devices.map(d => (
                  <option key={d.name} value={d.name}>{d.name} ({formatBytes(d.capacity_bytes)}) - {d.type}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-muted mb-2">Sanitization Method</label>
              <select 
                className="input" 
                value={selectedMethod} 
                onChange={(e) => setSelectedMethod(e.target.value as SanitizationMethod)}
              >
                {Object.keys(METHOD_INFO).map((m) => (
                  <option key={m} value={m}>{METHOD_INFO[m as SanitizationMethod].label}</option>
                ))}
              </select>
              <div className="mt-2 text-[11px] text-muted p-3 bg-bg-primary border rounded" style={{ borderColor: 'var(--color-border)' }}>
                <strong>{METHOD_INFO[selectedMethod].passes}:</strong> {METHOD_INFO[selectedMethod].desc}
              </div>
            </div>

            <div className="mt-auto pt-6">
              <div className="p-3 mb-4 rounded border" style={{ background: 'var(--color-danger-muted)', borderColor: 'var(--color-danger)', color: 'var(--color-text-primary)' }}>
                <div className="text-[11px] font-bold uppercase mb-1">Warning</div>
                <div className="text-[12px]">This action is irreversible. Data will be permanently destroyed.</div>
              </div>
              <button 
                className="btn btn-danger w-full justify-center mono tracking-wider" 
                onClick={handleStart} 
                disabled={starting || !selectedDevice}
              >
                {starting ? 'EXECUTING...' : 'AUTHORIZE ERASURE'}
              </button>
            </div>
          </div>
        </div>

        {/* Jobs List */}
        <div className="card col-span-2 p-0 overflow-hidden flex flex-col h-full">
          <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted font-medium">Active & Completed Operations</h3>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Target</th>
                  <th>Method</th>
                  <th>Progress</th>
                  <th>Status</th>
                  <th>Verify / Cert</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const progress = job.passes_total > 0
                    ? Math.round((job.passes_completed / job.passes_total) * 100)
                    : job.status === 'completed' ? 100 : 0;
                  return (
                    <tr key={job.id}>
                      <td className="mono text-[12px]">{job.id}</td>
                      <td className="mono text-[12px]">{job.device.name}</td>
                      <td className="mono text-[11px]">{job.method}</td>
                      <td style={{ minWidth: 120 }}>
                        <div className="flex flex-col gap-1">
                          <div className="flex justify-between text-[11px] mono text-muted">
                            <span>{progress}%</span>
                            <span>{job.passes_completed}/{job.passes_total || '-'}</span>
                          </div>
                          <div className="progress-track">
                            <div className="progress-fill" style={{ width: `${progress}%` }} />
                          </div>
                        </div>
                      </td>
                      <td><SanitizationStatusBadge status={job.status} /></td>
                      <td className="text-[12px]">
                        {job.status === 'completed' ? (
                          <div className="flex flex-col gap-1">
                            <span style={{ color: job.verification.passed ? 'var(--color-success)' : 'var(--color-danger)' }}>
                              {job.verification.passed ? 'VERIFIED' : 'FAILED'}
                            </span>
                            {job.certificate_url && (
                              <a href="#" className="mono text-[11px] text-accent hover:underline">CERTIFICATE.PDF</a>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted mono text-[11px]">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
