import { BrowserRouter, Routes, Route } from 'react-router';
import { AuthProvider } from './context/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import RequireAuth from './components/RequireAuth';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import EvidenceImport from './pages/EvidenceImport';
import RecoveryResults from './pages/RecoveryResults';
import ErasureFlow from './pages/ErasureFlow';
import AuditLog from './pages/AuditLog';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import AIClassifier from './pages/AIClassifier';
import AIClassifierPage from './pages/AIClassifierPage';
import SSDErasurePage from './pages/SSDErasurePage';
import AuditChainPage from './pages/AuditChainPage';
import DeleteRecoverDemoPage from './pages/DeleteRecoverDemo';
import Profile from './pages/Profile';
import NotFound from './pages/NotFound';

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/import" element={<EvidenceImport />} />
              <Route path="/demo/delete-recover" element={<DeleteRecoverDemoPage />} />
              <Route path="/recovery/results" element={<RecoveryResults />} />
              <Route path="/erasure" element={<ErasureFlow />} />
              <Route path="/erasure/ssd" element={<SSDErasurePage />} />
              <Route path="/ai" element={<AIClassifier />} />
              <Route path="/ai/classifier" element={<AIClassifierPage />} />
              <Route path="/audit" element={<AuditLog />} />
              <Route path="/audit/chain" element={<AuditChainPage />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
