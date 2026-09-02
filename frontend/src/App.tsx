import { BrowserRouter, Routes, Route } from 'react-router';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import EvidenceImport from './pages/EvidenceImport';
import RecoveryResults from './pages/RecoveryResults';
import ErasureFlow from './pages/ErasureFlow';
import AuditLog from './pages/AuditLog';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/import" element={<EvidenceImport />} />
          <Route path="/recovery/results" element={<RecoveryResults />} />
          <Route path="/erasure" element={<ErasureFlow />} />
          <Route path="/audit" element={<AuditLog />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
