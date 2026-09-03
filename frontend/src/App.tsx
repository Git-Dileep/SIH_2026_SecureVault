import { BrowserRouter, Routes, Route } from 'react-router';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import EvidenceImport from './pages/EvidenceImport';
import RecoveryResults from './pages/RecoveryResults';
import ErasureFlow from './pages/ErasureFlow';
import AuditLog from './pages/AuditLog';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';

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
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
