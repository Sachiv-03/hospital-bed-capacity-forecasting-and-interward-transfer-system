import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Ward } from '../types';
import { getWards } from '../services/wardService';
import { forecastService, WardForecastResponse } from '../services/forecastService';
import { ForecastSummaryCards } from '../components/forecast/ForecastSummaryCards';
import { ForecastChart } from '../components/forecast/ForecastChart';
import { ForecastWarningBanner } from '../components/forecast/ForecastWarningBanner';
import { ModelPerformanceCard } from '../components/forecast/ModelPerformanceCard';
import { HospitalForecastOverview } from '../components/forecast/HospitalForecastOverview';
import { TrendingUp, RefreshCw, Cpu, CheckCircle2, AlertCircle, Play } from 'lucide-react';

export const ForecastPage: React.FC = () => {
  const { user } = useAuth();
  const hospitalId = user?.hospital_id || 1;
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  const [wards, setWards] = useState<Ward[]>([]);
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);
  const [horizon, setHorizon] = useState<number>(7);

  const [forecastData, setForecastData] = useState<WardForecastResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load Wards List
  useEffect(() => {
    getWards({ limit: 100 })
      .then((res) => {
        setWards(res.items);
        if (res.items.length > 0 && !selectedWardId) {
          setSelectedWardId(res.items[0].id);
        }
      })
      .catch((err) => console.error('Failed to load wards for forecasting:', err));
  }, []);

  // Fetch Ward Forecast Data
  const fetchForecast = useCallback(async () => {
    if (!selectedWardId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await forecastService.getWardForecast(selectedWardId, horizon);
      setForecastData(res);
    } catch (err: any) {
      console.error('Failed to fetch forecast:', err);
      setError(err?.response?.data?.detail || 'Failed to load bed capacity forecast.');
    } finally {
      setLoading(false);
    }
  }, [selectedWardId, horizon]);

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  // Handle Manual Forecast Trigger (Admin)
  const handleManualGenerate = async () => {
    setGenerating(true);
    try {
      const res = await forecastService.generateManualForecast(hospitalId, horizon);
      setToastMessage(`Forecast pipeline executed successfully! (${res.forecasts_generated} forecasts generated).`);
      setTimeout(() => setToastMessage(null), 4000);
      fetchForecast();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to run manual forecast generation.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Toast Banner */}
      {toastMessage && (
        <div className="p-4 rounded-xl shadow-lg border bg-emerald-50 dark:bg-emerald-950/90 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="text-sm font-semibold">{toastMessage}</span>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
              <Cpu className="w-3.5 h-3.5" />
              Stage 3 — Time-Series Forecasting Engine
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-sky-600 dark:text-sky-400" />
            AI Bed Capacity Forecast
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Predictive SARIMA & Moving Average models for 1-day, 3-day, and 7-day hospital occupancy projections.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isAdmin && (
            <button
              onClick={handleManualGenerate}
              disabled={generating}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm text-white bg-purple-600 hover:bg-purple-500 shadow-md shadow-purple-600/20 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
            >
              <Play className={`w-4 h-4 fill-white ${generating ? 'animate-spin' : ''}`} />
              <span>{generating ? 'Running Pipeline...' : 'Run Forecast Job'}</span>
            </button>
          )}

          <button
            onClick={fetchForecast}
            className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            title="Refresh Forecast"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500' : ''}`} />
          </button>
        </div>
      </div>

      {/* Ward & Horizon Controls */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider shrink-0">
            Select Ward:
          </label>
          <select
            value={selectedWardId || ''}
            onChange={(e) => setSelectedWardId(Number(e.target.value))}
            className="w-full sm:w-64 px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-bold"
          >
            {wards.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.ward_type}) &bull; {w.capacity} beds
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Horizon:
          </span>
          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 p-1 bg-slate-50 dark:bg-slate-950 text-xs font-semibold">
            {[1, 3, 7].map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
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
        </div>
      </div>

      {/* Warning Banner */}
      <ForecastWarningBanner forecastData={forecastData} />

      {/* Forecast Summary Stat Cards */}
      <ForecastSummaryCards data={forecastData} loading={loading} />

      {/* Main Forecast Chart */}
      <ForecastChart
        forecastData={forecastData}
        horizon={horizon}
        onHorizonChange={setHorizon}
      />

      {/* Model Performance Comparison Card */}
      {selectedWardId && <ModelPerformanceCard wardId={selectedWardId} />}

      {/* Hospital Overview Card */}
      <HospitalForecastOverview hospitalId={hospitalId} />
    </div>
  );
};
