import { useEffect, useState } from 'react';
import { getHealth } from '../api/recovery';

export default function LabBanner() {
  const [text, setText] = useState('LAB APPLIANCE — evidence is read-only; erasure runs on a working COPY; firmware wipe is simulated.');

  useEffect(() => {
    getHealth()
      .then((health) => {
        const chain = health.chain?.valid === false ? ' AUDIT CHAIN TAMPERED.' : '';
        const fw = health.firmware_simulated === false ? ' FIRMWARE ERASE IS LIVE.' : ' Firmware erase is simulated.';
        setText(`LAB APPLIANCE (${health.mode ?? 'lab'}). Evidence read-only.${fw}${chain}`);
      })
      .catch(() => undefined);
  }, []);

  return <div className="lab-banner">{text}</div>;
}
