import { useEffect, useMemo, useState } from 'react';
import type { DriveDetection, SanitizationDevice, SanitizationResult } from '../types';
import { detectDriveType, getDevices, getErasureJobs, importErasureFile, sanitizeDrive } from '../api/erasure';
import DriveTypeBadge from '../components/DriveTypeBadge';
import ComplianceCertificate from '../components/ComplianceCertificate';
import PageHeader from '../components/PageHeader';
import { SanitizationStatusBadge } from '../components/StatusBadge';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function methodFor(type: string): { label: string; passes: number; note: string } {
  if (type === 'HDD') return { label: 'DoD 5220.22-M 7-pass', passes: 7, note: 'User-addressable overwrite is a valid HDD Purge analogue.' };
  if (type === 'SSD') return { label: 'ATA Secure Erase', passes: 1, note: 'Wear-leveling hides 20–30% of NAND. Firmware erase is required.' };
  if (type === 'NVMe') return { label: 'NVMe Format NVM (SES=1)', passes: 1, note: 'Controller erase of all namespaces, including hidden capacity.' };
  return { label: 'NIST Clear overwrite', passes: 1, note: 'File/USB target — working COPY only.' };
}

export default function SSDErasurePage() {
  const [devices, setDevices] = useState<SanitizationDevice[]>([]);
  const [jobs, setJobs] = useState<SanitizationResult[]>([]);
  const [selected, setSelected] = useState('');
  const [detection, setDetection] = useState<DriveDetection | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [passLabel, setPassLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [treatAs, setTreatAs] = useState<'FILE' | 'HDD' | 'SSD' | 'NVMe'>('FILE');

  useEffect(() => {
    Promise.all([getDevices(), getErasureJobs()])
      .then(([devs, jbs]) => {
        setDevices(devs);
        setJobs(jbs);
        if (devs[0]) setSelected(devs[0].name);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load devices'));
  }, []);

  const current = useMemo(() => devices.find((d) => d.name === selected), [devices, selected]);
  const driveType = detection?.drive_type || detection?.type || current?.type || 'UNKNOWN';
  const method = methodFor(driveType);
  const latest = jobs[0];

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const staged = await importErasureFile(file, treatAs);
      const [devs, jbs] = await Promise.all([getDevices(), getErasureJobs()]);
      setDevices(devs);
      setJobs(jbs);
      setSelected(staged.name);
      setDetection(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDetect = async () => {
    if (!selected) return;
    setError(null);
    try {
      const info = await detectDriveType(selected);
      setDetection(info);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Detection failed');
    }
  };

  const handleErase = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    setProgress(8);
    setPassLabel(`Pass 1/${method.passes}`);
    const timer = window.setInterval(() => {
      setProgress((prev) => Math.min(90, prev + 12));
    }, 180);
    try {
      const job = await sanitizeDrive(selected);
      setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
      setProgress(100);
      const total = job.passes_total || method.passes;
      setPassLabel(`Pass ${job.passes_completed}/${total}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sanitization failed');
    } finally {
      window.clearInterval(timer);
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="SSD-Aware Secure Erasure"
        subtitle="Lab mode: detect media, select the NIST method, simulate firmware Purge on a working COPY, emit a labeled prototype certificate."
      />
      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="card flex flex-col gap-4">
          <div className="p-3 text-[12px] border rounded" style={{ borderColor: 'var(--color-border)' }}>
            <strong>Same idea as recovery:</strong> pick a file from this Mac. We copy it into the lab workspace.
            Erasure overwrites that <em>copy</em>. The file on your disk is not deleted or overwritten.
          </div>
          <label className="text-[11px] uppercase tracking-wider text-muted">Upload a local file</label>
          <div className="flex gap-2">
            <select className="input" value={treatAs} onChange={(e) => setTreatAs(e.target.value as typeof treatAs)}>
              <option value="FILE">Treat as file (1-pass Clear)</option>
              <option value="HDD">Treat as HDD (DoD 7-pass)</option>
              <option value="SSD">Treat as SSD (ATA SE analogue)</option>
              <option value="NVMe">Treat as NVMe (Format analogue)</option>
            </select>
          </div>
          <input
            type="file"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) void handleUpload(file);
            }}
          />
          <label className="text-[11px] uppercase tracking-wider text-muted">Or pick a staged / demo target</label>
          <select className="input" value={selected} onChange={(e) => { setSelected(e.target.value); setDetection(null); }}>
            {devices.map((d) => (
              <option key={d.name} value={d.name}>
                {d.type} — {d.name} ({formatBytes(d.capacity_bytes)})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <button className="btn btn-secondary" onClick={() => void handleDetect()} disabled={!selected}>
              Detect Drive Type
            </button>
            <button className="btn btn-danger" onClick={() => void handleErase()} disabled={busy || !selected}>
              {busy ? 'Erasing…' : 'Start Secure Erasure'}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <DriveTypeBadge type={driveType} />
            <span className="text-[12px] text-muted">{method.label}</span>
          </div>
          <p className="text-[12px]">{method.note}</p>
          {(detection?.overprovisioning_risk || current?.overprovisioning_risk) && (
            <div className="p-3 text-[12px] border rounded" style={{ borderColor: 'var(--color-warning)', color: 'var(--color-warning)' }}>
              Overprovisioning risk: host overwrite cannot Purge this media.
            </div>
          )}
          <div>
            <div className="flex justify-between text-[11px] mono text-muted mb-1">
              <span>{passLabel || 'Idle'}</span>
              <span>{progress}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>

        <ComplianceCertificate
          jobId={latest?.id}
          certificateUrl={latest?.certificate_url}
          certificate={latest?.certificate as Record<string, unknown> | undefined}
        />
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
          <h3 className="text-[13px] uppercase tracking-wider text-muted">Jobs</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Drive</th>
              <th>Technique</th>
              <th>Passes</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td className="mono">{job.id}</td>
                <td><DriveTypeBadge type={job.drive_type || job.device.type} /></td>
                <td className="mono text-[11px]">{job.technique || job.method}</td>
                <td className="mono">{job.passes_completed}/{job.passes_total}</td>
                <td><SanitizationStatusBadge status={job.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
