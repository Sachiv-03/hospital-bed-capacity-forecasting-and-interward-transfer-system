import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { TrendingUp, Calendar, RefreshCw } from 'lucide-react';
import { getHospitalCapacityHistory } from '../services/ingestionService';

interface ChartItem {
  timestamp: string;
  timeLabel: string;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  occupancy_percentage: number;
}

interface Props {
  hospitalId: number;
}

export const HistoricalCapacityChart: React.FC<Props> = ({ hospitalId }) => {
  const [range, setRange] = useState<'today' | '7d' | '30d'>('today');
  const [data, setData] = useState<ChartItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const now = new Date();
      let startDate: Date;
      if (range === 'today') {
        startDate = new Date(now.getFullYear(), now.monthIndex || now.getMonth(), now.getDate());
      } else if (range === '7d') {
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      } else {
        startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      }

      const res = await getHospitalCapacityHistory(hospitalId, {
        start_date: startDate.toISOString(),
        end_date: now.toISOString(),
        limit: 300,
      });

      const formatted: ChartItem[] = (res || []).map((item: any) => {
        const d = new Date(item.timestamp);
        const timeLabel =
          range === 'today'
            ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
        return {
          timestamp: item.timestamp,
          timeLabel,
          total_beds: item.total_beds,
          occupied_beds: item.occupied_beds,
          available_beds: item.available_beds,
          occupancy_percentage: item.occupancy_percentage,
        };
      });

      setData(formatted);
    } catch (err) {
      console.error('Failed to fetch historical capacity:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [hospitalId, range]);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-sky-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Historical Capacity & Occupancy Trend
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Automated occupancy snapshots computed live over time
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 p-1 bg-slate-50 dark:bg-slate-950">
            <button
              onClick={() => setRange('today')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                range === 'today'
                  ? 'bg-sky-500 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Today
            </button>
            <button
              onClick={() => setRange('7d')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                range === '7d'
                  ? 'bg-sky-500 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Last 7 Days
            </button>
            <button
              onClick={() => setRange('30d')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                range === '30d'
                  ? 'bg-sky-500 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Last 30 Days
            </button>
          </div>

          <button
            onClick={fetchHistory}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Refresh chart"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500' : ''}`} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-sm text-slate-400">
          Loading historical capacity trend data...
        </div>
      ) : data.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
          <Calendar className="w-8 h-8 text-slate-400 mb-2" />
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            No historical snapshots recorded yet for this period
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
            Automated snapshot scheduler generates snapshots every 5 minutes. Use the manual trigger button to create an instant snapshot.
          </p>
        </div>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis dataKey="timeLabel" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} unit="%" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '0.5rem',
                  color: '#fff',
                  fontSize: '12px',
                }}
                formatter={(value: any, name: string) => [
                  name === 'occupancy_percentage' ? `${value}%` : value,
                  name === 'occupancy_percentage'
                    ? 'Occupancy Rate'
                    : name === 'occupied_beds'
                    ? 'Occupied Beds'
                    : 'Total Beds',
                ]}
              />
              <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
              <Line
                type="monotone"
                dataKey="occupancy_percentage"
                name="Occupancy %"
                stroke="#0284c7"
                strokeWidth={3}
                dot={{ r: 3, fill: '#0284c7' }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="occupied_beds"
                name="Occupied Beds"
                stroke="#f59e0b"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
