import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle2, ShieldAlert, Zap } from 'lucide-react';
import { CapacityAlert } from '../types';
import { getCapacityAlerts, resolveCapacityAlert } from '../services/ingestionService';

interface Props {
  hospitalId?: number;
}

export const CapacityAlertsSection: React.FC<Props> = ({ hospitalId }) => {
  const [alerts, setAlerts] = useState<CapacityAlert[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await getCapacityAlerts({ hospital_id: hospitalId, status: 'ACTIVE' });
      setAlerts(res.items || []);
    } catch (err) {
      console.error('Failed to fetch capacity alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (alertId: number) => {
    try {
      await resolveCapacityAlert(alertId);
      fetchAlerts();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const timer = setInterval(fetchAlerts, 20_000);
    return () => clearInterval(timer);
  }, [hospitalId]);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-rose-500" />
          <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
            Rule-Based Capacity Alerts
          </h3>
        </div>
        <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
          {alerts.length} Active
        </span>
      </div>

      {loading ? (
        <p className="text-xs text-slate-400 py-4">Checking for capacity alerts...</p>
      ) : alerts.length === 0 ? (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-300">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-500" />
          <div>
            <p className="text-xs font-bold">All Wards Normal</p>
            <p className="text-xs opacity-90">No active capacity alerts or low bed availability warnings.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const isCritical = alert.severity === 'CRITICAL';
            return (
              <div
                key={alert.id}
                className={`p-4 rounded-lg border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                  isCritical
                    ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900 text-rose-900 dark:text-rose-200'
                    : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200'
                }`}
              >
                <div className="flex items-start gap-3">
                  <AlertCircle className={`w-5 h-5 shrink-0 mt-0.5 ${isCritical ? 'text-rose-500' : 'text-amber-500'}`} />
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-2 py-0.5 text-[10px] font-extrabold uppercase rounded-md tracking-wider ${
                          isCritical
                            ? 'bg-rose-600 text-white'
                            : 'bg-amber-600 text-white'
                        }`}
                      >
                        {alert.severity} • {alert.alert_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs font-bold">{alert.ward_name}</span>
                    </div>
                    <p className="text-xs text-slate-700 dark:text-slate-300">{alert.message}</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
                      Triggered value: <span className="font-semibold">{alert.trigger_value}</span> (Threshold: {alert.threshold_value}) • {new Date(alert.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => handleResolve(alert.id)}
                  className="px-3 py-1 text-xs font-bold rounded-md bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors self-end sm:self-center"
                >
                  Resolve Alert
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
