import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts';
import { TrendingUp, Info } from 'lucide-react';
import { WardForecastResponse } from '../../services/forecastService';

interface Props {
  forecastData: WardForecastResponse | null;
  historicalData?: Array<{ date: string; occupancy_percentage: number }>;
  onHorizonChange?: (horizon: number) => void;
  horizon?: number;
}

export const ForecastChart: React.FC<Props> = ({
  forecastData,
  historicalData = [],
  onHorizonChange,
  horizon = 7,
}) => {
  const [showConfidence, setShowConfidence] = useState<boolean>(true);

  if (!forecastData || forecastData.status === 'INSUFFICIENT_DATA') {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-sky-500" />
          <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
            AI Bed Capacity Forecast Chart
          </h3>
        </div>
        <div className="h-64 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
          <Info className="w-8 h-8 text-amber-500 mb-2" />
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            {forecastData?.message || 'Insufficient historical data for reliable forecasting.'}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
            At least 7 daily snapshot observations are required to train time-series models.
          </p>
        </div>
      </div>
    );
  }

  // Combine past historical data + future forecast data for continuous line plotting
  const combinedChartData: any[] = [];

  // Add historical points (PAST)
  historicalData.forEach((item) => {
    combinedChartData.push({
      date: item.date,
      dateLabel: item.date.slice(5),
      actualOccupancy: item.occupancy_percentage,
      forecastOccupancy: null,
      lowerBound: null,
      upperBound: null,
      type: 'PAST',
    });
  });

  // Current today point (transition point)
  const todayStr = new Date().toISOString().slice(0, 10);
  const currentPct = forecastData.current_occupancy_percentage;

  if (combinedChartData.length === 0) {
    combinedChartData.push({
      date: todayStr,
      dateLabel: 'Today',
      actualOccupancy: currentPct,
      forecastOccupancy: currentPct,
      lowerBound: currentPct,
      upperBound: currentPct,
      type: 'TODAY',
    });
  } else {
    // Bridge past and future
    const lastItem = combinedChartData[combinedChartData.length - 1];
    lastItem.forecastOccupancy = lastItem.actualOccupancy;
    lastItem.lowerBound = lastItem.actualOccupancy;
    lastItem.upperBound = lastItem.actualOccupancy;
  }

  // Add future forecast points (FUTURE FORECAST)
  forecastData.forecasts.forEach((item) => {
    combinedChartData.push({
      date: item.date,
      dateLabel: `${item.date.slice(5)} (F)`,
      actualOccupancy: null,
      forecastOccupancy: item.predicted_occupancy_percentage,
      lowerBound: item.lower_bound ?? item.predicted_occupancy_percentage,
      upperBound: item.upper_bound ?? item.predicted_occupancy_percentage,
      boundsRange: [
        item.lower_bound ?? item.predicted_occupancy_percentage,
        item.upper_bound ?? item.predicted_occupancy_percentage,
      ],
      riskLevel: item.risk_level,
      predictedBeds: item.predicted_occupied_beds,
      type: 'FUTURE',
    });
  });

  const todayIndex = combinedChartData.findIndex((x) => x.type === 'TODAY' || x.actualOccupancy !== null);
  const todayLabel = todayIndex >= 0 ? combinedChartData[todayIndex].dateLabel : 'Today';

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-sky-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              7-Day Occupancy Forecast & Confidence Bounds
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Historical Actuals vs {forecastData.model} (v{forecastData.model_version}) Future Predictions
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Horizon Selector Buttons */}
          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 p-1 bg-slate-50 dark:bg-slate-950 text-xs font-semibold">
            {[1, 3, 7].map((h) => (
              <button
                key={h}
                onClick={() => onHorizonChange && onHorizonChange(h)}
                className={`px-3 py-1 rounded-md transition-colors ${
                  horizon === h
                    ? 'bg-sky-500 text-white shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {h}-Day
              </button>
            ))}
          </div>

          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showConfidence}
              onChange={(e) => setShowConfidence(e.target.checked)}
              className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Show 95% Confidence Interval
          </label>
        </div>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={combinedChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
            <XAxis dataKey="dateLabel" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} unit="%" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                borderColor: '#334155',
                borderRadius: '0.5rem',
                color: '#fff',
                fontSize: '12px',
              }}
              formatter={(value: any, name: string) => {
                if (Array.isArray(value)) {
                  return [`${value[0]}% - ${value[1]}%`, '95% Confidence Bounds'];
                }
                if (typeof value === 'number') {
                  return [`${value}%`, name];
                }
                return [value, name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />

            {/* Threshold lines */}
            <ReferenceLine y={85} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'HIGH (85%)', fill: '#f59e0b', fontSize: 10 }} />
            <ReferenceLine y={95} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'CRITICAL (95%)', fill: '#ef4444', fontSize: 10 }} />

            {/* Shaded Confidence Area */}
            {showConfidence && (
              <Area
                type="monotone"
                dataKey="boundsRange"
                name="95% Confidence Interval"
                fill="#38bdf8"
                fillOpacity={0.15}
                stroke="none"
              />
            )}

            {/* Past Actual Occupancy Line */}
            <Line
              type="monotone"
              dataKey="actualOccupancy"
              name="Past Actual Occupancy %"
              stroke="#0284c7"
              strokeWidth={3}
              dot={{ r: 3, fill: '#0284c7' }}
              connectNulls
            />

            {/* Future Forecasted Occupancy Line */}
            <Line
              type="monotone"
              dataKey="forecastOccupancy"
              name="Forecast Occupancy %"
              stroke="#a855f7"
              strokeWidth={3}
              strokeDasharray="5 5"
              dot={{ r: 4, fill: '#a855f7' }}
              activeDot={{ r: 6 }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between">
        <div>
          <span className="font-semibold text-slate-700 dark:text-slate-300">Model: </span>
          {forecastData.model} v{forecastData.model_version} &bull; Generated at:{' '}
          {new Date(forecastData.generated_at).toLocaleString()}
        </div>
        <div className="font-medium text-sky-600 dark:text-sky-400">
          Estimated Range &bull; Not Guaranteed
        </div>
      </div>
    </div>
  );
};
