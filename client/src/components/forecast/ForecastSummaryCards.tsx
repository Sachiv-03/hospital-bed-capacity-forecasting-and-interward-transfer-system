import React from 'react';
import { Activity, Calendar, AlertTriangle, ShieldCheck, Cpu } from 'lucide-react';
import { WardForecastResponse } from '../../services/forecastService';

interface Props {
  data: WardForecastResponse | null;
  loading?: boolean;
}

export const ForecastSummaryCards: React.FC<Props> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 animate-pulse">
            <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-2/3 mb-3"></div>
            <div className="h-7 bg-slate-200 dark:bg-slate-800 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!data) return null;

  const currentPct = data.current_occupancy_percentage;
  const tomorrowForecast = data.forecasts && data.forecasts.length > 0 ? data.forecasts[0] : null;
  const tomorrowPct = tomorrowForecast ? tomorrowForecast.predicted_occupancy_percentage : currentPct;
  const maxPct = data.max_predicted_occupancy || currentPct;
  const riskLevel = data.max_risk_level || 'NORMAL';
  const modelName = `${data.model} v${data.model_version}`;

  const getRiskBadge = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'HIGH':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'MODERATE':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
      default:
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      {/* Current Occupancy */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
        <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold mb-2">
          <span>Current Occupancy</span>
          <Activity className="w-4 h-4 text-sky-500" />
        </div>
        <div className="text-2xl font-black text-slate-900 dark:text-white">
          {currentPct}%
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          {data.current_occupied_beds} / {data.total_beds} beds occupied
        </div>
      </div>

      {/* Tomorrow Forecast */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
        <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold mb-2">
          <span>Tomorrow Forecast</span>
          <Calendar className="w-4 h-4 text-indigo-500" />
        </div>
        <div className="text-2xl font-black text-slate-900 dark:text-white">
          {tomorrowPct}%
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          {tomorrowForecast ? `Est. ${tomorrowForecast.predicted_occupied_beds} beds` : 'N/A'}
        </div>
      </div>

      {/* 7-Day Maximum */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
        <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold mb-2">
          <span>7-Day Maximum</span>
          <AlertTriangle className="w-4 h-4 text-amber-500" />
        </div>
        <div className="text-2xl font-black text-slate-900 dark:text-white">
          {maxPct}%
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Expected on {data.max_predicted_date || 'N/A'}
        </div>
      </div>

      {/* Predicted Risk */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
        <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold mb-2">
          <span>Predicted Risk</span>
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
        </div>
        <div>
          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-black border ${getRiskBadge(riskLevel)}`}>
            {riskLevel}
          </span>
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-2">
          Future capacity pressure
        </div>
      </div>

      {/* Forecast Model */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs">
        <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold mb-2">
          <span>Forecast Model</span>
          <Cpu className="w-4 h-4 text-purple-500" />
        </div>
        <div className="text-lg font-black text-slate-900 dark:text-white truncate">
          {modelName}
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 truncate">
          Gen: {new Date(data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
};
