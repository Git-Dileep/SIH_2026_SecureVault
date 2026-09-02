import { useEffect, useState, useCallback } from 'react';
import type { Evidence } from '../types';
import { getEvidenceList, importEvidence } from '../api/recovery';
import PageHeader from '../components/PageHeader';
import { EvidenceStatusBadge } from '../components/StatusBadge';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function EvidenceImport() {
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    getEvidenceList()
      .then(setEvidence)
      .finally(() => setLoading(false));
  }, []);

  const handleImport = useCallback(async (filename: string) => {
    setImporting(true);
    try {
      const result = await importEvidence({
        filename,
        format: filename.endsWith('.E01') ? 'E01' : filename.endsWith('.AFF4') ? 'AFF4' : 'raw',
      });
      setEvidence((prev) => [result, ...prev]);
    } finally {
      setImporting(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleImport(file.name);
    },
    [handleImport]
  );

  return (
    <>
      <PageHeader title="Evidence Library" subtitle="Manage and ingest forensic images" />

      {/* Upload zone */}
      <div
        className={`upload-zone mb-6 ${dragOver ? 'border-accent bg-surface-hover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => handleImport('new_evidence_image.E01')}
      >
        {importing ? (
          <div className="text-[13px] text-muted uppercase tracking-wider">Acquiring Image...</div>
        ) : (
          <div>
            <div className="text-[13px] font-medium mb-1">Click or drag to acquire new evidence image</div>
            <div className="text-[12px] text-muted mono">Supported formats: .E01, .AFF4, .raw, .dd</div>
          </div>
        )}
      </div>

      {/* Evidence table */}
      <div className="card p-0 overflow-hidden">
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
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev) => (
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
