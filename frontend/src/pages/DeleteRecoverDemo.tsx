import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import type { DeleteRecoverDemo, RecoveredFile } from '../types';
import {
  getDeleteRecoverDemo,
  getRecoveryResults,
  runDeleteRecoverDemo,
  uploadDemoExhibit,
} from '../api/recovery';
import { apiAssetUrl, fileUrl } from '../api/client';
import PageHeader from '../components/PageHeader';
import ChainLive from '../components/ChainLive';

function formatBytes(bytes?: number): string {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${(bytes / k ** i).toFixed(1)} ${sizes[i]}`;
}

function isImage(name: string): boolean {
  return /\.(png|jpe?g)$/i.test(name);
}

export default function DeleteRecoverDemoPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [demo, setDemo] = useState<DeleteRecoverDemo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [recoveredFiles, setRecoveredFiles] = useState<RecoveredFile[]>([]);
  const [recoverStatus, setRecoverStatus] = useState<string>('');

  const refresh = () => getDeleteRecoverDemo().then(setDemo);

  useEffect(() => {
    refresh().catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load demo'));
  }, []);

  useEffect(() => {
    if (demo?.phase !== 'recovering' || !demo.evidence_id) return;
    const tick = () =>
      getRecoveryResults()
        .then((res) => {
          setRecoveredFiles(res.files ?? []);
          setRecoverStatus(res.status === 'completed' ? 'completed' : res.message || 'running');
        })
        .catch(() => undefined);
    void tick();
    const timer = window.setInterval(tick, 700);
    return () => window.clearInterval(timer);
  }, [demo?.phase, demo?.evidence_id]);

  const run = async (action: 'stage' | 'delete' | 'recover' | 'reset', extra?: { use_samples?: boolean }) => {
    setBusy(action);
    setError(null);
    try {
      const next = await runDeleteRecoverDemo(action, extra);
      setDemo(next);
      if (action === 'reset') {
        setRecoveredFiles([]);
        setRecoverStatus('');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Demo step failed');
    } finally {
      setBusy(null);
    }
  };

  const addFiles = useCallback(async (list: FileList | File[]) => {
    const files = Array.from(list);
    if (!files.length) return;
    setBusy('upload');
    setError(null);
    try {
      let latest = demo;
      for (const file of files) {
        latest = await uploadDemoExhibit(file);
      }
      if (latest) setDemo(latest);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(null);
    }
  }, [demo]);

  const removeInbox = async (filename: string) => {
    setBusy('remove');
    setError(null);
    try {
      setDemo(await runDeleteRecoverDemo('remove', { filename }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not remove file');
    } finally {
      setBusy(null);
    }
  };

  const phase = demo?.phase ?? 'empty';
  const inbox = demo?.inbox ?? [];
  const folder = demo?.exhibits_folder ?? [];
  const directory = demo?.directory ?? [];
  const planted = demo?.planted ?? [];
  const locked = phase === 'deleted' || phase === 'recovering';
  const canPlant = inbox.length > 0 && !locked && phase !== 'staged';
  const canDelete = (phase === 'staged') && !busy;
  const canRecover = (phase === 'deleted' || phase === 'recovering') && !busy;
  const doneRecover = recoverStatus === 'completed' && recoveredFiles.length > 0;

  return (
    <>
      <PageHeader
        title="Delete, then recover"
        subtitle="Choose your own files on this page. We copy them onto a fake disk, you delete the names, then we carve the bytes back. Nothing on your Desktop is changed."
        actions={
          <button className="btn btn-secondary mono text-[12px]" onClick={() => void run('reset')} disabled={!!busy}>
            START OVER
          </button>
        }
      />
      {error && (
        <div className="mb-4 p-3 text-[13px] border rounded" style={{ borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      <ol className="demo-steps mb-6">
        <li className={phase === 'empty' || phase === 'picking' || phase === 'staged' ? 'is-current' : 'is-done'}>
          <span>1</span> Pick files
        </li>
        <li className={phase === 'staged' ? 'is-current' : phase === 'deleted' || phase === 'recovering' ? 'is-done' : ''}>
          <span>2</span> See them
        </li>
        <li className={phase === 'deleted' ? 'is-current' : phase === 'recovering' ? 'is-done' : ''}>
          <span>3</span> Delete
        </li>
        <li className={phase === 'recovering' || doneRecover ? 'is-current' : ''}>
          <span>4</span> Recover
        </li>
      </ol>

      {/* Step 1 — pick */}
      <div className="card mb-6">
        <h3 className="text-[13px] uppercase tracking-wider text-muted mb-2">Step 1 — Choose files for the fake disk</h3>
        <p className="text-[13px] mb-4">Best results: JPEG, PNG, PDF, ZIP. We copy them; we do not move or delete the originals.</p>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          accept=".jpg,.jpeg,.png,.pdf,.zip,.JPG,.JPEG,.PNG,.PDF,.ZIP"
          onChange={(e) => {
            const list = e.target.files;
            e.target.value = '';
            if (list) void addFiles(list);
          }}
        />
        <div
          className={`upload-zone mb-3 ${dragOver ? 'is-over' : ''}`}
          onClick={() => !locked && fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (!locked) void addFiles(e.dataTransfer.files);
          }}
        >
          <div className="text-[16px] font-medium mb-2">{busy === 'upload' ? 'Adding files…' : 'Choose files from this computer'}</div>
          <div className="text-[13px] text-muted">Click to open Finder, or drag photos/PDFs/ZIPs here. Originals are only copied.</div>
        </div>
        <button
          type="button"
          className="btn btn-primary mb-4"
          disabled={!!busy || locked}
          onClick={() => fileRef.current?.click()}
        >
          Browse files…
        </button>

        {inbox.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {inbox.map((file) => (
              <div key={file.filename} className="file-chip">
                <span className="mono text-[12px]">{file.filename}</span>
                <span className="text-[11px] text-muted">{formatBytes(file.size)}</span>
                {!file.carvable && <span className="text-[11px]" style={{ color: 'var(--color-warning)' }}>may not carve</span>}
                <button className="btn-ghost p-0 text-[12px]" disabled={!!busy || locked} onClick={() => void removeInbox(file.filename)}>remove</button>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button className="btn btn-primary" disabled={!!busy || locked || inbox.length === 0} onClick={() => void run('stage')}>
            {busy === 'stage' ? 'Building image…' : `Build disk image from my files (${inbox.length})`}
          </button>
          <button className="btn btn-secondary" disabled={!!busy || locked} onClick={() => void run('stage', { use_samples: true })}>
            Use built-in case files instead
          </button>
        </div>
        {canPlant && <p className="text-[12px] text-muted mt-2">Ready. Click build to write these onto suspect_disk.img.</p>}
      </div>

      {/* Step 2 — planted view */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b flex justify-between" style={{ borderColor: 'var(--color-border)' }}>
            <div>
              <h3 className="text-[13px] uppercase tracking-wider text-muted">Step 2 — Visible folder</h3>
              <p className="text-[12px] text-muted">Named files the “suspect” still has.</p>
            </div>
            <span className="mono text-[12px]">{folder.length} file(s)</span>
          </div>
          {folder.length === 0 ? (
            <div className="p-6 text-[13px] text-muted">
              {phase === 'deleted' || phase === 'recovering' ? 'Empty after delete — names are gone.' : 'Build the image to fill this folder.'}
            </div>
          ) : (
            <div className="p-4 grid grid-cols-2 gap-3">
              {folder.map((file) => (
                <div key={file.filename} className="border p-3" style={{ borderColor: 'var(--color-border)' }}>
                  <div className="mono text-[12px] truncate">{file.filename}</div>
                  <div className="text-[11px] text-muted">{formatBytes(file.size)}</div>
                  {file.url && isImage(file.filename) && (
                    <img src={apiAssetUrl(file.url)} alt="" className="mt-2 max-h-28 w-full object-contain border" style={{ borderColor: 'var(--color-border)' }} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted">Directory on the image</h3>
            <p className="text-[12px] text-muted">Filename + byte offset. This is what delete wipes.</p>
          </div>
          {directory.length === 0 ? (
            <div className="p-6 text-[13px] text-muted">
              {phase === 'deleted' || phase === 'recovering' ? 'Directory is zeros. Data is still in the image.' : 'No table yet.'}
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Offset</th>
                  <th>Size</th>
                </tr>
              </thead>
              <tbody>
                {directory.map((row) => (
                  <tr key={row.filename}>
                    <td className="mono">{row.filename}</td>
                    <td className="mono">0x{(row.offset ?? 0).toString(16).toUpperCase()}</td>
                    <td className="mono">{formatBytes(row.size)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Step 3 + 4 actions */}
      <div className="card mb-6">
        <h3 className="text-[13px] uppercase tracking-wider text-muted mb-3">Step 3 & 4 — Delete, then recover</h3>
        <p className="text-[13px] mb-4">
          Delete removes the folder and the directory table. Recover carves the raw image. Your original uploads stay on your computer.
        </p>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-danger" disabled={!canDelete} onClick={() => void run('delete')}>
            {busy === 'delete' ? 'Deleting…' : 'Delete exhibits'}
          </button>
          <button className="btn btn-primary" disabled={!canRecover || phase === 'recovering'} onClick={() => void run('recover')}>
            {(busy === 'recover' || (phase === 'recovering' && recoverStatus !== 'completed')) ? 'Recovering…' : 'Recover from image'}
          </button>
          <Link to="/recovery/results" className="btn btn-secondary no-underline">Full recovery page</Link>
        </div>
        {phase === 'recovering' && (
          <div className="mt-4 text-[13px]">
            {recoverStatus === 'completed'
              ? `Done — ${recoveredFiles.length} file(s) carved.`
              : `Carving… ${recoveredFiles.length} found so far.`}
          </div>
        )}
      </div>

      <div className="mb-6">
        <ChainLive refreshKey={`${phase}-${busy ?? ''}-${recoveredFiles.length}`} />
      </div>

      {recoveredFiles.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[13px] uppercase tracking-wider text-muted">Recovered from unallocated space</h3>
          </div>
          <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            {recoveredFiles.map((file) => (
              <div key={file.id} className="border p-3" style={{ borderColor: 'var(--color-border)' }}>
                <div className="mono text-[11px] truncate">{file.filename}</div>
                <div className="text-[11px] text-muted">{file.file_type} · {formatBytes(file.size_bytes)}</div>
                {(file.file_type === 'JPEG' || file.file_type === 'PNG') && (
                  <img src={fileUrl(file.evidence_id, file.filename)} alt="" className="mt-2 max-h-28 w-full object-contain" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {planted.length > 0 && phase !== 'empty' && (
        <p className="text-[12px] text-muted mt-4">
          Image {formatBytes(demo?.image_size)} · source {demo?.source ?? '—'} · {planted.length} planted
        </p>
      )}
    </>
  );
}
