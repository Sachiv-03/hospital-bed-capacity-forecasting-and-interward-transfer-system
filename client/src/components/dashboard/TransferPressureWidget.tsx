import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightLeft, ShieldAlert, ArrowRight, Activity } from 'lucide-react';
import { TransferOverviewStats } from '../../types';
import { transferService } from '../../services/transferService';

interface TransferPressureWidgetProps {
  hospitalId?: number;
}

export const TransferPressureWidget: React.FC<TransferPressureWidgetProps> = ({ hospitalId }) => {
  const [stats, setStats] = useState<TransferOverviewStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetchStats();
  }, [hospitalId]);

  const fetchStats = async () => {
    try {
      const data = await transferService.getOverviewStats(hospitalId);
      setStats(data);
    } catch (err) {
      // Silent error fallback
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs animate-pulse">
        <div className="h-5 w-40 bg-slate-200 dark:bg-slate-800 rounded mb-3"></div>
        <div className="h-10 bg-slate-100 dark:bg-slate-800/60 rounded"></div>
      </div>
    );
  }

  const hasHighPressure = stats.critical_pressure_wards > 0 || stats.high_pressure_wards > 0;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400">
            <ArrowRightLeft className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Inter-Ward Transfer Decision Support
            </h3>
            <p className="text-xs text-slate-500">Real-time capacity relief recommendations</p>
          </div>
        </div>

        <Link
          to="/transfers"
          className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300"
        >
          Open Dashboard
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-3 p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
        <div>
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
            Critical Pressure
          </div>
          <div className="text-lg font-extrabold text-rose-600 dark:text-rose-400">
            {stats.critical_pressure_wards} Wards
          </div>
        </div>

        <div>
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
            High Pressure
          </div>
          <div className="text-lg font-extrabold text-amber-600 dark:text-amber-400">
            {stats.high_pressure_wards} Wards
          </div>
        </div>

        <div>
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
            Pending Recommendations
          </div>
          <div className="text-lg font-extrabold text-sky-600 dark:text-sky-400">
            {stats.pending_recommendations}
          </div>
        </div>
      </div>

      {hasHighPressure ? (
        <div className="mt-3 flex items-center justify-between text-xs text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 rounded-lg border border-amber-200/60 dark:border-amber-900/40">
          <span className="flex items-center gap-1.5 font-medium">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
            Capacity relief recommendations available for review.
          </span>
          <Link to="/transfers" className="font-bold underline hover:no-underline">
            Review
          </Link>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2 rounded-lg border border-emerald-200/60 dark:border-emerald-900/40">
          <span>All ward capacities are operating within normal thresholds.</span>
        </div>
      )}
    </div>
  );
};
