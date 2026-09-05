import { useCallback, useRef, useState } from 'react';

export default function FileUpload({
  accept,
  hint,
  disabled,
  onFile,
}: {
  accept?: string;
  hint?: string;
  disabled?: boolean;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const take = useCallback(
    (file?: File | null) => {
      if (file && !disabled) onFile(file);
    },
    [disabled, onFile],
  );

  return (
    <div
      className={`upload-zone ${over ? 'is-over' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accept}
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          take(file);
        }}
      />
      <div className="text-[13px]">{disabled ? 'Working…' : 'Drop a 512-byte fragment or click to upload'}</div>
      {hint && <div className="text-[11px] text-muted mono mt-1">{hint}</div>}
    </div>
  );
}
