import { useEffect, useMemo, useState } from 'react';
import type { SanitizationResult, SanitizationDevice, SanitizationMethod } from '../types';
import { detectDriveType, getErasureJobs, getDevices, importErasureFile, startErasure } from '../api/erasure';
import { apiAssetUrl } from '../api/client';
import PageHeader from '../components/PageHeader';
import { SanitizationStatusBadge } from '../components/StatusBadge';
import DriveTypeBadge from '../components/DriveTypeBadge';
import ComplianceCertificate from '../components/ComplianceCertificate';
import type { DriveDetection } from '../types';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

const METHOD_INFO: Record<string, { label: string; desc: string; passes: string }> = {
  auto: {
    label: 'MEDIA-AWARE (NIST 800-88)',
    desc: 'Detect HDD / SSD / NVMe and select the Purge command that actually covers the media. SSDs do not get HDD overwrite.',
    passes: 'auto',
  },
  clear: {
    label: 'CLEAR',
    desc: 'Single-pass overwrite of user-addressable LBAs. NIST Clear only — not sufficient Purge for SSD/NVMe.',
    passes: '1 pass',
  },
  purge: {
    label: 'PURGE (alias of media-aware)',
    desc: 'Same as media-aware: DoD 7-pass on HDD, ATA Secure Erase on SSD, NVMe Format NVM on NVMe.',
    passes: 'media-dependent',
  },
  destroy: {
    label: 'DESTROY',
    desc: 'Physical destruction verification logging. Device cannot be reused. Not performed by software.',
    passes: 'N/A',
  },
};

function techniqueFor(device?: SanitizationDevice): string {
  if (!device) return 'Detecting…';
  if (device.type === 'HDD') return 'DoD 5220.22-M 7-pass overwrite';
  if (device.type === 'SSD') return 'ATA Secure Erase (covers overprovisioned NAND)';
  if (device.type === 'NVMe') return 'NVMe Format NVM (SES=1 User Data Erase)';
  return 'Overwrite (USB/file target)';
}

