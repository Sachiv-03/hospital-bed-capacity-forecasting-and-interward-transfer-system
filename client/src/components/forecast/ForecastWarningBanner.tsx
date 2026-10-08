import React from 'react';
import { AlertTriangle, ShieldAlert, Info } from 'lucide-react';
import { WardForecastResponse } from '../../services/forecastService';

interface Props {
  forecastData: WardForecastResponse | null;
}

export const ForecastWarningBanner: React.FC<Props> = ({ forecastData }) => {
  if (!forecastData) return null;

  if (forecastData.status === 'INSUFFICIENT_DATA') {
    return (
      <div className="rounded-xl p-4 mb-6 border shadow-xs bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-200">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-white/50 dark:bg-slate-900/50 shrink-0">
            <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="flex-1">
            <h4 className="text-sm font-extrabold uppercase tracking-wider">
              Insufficient Historical Data for Forecasting
            </h4>
            <p className="text-sm font-medium mt-1">
              {forecastData.message || `Ward ${forecastData.ward_name} has insufficient historical daily observations for reliable SARIMA forecasting.`}
            </p>
            <div className="mt-2 flex items-center gap-3 text-xs font-semibold opacity-90">
              <span>Required: {forecastData.required_observations ?? 7} daily observations</span>
              <span>&bull;</span>
              <span>Available: {forecastData.available_observations ?? 0} daily observations</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const maxRisk = forecastData.max_risk_level;
  if (maxRisk !== 'HIGH' && maxRisk !== 'CRITICAL') return null;

  const isCritical = maxRisk === 'CRITICAL';
  const peakDate = forecastData.max_predicted_date || 'upcoming days';
  const peakPct = forecastData.max_predicted_occupancy;

  return (
    <div
      className={`rounded-xl p-4 mb-6 border shadow-xs transition-all ${
        isCritical
          ? 'bg-red-500/10 border-red-500/30 text-red-900 dark:text-red-200'
          : 'bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-200'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-white/50 dark:bg-slate-900/50 shrink-0">
          {isCritical ? (
            <ShieldAlert className="w-6 h-6 text-red-600 dark:text-red-400 animate-pulse" />
          ) : (
            <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400" />
          )}
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-extrabold uppercase tracking-wider">
              ⚠ PREDICTED {maxRisk} CAPACITY WARNING
            </h4>
            <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-white/70 dark:bg-slate-900/70">
              Ward: {forecastData.ward_name}
            </span>
          </div>

          <p className="text-sm font-medium mt-1">
            {forecastData.ward_name} is predicted to reach{' '}
            <span className="font-extrabold">{peakPct}%</span> capacity on{' '}
            <span className="font-extrabold">{peakDate}</span>.
          </p>

          <div className="mt-2 pt-2 border-t border-slate-900/10 dark:border-slate-100/10 flex items-center gap-1.5 text-xs opacity-90">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span>
              Disclaimer: This warning is an automated statistical projection and does not represent a confirmed present event.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
