import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Ward, Hospital } from '../types';
import { getWards } from '../services/wardService';
import { hospitalService } from '../services/hospitalService';
import { forecastService, WardForecastResponse } from '../services/forecastService';
import { ForecastSummaryCards } from '../components/forecast/ForecastSummaryCards';
import { ForecastChart } from '../components/forecast/ForecastChart';
import { ForecastWarningBanner } from '../components/forecast/ForecastWarningBanner';
import { ModelPerformanceCard } from '../components/forecast/ModelPerformanceCard';
import { HospitalForecastOverview } from '../components/forecast/HospitalForecastOverview';
import { CapacityAlertsSection } from '../components/CapacityAlertsSection';
import {
  TrendingUp,
  RefreshCw,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Play,
  Database,
  Calendar,
  Building,
} from 'lucide-react';
import { getDataQualityReport, getWardCapacityHistory } from '../services/ingestionService';

interface CapacityHistoryItem {
  snapshot_time?: string;
  date?: string;
  occupancy_percentage?: number | string;
}

interface HistoricalDataPoint {
  date: string;
  occupancy_percentage: number;
}

interface HistoricalDataQualityReport {
  total_observations?: number;
  total_snapshots?: number;
  data_frequency?: string;
  earliest_observation_date?: string;
  latest_observation_date?: string;
  health_score?: number;
  missing_dates?: number;
}

const extractErrorMessage = (err: unknown, defaultMessage: string): string => {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) {
      return response.data.detail;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return defaultMessage;
};

