import { useState, useEffect } from 'react'

interface Device {
  drive_letter: string;
  volume_label: string;
  file_system: string;
  total_bytes: number;
}

interface RecoverySummary {
  total_recovered: number;
  valid_png_count: number;
  image_urls: string[];
}

function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [recovering, setRecovering] = useState<boolean>(false);
  const [summary, setSummary] = useState<RecoverySummary | null>(null);

  const fetchDevices = async () => {
    try {
      const res = await fetch('/api/devices');
      const data = await res.json();
      setDevices(data.devices || []);
    } catch (err) {
      console.error("Failed to fetch devices", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(fetchDevices, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleRecover = async (drive_letter: string) => {
    setRecovering(true);
    setSummary(null);
    try {
      const res = await fetch('/api/recover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drive_letter })
      });
      const data = await res.json();
      if (res.ok) {
        setSummary(data);
      } else {
        alert("Error: " + data.detail);
      }
    } catch (err) {
      alert("Network error occurred.");
    } finally {
      setRecovering(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 GB';
    return (bytes / Math.pow(1024, 3)).toFixed(2) + ' GB';
  };

  return (
    <div className="app-container">
      <header>
        <h1>SecureVault</h1>
        <p className="subtitle">Forensic Pendrive Recovery</p>
      </header>

      {!recovering && !summary && (
        <div className="device-list">
          {loading ? (
             <div className="loader-container">
               <div className="spinner"></div>
               <p>Detecting devices...</p>
             </div>
          ) : devices.length > 0 ? (
            devices.map((dev) => (
              <div className="device-panel" key={dev.drive_letter}>
                <div className="device-info">
                  <h3>Drive {dev.drive_letter}</h3>
                  <p>{dev.volume_label || 'Removable Disk'} • {dev.file_system} • {formatBytes(dev.total_bytes)}</p>
                </div>
                <button 
                  className="primary-btn"
                  onClick={() => handleRecover(dev.drive_letter)}
                >
                  Recover PNGs
                </button>
              </div>
            ))
          ) : (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{opacity: 0.5, marginBottom: '16px'}}>
                <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path>
                <path d="M12 12v9"></path>
                <path d="m8 17 4-4 4 4"></path>
              </svg>
              <h3>No Pendrives Detected</h3>
              <p>Please insert a USB drive to begin.</p>
            </div>
          )}
        </div>
      )}

      {recovering && (
        <div className="loader-container">
          <div className="spinner"></div>
          <h2>Scanning Sectors...</h2>
          <p className="subtitle">Carving forensic PNG files. This might take a moment.</p>
        </div>
      )}

      {summary && !recovering && (
        <div className="results-container">
          <div className="summary-stats">
            <div className="stat">
              <div className="stat-value">{summary.total_recovered}</div>
              <div className="stat-label">Total Found</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{color: 'var(--accent-color)'}}>{summary.valid_png_count}</div>
              <div className="stat-label">Valid CRCs</div>
            </div>
          </div>

          <button className="primary-btn" style={{display: 'block', margin: '0 auto 30px auto'}} onClick={() => setSummary(null)}>
            Scan Another Drive
          </button>

          {summary.image_urls.length > 0 ? (
            <div className="results-grid">
              {summary.image_urls.map((url, idx) => (
                <div className="result-card" key={idx}>
                  <img src={url} alt={`Recovered ${idx}`} loading="lazy" />
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No valid PNG files could be carved from this drive.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
