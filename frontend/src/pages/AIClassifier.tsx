import { useCallback, useEffect, useRef, useState } from 'react';
import type { AccuracyReport, FragmentClassification } from '../types';
import { classifyFragment, getAccuracy } from '../api/ai';
import PageHeader from '../components/PageHeader';

function hexDump(bytes: Uint8Array, limit = 512): string {
  const slice = bytes.slice(0, limit);
  const lines: string[] = [];
  for (let i = 0; i < slice.length; i += 16) {
    const chunk = slice.slice(i, i + 16);
    const hex = Array.from(chunk).map((b) => b.toString(16).padStart(2, '0')).join(' ');
    const ascii = Array.from(chunk).map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.')).join('');
    lines.push(`${i.toString(16).padStart(8, '0')}  ${hex.padEnd(47, ' ')}  ${ascii}`);
  }
  return lines.join('\n');
}

export default function AIClassifier() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [accuracy, setAccuracy] = useState<AccuracyReport | null>(null);
  const [result, setResult] = useState<FragmentClassification | null>(null);
  const [dump, setDump] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAccuracy().then(setAccuracy).catch(() => undefined);
  }, []);

  const runBytes = useCallback(async (bytes: Uint8Array, file?: File) => {
    setBusy(true);
    setError(null);
    setDump(hexDump(bytes));
    try {
      const hex = Array.from(bytes.slice(0, 512)).map((b) => b.toString(16).padStart(2, '0')).join('');
      const classified = file
        ? await classifyFragment({ file })
        : await classifyFragment({ hex });
      setResult(classified);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Classification failed');
    } finally {
      setBusy(false);
    }
  }, []);

  const onFile = async (file: File) => {
    const buf = new Uint8Array(await file.arrayBuffer());
    await runBytes(buf.slice(0, 512), file);
  };

  const perClass = accuracy?.per_class ?? {};
  const acc = accuracy?.accuracy != null ? Math.round(accuracy.accuracy * 100) : null;
  const baseline = accuracy?.baseline_signature_only != null ? Math.round(accuracy.baseline_signature_only * 100) : 62;

  return (
    <>
      <PageHeader
        title="AI Fragment Classifier"
        subtitle="512-byte windows → file type. Signature carvers stall at 60–65%; this MLP+heuristic prior targets the 90%+ band."
      />

      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Model accuracy</div>
          <div className="text-[28px] font-mono" style={{ color: 'var(--color-success)' }}>{acc != null ? `${acc}%` : '—'}</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Signature-only baseline</div>
          <div className="text-[28px] font-mono">{baseline}%</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Keep threshold</div>
          <div className="text-[28px] font-mono">{Math.round((accuracy?.threshold ?? 0.7) * 100)}%</div>
        </div>
        <div className="card">
          <div className="text-[11px] uppercase tracking-wider text-muted">Window</div>
          <div className="text-[28px] font-mono">{accuracy?.fragment_size ?? 512} B</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="card">
          <h3 className="text-[13px] uppercase tracking-wider text-muted mb-3">Classify a fragment</h3>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) void onFile(file);
            }}
          />
          <div className="upload-zone mb-4" onClick={() => fileRef.current?.click()}>
            <div className="text-[13px]">{busy ? 'Classifying…' : 'Drop or click a file — first 512 bytes are scored'}</div>
            <div className="text-[11px] text-muted mono mt-1">jpg png pdf zip docx xlsx mp4 mp3 txt exe</div>
          </div>
          {result && (
            <div>
              <div className="flex items-end gap-3 mb-2">
                <div className="text-[24px] font-mono">{result.display_type}</div>
                <div className="mono" style={{ color: result.below_threshold ? 'var(--color-danger)' : 'var(--color-success)' }}>
                  {Math.round(result.confidence * 100)}% {result.below_threshold ? 'REJECTED' : 'KEEP'}
                </div>
              </div>
              <div className="text-[12px] text-muted mb-3">
                entropy {result.entropy.toFixed(2)} bits/byte · {result.method}
              </div>
              <div className="space-y-1">
                {Object.entries(result.scores).sort((a, b) => b[1] - a[1]).map(([label, score]) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className="mono w-12 text-[11px]">{label}</span>
                    <div className="progress-track flex-1">
                      <div className="progress-fill" style={{ width: `${Math.round(score * 100)}%` }} />
                    </div>
                    <span className="mono text-[11px] w-10 text-right">{Math.round(score * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted">Per-class hold-out accuracy</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Accuracy</th>
              </tr>
            </thead>
            <tbody>
              {(accuracy?.types ?? Object.keys(perClass)).map((label) => (
                <tr key={label}>
                  <td className="mono">{label}</td>
                  <td className="mono">{perClass[label] != null ? `${Math.round(perClass[label] * 100)}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {accuracy?.notes && (
            <p className="p-4 text-[12px] text-muted">{accuracy.notes}</p>
          )}
        </div>
      </div>

      {dump && (
        <div className="card">
          <h3 className="text-[13px] uppercase tracking-wider text-muted mb-3">512-byte window</h3>
          <pre className="mono text-[11px] overflow-x-auto" style={{ color: 'var(--color-text-secondary)' }}>{dump}</pre>
        </div>
      )}
    </>
  );
}
