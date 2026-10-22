import React from 'react';
import { useAuth } from '../context/AuthContext';
import { CapacityAlertsSection } from '../components/CapacityAlertsSection';
import { ShieldAlert, Info } from 'lucide-react';

export const AlertsPage: React.FC = () => {
  const { user } = useAuth();
  const hospitalId = user?.hospital_id || 1;

  return (
    <div className="space-y-6">
      {/* Page Title & Context Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-rose-600 to-amber-600 text-white shadow-md shadow-rose-500/20">
              <ShieldAlert className="w-6 h-6 stroke-[2.2]" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                Alerts & Early Warning Command Center
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                Explainable bed capacity risk signals, statistical forecast warnings, and administrative decision support.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Support Advisory Notice */}
      <div className="p-4 rounded-2xl bg-sky-50/70 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800 text-sky-900 dark:text-sky-200 text-xs flex items-start gap-3">
        <Info className="w-5 h-5 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-bold">Clinical & Operational Decision Support Notice</p>
          <p className="opacity-90 leading-relaxed">
            Capacity alerts provide deterministic early warning indicators based on verified physical bed records,
            historical occupancy trends, and approved SARIMA time-series forecasts. This feature is intended for authorized
            clinical staff review and does not initiate automated patient transfers or autonomous medical interventions.
          </p>
        </div>
      </div>

      {/* Main Explainable Alerts Center Component */}
      <CapacityAlertsSection hospitalId={hospitalId} />
    </div>
  );
};

export default AlertsPage;
