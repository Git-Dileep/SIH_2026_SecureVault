import { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import type { Evidence } from '../types';
import { getEvidenceList, importEvidence, startRecovery } from '../api/recovery';
import PageHeader from '../components/PageHeader';
import { EvidenceStatusBadge } from '../components/StatusBadge';
import Tooltip from '../components/Tooltip';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function EvidenceImport() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    return getEvidenceList().then(setEvidence);
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    const busy = evidence.some((item) => item.status === 'importing' || item.status === 'analyzing');
    if (!busy) return;
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 800);
    return () => window.clearInterval(timer);
  }, [evidence, refresh]);

  const runImport = useCallback(
    async (input: { file?: File; demo?: boolean }) => {
      setImporting(true);
      setError(null);
      try {
        const result = await importEvidence(input);
        setEvidence((prev) => {
          const rest = prev.filter((item) => item.id !== result.id);
          return [result, ...rest];
        });
        navigate('/recovery/results');
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Import failed');
      } finally {
        setImporting(false);
      }
    },
    [navigate],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) void runImport({ file });
    },
    [runImport],
  );

  const handleRecarve = async (id: string) => {
    setError(null);
    try {
      await startRecovery(id);
      navigate('/recovery/results');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Recovery failed');
    }
  };

  return (
    <>
      <PageHeader
        title="Evidence Library"
        subtitle="Import a raw disk image. The Python carver scans it read-only."
        actions={
          <Tooltip text="Populate a test evidence image">
            <button
              className="btn btn-primary mono text-[12px] hover-lift"
              disabled={importing}
              onClick={() => void runImport({ demo: true })}
            >
              {importing ? 'IMPORTING…' : 'LOAD DEMO IMAGE'}
            </button>
          </Tooltip>
        }
      />

      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        className="hidden"
        accept=".img,.dd,.raw,.bin,.e01,.aff4,.E01,.AFF4"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) void runImport({ file });
        }}
      />

      <Tooltip text="Click to select a file or drag and drop">
        <div
          className={`upload-zone mb-6 ${dragOver ? 'border-accent bg-surface-hover' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          {importing ? (
            <div className="text-[13px] text-muted uppercase tracking-wider">Hashing image and starting carve...</div>
          ) : (
            <div>
              <div className="text-[13px] font-medium mb-1">Click or drag a raw image (.img / .dd / .raw)</div>
              <div className="text-[12px] text-muted mono">Or use Load demo image for testdata/synthetic_disk.img</div>
            </div>
          )}
        </div>
      </Tooltip>

      {/* Evidence table */}
      <div id="library" className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-[13px] text-muted text-center">Loading evidence library...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Evidence ID</th>
                <th>Source Filename</th>
                <th>SHA-256 Hash</th>
                <th>Size</th>
                <th>Type</th>
                <th>Status</th>
                <th>Imported</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {evidence.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-muted text-center py-8">
                    No evidence yet. Load the 64 MiB synthetic demo image to run the carver.
                  </td>
                </tr>
              ) : evidence.map((ev) => (
                <tr key={ev.id}>
                  <td className="mono font-medium text-accent">{ev.id}</td>
                  <td className="truncate max-w-[200px]">{ev.filename}</td>
                  <td className="mono text-muted text-[11px] max-w-[150px] truncate" title={ev.hashes.sha256}>
                    {ev.hashes.sha256}
                  </td>
                  <td className="mono">{formatBytes(ev.size_bytes)}</td>
                  <td className="mono text-[12px]">{ev.format}</td>
                  <td><EvidenceStatusBadge status={ev.status} /></td>
                  <td className="mono text-muted">
                    {new Date(ev.import_timestamp).toISOString().replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="text-[12px]">
                    <div className="flex gap-3">
                      <Tooltip text="View recovery results">
                        <Link to="/recovery/results" className="text-accent hover:underline hover-glow">Results</Link>
                      </Tooltip>
                      <Tooltip text="Run carving algorithm again">
                        <button
                          className="btn-ghost p-0 text-[12px] hover-glow"
                          onClick={() => void handleRecarve(ev.id)}
                          disabled={ev.status === 'analyzing' || ev.status === 'importing'}
                        >
                          Re-carve
                        </button>
                      </Tooltip>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
