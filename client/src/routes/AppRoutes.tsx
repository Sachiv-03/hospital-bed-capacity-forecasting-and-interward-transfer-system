import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { DashboardPage } from '../pages/DashboardPage';
import { GenericPage } from '../pages/GenericPage';
import { WardsPage } from '../pages/wards/WardsPage';
import { WardDetailPage } from '../pages/wards/WardDetailPage';


import { LoginPage } from '../pages/auth/LoginPage';
import { RegisterPage } from '../pages/auth/RegisterPage';
import { ForgotPasswordPage } from '../pages/auth/ForgotPasswordPage';
import { UnauthorizedPage } from '../pages/auth/UnauthorizedPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { RoleGuard } from '../components/auth/RoleGuard';

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
        
        <Route
          path="patients"
          element={
            <RoleGuard allowedRoles={['admin', 'doctor', 'nurse', 'receptionist']}>
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
            <RoleGuard allowedRoles={['admin', 'doctor', 'nurse']}>
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
            <RoleGuard allowedRoles={['admin', 'doctor', 'nurse', 'receptionist']}>
              <WardsPage />
            </RoleGuard>
          }
        />

        <Route
          path="wards/:id"
          element={
            <RoleGuard allowedRoles={['admin', 'doctor', 'nurse', 'receptionist']}>
              <WardDetailPage />
            </RoleGuard>
          }
        />

        
        <Route
          path="forecast"
          element={
            <RoleGuard allowedRoles={['admin', 'doctor']}>
              <GenericPage
                title="AI Bed Capacity Forecast"
                description="Predictive Machine Learning models for 24h, 48h, and 7-day occupancy projections."
                moduleName="AI Forecasting"
              />
            </RoleGuard>
          }
        />
        
        <Route
          path="transfers"
          element={
            <RoleGuard allowedRoles={['admin', 'doctor', 'nurse']}>
              <GenericPage
                title="Inter-Ward Transfer System"
                description="Intelligent transfer request routing, priority prioritization, and bed matching."
                moduleName="Inter-Ward Transfer"
              />
            </RoleGuard>
          }
        />
        
        <Route
          path="analytics"
          element={
            <RoleGuard allowedRoles={['admin', 'doctor']}>
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
            <RoleGuard allowedRoles={['admin', 'doctor']}>
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
            <RoleGuard allowedRoles={['admin']}>
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
