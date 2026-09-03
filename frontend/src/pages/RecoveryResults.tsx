import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import {
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { RecoveredFile, RecoveryResultsResponse } from '../types';
import { getRecoveryResults } from '../api/recovery';
import { fileUrl, reportUrl } from '../api/client';
import PageHeader from '../components/PageHeader';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function getConfidenceBar(score: number): string {
  const totalBlocks = 20;
  const filledBlocks = Math.round(score * totalBlocks);
  const emptyBlocks = totalBlocks - filledBlocks;
  return '█'.repeat(filledBlocks) + '░'.repeat(emptyBlocks);
}

function FileRow({ file }: { file: RecoveredFile }) {
  const [expanded, setExpanded] = useState(false);
  const score = Math.round(file.confidence_score * 100);
  
  const statusColor = score >= 80 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
  const label = file.confidence_label.toUpperCase();

  return (
    <>
      <tr
        className="cursor-pointer group"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="w-1/3">
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-muted" />
            <span className="font-medium truncate max-w-[250px]">{file.filename}</span>
          </div>
        </td>
        <td className="w-1/6 mono">{file.file_type}</td>
        <td className="w-1/6 mono">{formatBytes(file.size_bytes)}</td>
        <td className="w-1/6">
          <div className="flex flex-col">
            <span className="mono text-[12px]">{score} / 100</span>
          </div>
        </td>
        <td className="w-1/6">
          <span className="mono font-semibold" style={{ color: statusColor }}>{label}</span>
        </td>
        <td className="w-8">
          {expanded ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} style={{ padding: 0 }}>
            <div className="px-6 py-6" style={{
              background: 'var(--color-bg-elevated)',
              borderBottom: '1px solid var(--color-border)',
            }}>
              <div className="grid grid-cols-2 gap-8">
                {/* Score & Checks */}
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-muted mb-2">Recovery Confidence</h4>
                  <div className="flex items-end gap-3 mb-2">
                    <span className="text-[24px] font-mono leading-none">{score} <span className="text-[14px] text-muted">/ 100</span></span>
                    <span className="font-mono font-bold" style={{ color: statusColor }}>{label}</span>
                  </div>
                  <div className="mono text-[12px] mb-4 text-muted" style={{ letterSpacing: '2px' }}>
                    {getConfidenceBar(file.confidence_score)}
                  </div>
                  <div className="space-y-1.5 mono text-[12px]">
                    <div className="flex gap-2"><span style={{ color: file.integrity_checks.header_valid ? 'var(--color-success)' : 'var(--color-danger)' }}>{file.integrity_checks.header_valid ? '✓' : '✗'}</span> File signature</div>
                    <div className="flex gap-2"><span style={{ color: file.integrity_checks.structure_valid ? 'var(--color-success)' : 'var(--color-danger)' }}>{file.integrity_checks.structure_valid ? '✓' : '✗'}</span> Header structure</div>
                    <div className="flex gap-2"><span style={{ color: file.integrity_checks.footer_valid ? 'var(--color-success)' : 'var(--color-danger)' }}>{file.integrity_checks.footer_valid ? '✓' : '✗'}</span> File decoding</div>
                  </div>
                </div>

                {/* AI Assessment */}
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-muted mb-2">Analysis Assessment</h4>
                  <div className="space-y-2 text-[13px] mb-4">
                    <div className="grid grid-cols-[100px_1fr]">
                      <span className="text-muted">Classification:</span>
                      <span className="mono">{file.file_type}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr]">
                      <span className="text-muted">Integrity:</span>
                      <span className="mono">{label}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr]">
                      <span className="text-muted">Method:</span>
                      <span className="mono">{file.recovery_method}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr]">
                      <span className="text-muted">Offset:</span>
                      <span className="mono">0x{file.offset.toString(16).toUpperCase()}</span>
                    </div>
                  </div>
                  <p className="text-[12px] leading-relaxed border-l-2 pl-3" style={{ borderColor: 'var(--color-border)' }}>
                    {file.ai_explanation}
                  </p>
                  {(file.file_type === 'JPEG' || file.file_type === 'PNG') && (
                    <img
                      src={fileUrl(file.evidence_id, file.filename)}
                      alt={file.filename}
                      className="mt-4 max-h-40 border"
                      style={{ borderColor: 'var(--color-border)' }}
                    />
                  )}
                  <a
                    href={fileUrl(file.evidence_id, file.filename)}
                    className="inline-block mt-3 text-[12px] mono text-accent hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    DOWNLOAD FILE
                  </a>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function RecoveryResults() {
  const [data, setData] = useState<RecoveryResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = () =>
      getRecoveryResults()
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch((err: unknown) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load recovery results');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });

    void tick();
    const timer = window.setInterval(() => {
      if (cancelled) return;
      void getRecoveryResults()
        .then((result) => {
          if (cancelled) return;
          setData(result);
          if (result.status && result.status !== 'running') {
            window.clearInterval(timer);
          }
        })
        .catch(() => undefined);
    }, 800);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (loading) {
    return <div className="p-8 text-[13px] text-muted">Loading results...</div>;
  }

  if (error) {
    return <div className="p-8 text-[13px] text-danger">{error}</div>;
  }

  if (!data || data.status === 'idle' || !data.session_id) {
    return (
      <>
        <PageHeader title="Recovery Operations" subtitle="No carving session yet" />
        <div className="card max-w-[560px]">
          <p className="text-[13px] mb-4">Import a raw disk image to run the signature carver.</p>
          <Link to="/import" className="btn btn-primary no-underline">Open evidence import</Link>
        </div>
      </>
    );
  }

  const high = data.files.filter((f) => f.confidence_label === 'high').length;
  const medium = data.files.filter((f) => f.confidence_label === 'medium').length;
  const low = data.files.filter((f) => f.confidence_label === 'low').length;

  return (
    <>
      <PageHeader
        title="Recovery Operations"
        subtitle={`Session: ${data.session_id} • Target: ${data.evidence_id}${data.message ? ` • ${data.message}` : ''}`}
        actions={
          data.evidence_id ? (
            <a
              className="btn btn-secondary mono text-[12px] no-underline"
              href={reportUrl(data.evidence_id, 'html')}
              target="_blank"
              rel="noreferrer"
            >
              HTML REPORT
            </a>
          ) : null
        }
      />

      {/* Process Tracker */}
      <div className="card mb-8 p-6">
        <div className="flex justify-between items-center mb-2">
          {['01 Evidence', '02 Scan', '03 Extract', '04 Analyse', '05 Report'].map((step, idx) => {
            const doneSteps = data.status === 'completed' ? 5 : data.status === 'running' ? Math.min(4, Math.floor((data.progress ?? 0) * 5)) : 0;
            return (
            <div key={step} className="flex-1 flex flex-col gap-2">
              <span className={`text-[11px] font-mono uppercase tracking-wider ${idx < doneSteps ? 'text-primary' : 'text-muted'}`}>
                {step}
              </span>
              <div className="h-1 mr-2" style={{ background: idx < doneSteps - 1 ? 'var(--color-success)' : idx === doneSteps - 1 ? 'var(--color-accent)' : 'var(--color-border)' }} />
            </div>
            );
          })}
        </div>
        <div className="mt-6 grid grid-cols-6 gap-4 border-t pt-4" style={{ borderColor: 'var(--color-border)' }}>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Sectors</div>
            <div className="mono text-[14px]">{data.image_size_bytes ? Math.round(data.image_size_bytes / 512).toLocaleString() : '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Detected</div>
            <div className="mono text-[14px]">{data.total_files}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Recovered</div>
            <div className="mono text-[14px]">{data.total_files}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">High Conf</div>
            <div className="mono text-[14px]" style={{ color: 'var(--color-success)' }}>{high}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Medium Conf</div>
            <div className="mono text-[14px]" style={{ color: 'var(--color-warning)' }}>{medium}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Low Conf</div>
            <div className="mono text-[14px]" style={{ color: 'var(--color-danger)' }}>{low}</div>
          </div>
        </div>
      </div>

      {/* Results table */}
      <div id="files" className="card p-0 overflow-hidden">
        <div className="p-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border)' }}>
          <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted">Recovered Files Analysis</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>File Type</th>
              <th>Size</th>
              <th>Confidence</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.files.map((file) => (
              <FileRow key={file.id} file={file} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
