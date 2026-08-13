import React, { useState, useEffect } from 'react';
import { Layers, ArrowUpRight, ArrowDownRight, ArrowRightLeft } from 'lucide-react';
import { DailySummary } from '../types';
import { getWardDailySummary } from '../services/ingestionService';

interface Props {
  wardId: number;
}

export const WardTrendSummary: React.FC<Props> = ({ wardId }) => {
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      try {
        const data = await getWardDailySummary(wardId);
        if (data && data.length > 0) {
          setSummary(data[data.length - 1]);
        }
      } catch (err) {
        console.error('Failed to fetch ward daily summary:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchSummary();
  }, [wardId]);

  if (loading) {
    return <div className="p-4 text-xs text-slate-400">Loading ward trend summary...</div>;
  }

  if (!summary) {
    return null;
  }

  return (
    <div className="bg-slate-50 dark:bg-slate-950/60 rounded-lg p-4 border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-extrabold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-sky-500" />
          {summary.ward_name} Historical Trend Summary
        </span>
        <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">
          Date: {summary.date}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white dark:bg-slate-900 p-2.5 rounded border border-slate-200 dark:border-slate-800">
          <p className="text-[10px] text-slate-500 uppercase font-bold">Average Occupancy</p>
          <p className="text-sm font-extrabold text-sky-600 dark:text-sky-400">{summary.average_occupancy}%</p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-2.5 rounded border border-slate-200 dark:border-slate-800">
          <p className="text-[10px] text-slate-500 uppercase font-bold">Max / Min Occupancy</p>
          <p className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
            {summary.maximum_occupancy}% / {summary.minimum_occupancy}%
          </p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-2.5 rounded border border-slate-200 dark:border-slate-800">
          <p className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
            <ArrowUpRight className="w-3 h-3 text-emerald-500" /> Admissions / Discharges
          </p>
          <p className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
            {summary.admissions} / {summary.discharges}
          </p>
        </div>

        <div className="bg-white dark:bg-slate-900 p-2.5 rounded border border-slate-200 dark:border-slate-800">
          <p className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
            <ArrowRightLeft className="w-3 h-3 text-indigo-500" /> Transfers (In/Out)
          </p>
          <p className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
            {summary.transfers_in} / {summary.transfers_out}
          </p>
        </div>
      </div>
    </div>
  );
};
