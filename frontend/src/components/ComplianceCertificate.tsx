import { apiAssetUrl } from '../api/client';

export default function ComplianceCertificate({
  jobId,
  certificateUrl,
  certificate,
}: {
  jobId?: string;
  certificateUrl?: string | null;
  certificate?: Record<string, unknown> | null;
}) {
  const url = certificateUrl ? apiAssetUrl(certificateUrl) : null;
  const drive = (certificate?.drive as Record<string, unknown> | undefined) ?? {};
  const method = (certificate?.method as Record<string, unknown> | undefined) ?? {};
  const verification = (certificate?.verification as Record<string, unknown> | undefined) ?? {};

  if (!url && !certificate) {
    return <p className="text-[13px] text-muted">No NIST certificate yet. Run a media-aware purge first.</p>;
  }

  return (
    <div className="certificate-frame">
      <div className="text-[11px] uppercase tracking-widest text-muted mb-2">NIST SP 800-88 Rev. 2</div>
      <h3 className="text-[16px] mb-4">Certificate of Media Sanitization</h3>
      <div className="grid grid-cols-[140px_1fr] gap-2 text-[12px] mono">
        <span className="text-muted">ID</span>
        <span>{String(certificate?.certificate_id ?? jobId ?? '—')}</span>
        <span className="text-muted">Drive</span>
        <span>{String(drive.type ?? '—')} · {String(drive.path ?? '—')}</span>
        <span className="text-muted">Method</span>
        <span>{String(method.label ?? method.id ?? '—')}</span>
        <span className="text-muted">NIST level</span>
        <span className="uppercase">{String(method.nist_level ?? '—')}</span>
        <span className="text-muted">Verification</span>
        <span>{verification.passed ? 'PASS' : verification.passed === false ? 'FAIL' : '—'}</span>
      </div>
      {url && (
        <div className="mt-4 flex flex-col gap-3">
          <a className="btn btn-secondary mono text-[12px] no-underline w-fit" href={url} target="_blank" rel="noreferrer">
            DOWNLOAD PDF
          </a>
          <iframe title="NIST certificate" src={url} className="certificate-embed" />
        </div>
      )}
    </div>
  );
}
