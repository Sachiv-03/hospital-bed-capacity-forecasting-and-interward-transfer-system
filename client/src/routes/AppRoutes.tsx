import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { DashboardPage } from '../pages/DashboardPage';
import { GenericPage } from '../pages/GenericPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<DashboardPage />} />
        <Route
          path="patients"
          element={
            <GenericPage
              title="Patients Directory"
              description="Patient admission status, demographic metadata, and bed assignment registry."
              moduleName="Patients Management"
            />
          }
        />
        <Route
          path="beds"
          element={
            <GenericPage
              title="Hospital Bed Management"
              description="Real-time bed availability tracking, maintenance statuses, and telemetry."
              moduleName="Bed Capacity"
            />
          }
        />
        <Route
          path="wards"
          element={
            <GenericPage
              title="Ward Capacity Monitoring"
              description="Departmental ward layouts, ICU occupancy ratios, and staffing thresholds."
              moduleName="Ward Monitoring"
            />
          }
        />
        <Route
          path="forecast"
          element={
            <GenericPage
              title="AI Bed Capacity Forecast"
              description="Predictive Machine Learning models for 24h, 48h, and 7-day occupancy projections."
              moduleName="AI Forecasting"
            />
          }
        />
        <Route
          path="transfers"
          element={
            <GenericPage
              title="Inter-Ward Transfer System"
              description="Intelligent transfer request routing, priority prioritization, and bed matching."
              moduleName="Inter-Ward Transfer"
            />
          }
        />
        <Route
          path="analytics"
          element={
            <GenericPage
              title="Operational Analytics"
              description="Hospital length-of-stay (LOS) distributions, bottleneck indicators, and throughput metrics."
              moduleName="Operational Analytics"
            />
          }
        />
        <Route
          path="reports"
          element={
            <GenericPage
              title="Capacity & Compliance Reports"
              description="Automated PDF/CSV exports for administrative reporting and regulatory compliance."
              moduleName="Reporting Engine"
            />
          }
        />
        <Route
          path="settings"
          element={
            <GenericPage
              title="System Configuration"
              description="Database pooling options, API parameters, notification webhooks, and threshold settings."
              moduleName="System Settings"
            />
          }
        />
      </Route>
    </Routes>
  );
};