export default function ErasureFlow() {
  const [devices, setDevices] = useState<SanitizationDevice[]>([]);
  const [jobs, setJobs] = useState<SanitizationResult[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedDevice, setSelectedDevice] = useState<string>('');
  const [selectedMethod, setSelectedMethod] = useState<SanitizationMethod>('auto');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detection, setDetection] = useState<DriveDetection | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    Promise.all([getDevices(), getErasureJobs()])
      .then(([devs, jbs]) => {
        setDevices(devs);
        setJobs(jbs);
        if (devs.length > 0) setSelectedDevice(devs[0].name);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load erasure module');
      })
      .finally(() => setLoading(false));
  }, []);

  const current = useMemo(
    () => devices.find((d) => d.name === selectedDevice),
    [devices, selectedDevice],
  );

  const handleStart = async () => {
    if (!selectedDevice || !selectedMethod) return;
    setStarting(true);
    setError(null);
    try {
      const job = await startErasure(selectedDevice, selectedMethod);
      setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erasure failed');
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-[13px] text-muted text-center">Loading erasure module...</div>;
  }

  return (
    <>
      <PageHeader
        title="SSD-Aware Media Sanitization"
        subtitle="NIST SP 800-88 Rev. 2 — HDD overwrite, ATA Secure Erase, NVMe Format NVM. Working COPY only."
      />
      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { t: 'HDD', d: 'DoD 5220.22-M 7-pass. User LBAs are the whole story.' },
          { t: 'SSD', d: 'Wear-leveling hides 20–30% of NAND. ATA Secure Erase is required for Purge.' },
          { t: 'NVMe', d: 'NVMe Format NVM SES=1 erases namespaces including hidden capacity.' },
        ].map((card) => (
          <div key={card.t} className="card">
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Detected media</div>
            <div className="text-[18px] font-mono mb-2">{card.t}</div>
            <p className="text-[12px]">{card.d}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="card col-span-1 flex flex-col h-full border-danger">
          <div className="mb-6 pb-2 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-danger font-semibold">Initiate Sanitization</h3>
          </div>

          <div className="flex flex-col gap-4 flex-1">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-muted mb-2">Upload a file from this disk</label>
              <input
                type="file"
                className="mb-2 text-[12px]"
                disabled={uploading || starting}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = '';
                  if (!file) return;
                  setUploading(true);
                  setError(null);
                  void importErasureFile(file, 'FILE')
                    .then(async (staged) => {
                      const [devs, jbs] = await Promise.all([getDevices(), getErasureJobs()]);
                      setDevices(devs);
                      setJobs(jbs);
                      setSelectedDevice(staged.name);
                      setDetection(null);
                    })
                    .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Upload failed'))
                    .finally(() => setUploading(false));
                }}
              />
              <p className="text-[11px] text-muted mb-3">Your original file stays intact. We stage a copy, then overwrite that copy.</p>
              <label className="block text-[11px] uppercase tracking-wider text-muted mb-2">Target (copy only)</label>
              <select
                className="input"
                value={selectedDevice}
                onChange={(e) => {
                  setSelectedDevice(e.target.value);
                  setDetection(null);
                }}
              >
                {devices.map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.type} — {d.name} ({formatBytes(d.capacity_bytes)})
                  </option>
                ))}
              </select>
            </div>

            <button className="btn btn-secondary w-fit" type="button" onClick={() => selectedDevice && void detectDriveType(selectedDevice).then(setDetection).catch((err: unknown) => setError(err instanceof Error ? err.message : 'Detect failed'))}>
              Detect drive type
            </button>
            {current && (
              <div className="text-[11px] mono p-3 border rounded" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-primary)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <DriveTypeBadge type={detection?.drive_type || current.type} />
                  <span>{techniqueFor({ ...current, type: (detection?.drive_type as SanitizationDevice['type']) || current.type })}</span>
                </div>
                <div>TYPE {detection?.drive_type || current.type} · {current.protocol ?? 'file'}</div>
                <div>SERIAL {current.serial}</div>
                <div className="mt-2" style={{ color: current.overprovisioning_risk ? 'var(--color-warning)' : 'var(--color-success)' }}>
                  {current.overprovisioning_risk
                    ? 'OVERPROVISIONING RISK — overwrite will not Purge this media'
                    : 'Rotational media — overwrite reaches user-addressable LBAs'}
                </div>
                <div className="mt-2 text-muted">{techniqueFor(current)}</div>
              </div>
            )}

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-muted mb-2">Sanitization Method</label>
              <select
                className="input"
                value={selectedMethod}
                onChange={(e) => setSelectedMethod(e.target.value as SanitizationMethod)}
              >
                {Object.keys(METHOD_INFO).map((m) => (
                  <option key={m} value={m}>{METHOD_INFO[m].label}</option>
                ))}
              </select>
              <div className="mt-2 text-[11px] text-muted p-3 bg-bg-primary border rounded" style={{ borderColor: 'var(--color-border)' }}>
                <strong>{METHOD_INFO[selectedMethod].passes}:</strong> {METHOD_INFO[selectedMethod].desc}
              </div>
            </div>

            <div className="mt-auto pt-6">
              <div className="p-3 mb-4 rounded border" style={{ background: 'var(--color-danger-muted)', borderColor: 'var(--color-danger)', color: 'var(--color-text-primary)' }}>
                <div className="text-[11px] font-bold uppercase mb-1">Warning</div>
                <div className="text-[12px]">A working COPY is overwritten. Original files and real /dev devices are never touched. Firmware commands are simulated.</div>
              </div>
              <button
                className="btn btn-danger w-full justify-center mono tracking-wider"
                onClick={() => void handleStart()}
                disabled={starting || !selectedDevice}
              >
                {starting ? 'SANITIZING…' : 'AUTHORIZE NIST PURGE'}
              </button>
            </div>
          </div>
        </div>

        <div className="card col-span-2 p-0 overflow-hidden flex flex-col h-full">
          <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted font-medium">Operations & NIST certificates</h3>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Target</th>
                  <th>Drive</th>
                  <th>Technique</th>
                  <th>NIST</th>
                  <th>Status</th>
                  <th>Certificate</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-muted">No sanitization jobs yet. Run media-aware Purge on a virtual HDD/SSD/NVMe target.</td>
                  </tr>
                ) : jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="mono text-[12px]">{job.id}</td>
                    <td className="mono text-[12px] truncate max-w-[160px]">{job.device.name}</td>
                    <td><DriveTypeBadge type={job.drive_type || job.device.type} /></td>
                    <td className="mono text-[11px]">{job.technique || job.method}</td>
                    <td className="mono text-[11px] uppercase">{job.nist_level || job.method}</td>
                    <td><SanitizationStatusBadge status={job.status} /></td>
                    <td className="text-[12px]">
                      {job.status === 'completed' ? (
                        <div className="flex flex-col gap-1">
                          <span style={{ color: job.verification.passed ? 'var(--color-success)' : 'var(--color-danger)' }}>
                            {job.verification.passed ? 'VERIFIED' : 'FAILED'}
                          </span>
                          {job.certificate_url && (
                            <a href={apiAssetUrl(job.certificate_url)} className="mono text-[11px] text-accent hover:underline" target="_blank" rel="noreferrer">
                              NIST CERT.PDF
                            </a>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted mono text-[11px]">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {jobs[0] && (
        <ComplianceCertificate
          jobId={jobs[0].id}
          certificateUrl={jobs[0].certificate_url}
          certificate={jobs[0].certificate as Record<string, unknown> | undefined}
        />
      )}
    </>
  );
}
