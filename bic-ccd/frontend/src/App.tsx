import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAppSelector } from './store';
import { getFirstAvailableLandingPage, getRolesForPage } from './utils/helpers';
import { RequireRole } from './components/auth/RequireRole';
import AppLayout from './components/layout/AppLayout';
import LoginPage from './pages/Login/LoginPage';
import DashboardPage from './pages/Dashboard/DashboardPage';
import DataControlPage from './pages/DataControl/DataControlPage';
import ApprovalsPage from './pages/Approvals/ApprovalsPage';
import EvidencePage from './pages/Evidence/EvidencePage';
import VariancePage from './pages/Variance/VariancePage';
import AdminPage from './pages/Admin/AdminPage';
import KriWizardPage from './pages/KriWizard/KriWizardPage';
import KriConfigPage from './pages/KriConfig/KriConfigPage';
import KriOnboardingWizard from './pages/KriConfig/KriOnboardingWizard';
import KriDetailPage from './pages/KriConfig/KriDetailPage';
import ScorecardPage from './pages/Scorecard/ScorecardPage';
import EscalationMetricsPage from './pages/EscalationMetrics/EscalationMetricsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAppSelector((s) => s.auth);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RoleBasedRedirect() {
  const { user } = useAppSelector((s) => s.auth);
  const landingPage = user?.roles ? getFirstAvailableLandingPage(user.roles) : '/dashboard';
  return <Navigate to={landingPage} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
          <Route index element={<RoleBasedRedirect />} />

          <Route path="dashboard" element={
            <RequireRole roles={getRolesForPage('dashboard')}>
              <DashboardPage />
            </RequireRole>
          } />

          <Route path="data-control" element={
            <RequireRole roles={getRolesForPage('data-control')}>
              <DataControlPage />
            </RequireRole>
          } />

          <Route path="approvals" element={
            <RequireRole roles={getRolesForPage('approvals')}>
              <ApprovalsPage />
            </RequireRole>
          } />

          <Route path="evidence" element={
            <RequireRole roles={getRolesForPage('evidence')}>
              <EvidencePage />
            </RequireRole>
          } />

          <Route path="variance" element={
            <RequireRole roles={getRolesForPage('variance')}>
              <VariancePage />
            </RequireRole>
          } />

          <Route path="scorecard" element={
            <RequireRole roles={getRolesForPage('scorecard')}>
              <ScorecardPage />
            </RequireRole>
          } />

          <Route path="escalation-metrics" element={
            <RequireRole roles={getRolesForPage('escalation-metrics')}>
              <EscalationMetricsPage />
            </RequireRole>
          } />

          <Route path="admin" element={
            <RequireRole roles={getRolesForPage('admin')}>
              <AdminPage />
            </RequireRole>
          } />

          <Route path="kri-wizard" element={
            <RequireRole roles={getRolesForPage('kri-wizard')}>
              <KriWizardPage />
            </RequireRole>
          } />

          {/* KRI Config page hidden — routes disabled */}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
