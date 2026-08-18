import React from 'react';
import { Route, Routes } from 'react-router-dom';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { DashboardPage } from '../pages/DashboardPage';
import { ForecastPage } from '../pages/ForecastPage';
import { GenericPage } from '../pages/GenericPage';
import { HospitalDetailPage } from '../pages/hospitals/HospitalDetailPage';
import { HospitalsPage } from '../pages/hospitals/HospitalsPage';
import { WardDetailPage } from '../pages/wards/WardDetailPage';
import { WardsPage } from '../pages/wards/WardsPage';
import { TransferDashboardPage } from '../pages/transfers/TransferDashboardPage';

import { LoginPage } from '../pages/auth/LoginPage';

import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { RoleGuard } from '../components/auth/RoleGuard';
import { ForgotPasswordPage } from '../pages/auth/ForgotPasswordPage';
import { RegisterPage } from '../pages/auth/RegisterPage';
import { UnauthorizedPage } from '../pages/auth/UnauthorizedPage';
import { NotFoundPage } from '../pages/NotFoundPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Authentication Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />

      {/* Protected Healthcare SaaS Dashboard Layout */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        {/* Super Admin Hospitals Route */}
        <Route
          path="hospitals"
          element={
            <RoleGuard allowedRoles={['super_admin']}>
              <HospitalsPage />
            </RoleGuard>
          }
        />
        <Route
          path="hospitals/:id"
          element={
            <RoleGuard allowedRoles={['super_admin']}>
              <HospitalDetailPage />
            </RoleGuard>
          }
        />
        <Route
          path="patients"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse', 'receptionist']}>
              <GenericPage
                title="Patients Directory"
                description="Patient admission status, demographic metadata, and bed assignment registry."
                moduleName="Patients Management"
              />
            </RoleGuard>
          }
        />
        <Route
          path="beds"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse']}>
              <GenericPage
                title="Hospital Bed Management"
                description="Real-time bed availability tracking, maintenance statuses, and telemetry."
                moduleName="Bed Capacity"
              />
            </RoleGuard>
          }
        />
        <Route
          path="wards"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse', 'receptionist']}>
              <WardsPage />
            </RoleGuard>
          }
        />
        <Route
          path="wards/:id"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse', 'receptionist']}>
              <WardDetailPage />
            </RoleGuard>
          }
        />

        <Route
          path="forecast"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse', 'receptionist']}>
              <ForecastPage />
            </RoleGuard>
          }
        />

        <Route
          path="transfers"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor', 'nurse']}>
              <TransferDashboardPage />
            </RoleGuard>
          }
        />
        <Route
          path="analytics"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor']}>
              <GenericPage
                title="Operational Analytics"
                description="Hospital length-of-stay (LOS) distributions, bottleneck indicators, and throughput metrics."
                moduleName="Operational Analytics"
              />
            </RoleGuard>
          }
        />
        <Route
          path="reports"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin', 'doctor']}>
              <GenericPage
                title="Capacity & Compliance Reports"
                description="Automated PDF/CSV exports for administrative reporting and regulatory compliance."
                moduleName="Reporting Engine"
              />
            </RoleGuard>
          }
        />
        <Route
          path="settings"
          element={
            <RoleGuard allowedRoles={['super_admin', 'admin']}>
              <GenericPage
                title="System Configuration"
                description="Database pooling options, API parameters, notification webhooks, and threshold settings."
                moduleName="System Settings"
              />
            </RoleGuard>
          }
        />
      </Route>

      {/* 404 Not Found Fallback */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};