export const ForecastPage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number>(user?.hospital_id || 1);
  const [wards, setWards] = useState<Ward[]>([]);
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);
  const [horizon, setHorizon] = useState<number>(7);

  const [forecastData, setForecastData] = useState<WardForecastResponse | null>(null);
  const [historicalData, setHistoricalData] = useState<HistoricalDataPoint[]>([]);
  const [qualityReport, setQualityReport] = useState<HistoricalDataQualityReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load all available hospitals for all users (Doctors, Nurses, Admins)
  useEffect(() => {
    hospitalService
      .getHospitals({ limit: 100 })
      .then((res) => {
        setHospitals(res.items);
        if (res.items.length > 0 && !res.items.some((h) => h.id === selectedHospitalId)) {
          setSelectedHospitalId(res.items[0].id);
        }
      })
      .catch((err) => console.error('Failed to load hospitals list:', err));
  }, []);

  // Load Quality Report for selected hospital
  useEffect(() => {
    getDataQualityReport(selectedHospitalId)
      .then(setQualityReport)
      .catch((err) => console.error('Failed to load data quality report:', err));
  }, [selectedHospitalId]);

  // Load Wards List for selected hospital
  useEffect(() => {
    getWards({ hospital_id: selectedHospitalId, limit: 100 })
      .then((res) => {
        const hospWards = res.items.filter(
          (w) => !selectedHospitalId || w.hospital_id === selectedHospitalId
        );
        const finalWards = hospWards.length > 0 ? hospWards : res.items;
        // Sort so ICU appears first for immediate high-impact demo
        finalWards.sort((a, b) => {
          if (a.ward_type === 'ICU') return -1;
          if (b.ward_type === 'ICU') return 1;
          return a.name.localeCompare(b.name);
        });
        setWards(finalWards);
        setSelectedWardId(finalWards.length > 0 ? finalWards[0].id : null);
      })
      .catch((err) => console.error('Failed to load wards for forecasting:', err));
  }, [selectedHospitalId]);

  // Fetch Ward Forecast Data + 14-day history for the chart
  const fetchForecast = useCallback(async () => {
    if (!selectedWardId) return;
    setLoading(true);
    setError(null);
    try {
      const [res, historyRes] = await Promise.all([
        forecastService.getWardForecast(selectedWardId, horizon),
        getWardCapacityHistory(selectedWardId, { limit: 14 }).catch(() => null),
      ]);
      setForecastData(res);
      if (historyRes && Array.isArray(historyRes.items)) {
        const mapped: HistoricalDataPoint[] = (historyRes.items as CapacityHistoryItem[])
          .map((item) => ({
            date: item.snapshot_time ? item.snapshot_time.slice(0, 10) : item.date || '',
            occupancy_percentage: Number(item.occupancy_percentage || 0),
          }))
          .filter((item) => Boolean(item.date))
          .sort((a, b) => a.date.localeCompare(b.date));
        setHistoricalData(mapped);
      }
    } catch (err: unknown) {
      console.error('Failed to fetch forecast:', err);
      setError(extractErrorMessage(err, 'Failed to load bed capacity forecast.'));
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
      const res = await forecastService.generateManualForecast(selectedHospitalId, horizon);
      setToastMessage(
        `Forecast pipeline executed successfully! (${res.forecasts_generated} forecasts generated).`
      );
      setTimeout(() => setToastMessage(null), 4000);
      fetchForecast();
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to run manual forecast generation.'));
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

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 rounded-xl shadow-lg border bg-rose-50 dark:bg-rose-950/90 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
            <span className="text-sm font-semibold">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs font-bold underline hover:opacity-80 ml-3 shrink-0"
          >
            Dismiss
          </button>
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

      {/* Hospital, Ward & Horizon Controls */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Hospital Selector for All Roles */}
          {hospitals.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider shrink-0 flex items-center gap-1">
                <Building className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
                Hospital:
              </label>
              <select
                value={selectedHospitalId}
                onChange={(e) => setSelectedHospitalId(Number(e.target.value))}
                className="px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-bold"
              >
                {hospitals.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name} ({h.code})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Ward Selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider shrink-0">
              Ward:
            </label>
            <select
              value={selectedWardId || ''}
              onChange={(e) => setSelectedWardId(Number(e.target.value))}
              className="w-full sm:w-60 px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-bold"
            >
              {wards.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.ward_type}) &bull; {w.capacity} beds
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Horizon Buttons */}
        <div className="flex items-center gap-2 self-start md:self-auto">
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

      {/* Historical Data Quality & Provenance Banner */}
      {qualityReport && (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs flex flex-wrap items-center justify-between gap-3 text-slate-600 dark:text-slate-300">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-sky-500" />
            <span className="font-bold text-slate-800 dark:text-slate-100">
              Historical Data Coverage:
            </span>
            <span>
              {qualityReport.total_observations ?? qualityReport.total_snapshots ?? 0} daily records (
              {qualityReport.data_frequency || 'DAILY'})
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-purple-500" />
            <span className="font-bold text-slate-800 dark:text-slate-100">Date Range:</span>
            <span>
              {qualityReport.earliest_observation_date
                ? `${qualityReport.earliest_observation_date} to ${qualityReport.latest_observation_date}`
                : 'Continuous'}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Health Score: {qualityReport.health_score ?? 100}%
            </span>
            {(qualityReport.missing_dates ?? 0) > 0 && (
              <span className="inline-flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400">
                <AlertCircle className="w-3.5 h-3.5" />
                {qualityReport.missing_dates} missing dates imputed
              </span>
            )}
          </div>
        </div>
      )}

      {/* Warning Banner */}
      <ForecastWarningBanner forecastData={forecastData} />

      {/* Forecast Summary Stat Cards */}
      <ForecastSummaryCards data={forecastData} loading={loading} />

      {/* Main Forecast Chart */}
      <ForecastChart
        forecastData={forecastData}
        historicalData={historicalData}
        horizon={horizon}
        onHorizonChange={setHorizon}
      />

      {/* Explainable AI Bed Capacity Alerts Section */}
      <CapacityAlertsSection hospitalId={selectedHospitalId} />

      {/* Model Performance Comparison Card */}
      {selectedWardId && <ModelPerformanceCard wardId={selectedWardId} />}

      {/* Hospital Overview Card */}
      <HospitalForecastOverview hospitalId={selectedHospitalId} />
    </div>
  );
};
